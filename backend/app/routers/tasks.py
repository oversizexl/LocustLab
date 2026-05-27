import asyncio
import csv
import os
import shlex
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import LOGS_DIR, REPORTS_DIR
from app.crypto import decrypt
from app.database import async_session, get_db
from app.models import LoadTask, ScriptFile, SshServer
from app.schemas import ApiResponse, LoadTaskCreate, LoadTaskOut, LoadTaskUpdate
from app.services import ssh_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LoadTask).order_by(LoadTask.id.desc()))
    items = [
        LoadTaskOut.model_validate(row).model_dump() for row in result.scalars().all()
    ]
    return ApiResponse(data={"items": items, "total": len(items)})


@router.post("")
async def create_task(body: LoadTaskCreate, db: AsyncSession = Depends(get_db)):
    obj = LoadTask(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return ApiResponse(data=LoadTaskOut.model_validate(obj).model_dump())


@router.get("/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(LoadTask, task_id)
    if not obj:
        raise HTTPException(404, "task not found")
    return ApiResponse(data=LoadTaskOut.model_validate(obj).model_dump())


@router.put("/{task_id}")
async def update_task(
    task_id: int, body: LoadTaskUpdate, db: AsyncSession = Depends(get_db)
):
    obj = await db.get(LoadTask, task_id)
    if not obj:
        raise HTTPException(404, "task not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await db.commit()
    await db.refresh(obj)
    return ApiResponse(data=LoadTaskOut.model_validate(obj).model_dump())


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(LoadTask, task_id)
    if not obj:
        raise HTTPException(404, "task not found")
    await db.delete(obj)
    await db.commit()
    return ApiResponse(message="deleted")


@router.post("/{task_id}/precheck")
async def precheck_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(LoadTask, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    script = (
        await db.get(ScriptFile, task.script_file_id) if task.script_file_id else None
    )
    checks = []
    checks.append(
        {
            "name": "script_selected",
            "success": script is not None,
            "detail": script.name if script else "未选择脚本",
        }
    )
    checks.append(
        {
            "name": "target_host",
            "success": bool(task.target_host),
            "detail": task.target_host,
        }
    )
    checks.append(
        {"name": "users", "success": task.users > 0, "detail": str(task.users)}
    )
    checks.append(
        {
            "name": "spawn_rate",
            "success": task.spawn_rate > 0,
            "detail": str(task.spawn_rate),
        }
    )
    if task.server_id:
        server = await db.get(SshServer, task.server_id)
        if not server:
            checks.append(
                {"name": "server", "success": False, "detail": "压测机不存在"}
            )
        else:
            password = (
                decrypt(server.encrypted_password) if server.encrypted_password else ""
            )
            remote = await asyncio.to_thread(_remote_precheck, server, password)
            checks.extend(remote)
    else:
        locust_check = await asyncio.to_thread(
            _run_cmd, [sys.executable, "-m", "locust", "--version"], Path.cwd()
        )
        checks.append(
            {
                "name": "locust_installed",
                "success": locust_check["returncode"] == 0,
                "detail": locust_check["stdout"] or locust_check["stderr"],
            }
        )
    return ApiResponse(
        data={"success": all(item["success"] for item in checks), "checks": checks}
    )


@router.post("/{task_id}/start")
async def start_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(LoadTask, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if task.status == "running":
        return ApiResponse(code=400, message="task is already running")
    if not task.script_file_id:
        return ApiResponse(code=400, message="no script file selected")

    script = await db.get(ScriptFile, task.script_file_id)
    if not script:
        return ApiResponse(code=400, message="script not found")

    task.status = "running"
    task.error_message = ""
    task.started_at = datetime.utcnow()
    task.finished_at = None
    await db.commit()
    await db.refresh(task)

    if task.server_id:
        asyncio.create_task(_run_remote_locust(task.id))
    else:
        asyncio.create_task(_run_local_locust(task.id))
    return ApiResponse(
        message="task started", data=LoadTaskOut.model_validate(task).model_dump()
    )


@router.post("/{task_id}/stop")
async def stop_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(LoadTask, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if task.remote_pid:
        if task.server_id:
            server = await db.get(SshServer, task.server_id)
            if server:
                password = (
                    decrypt(server.encrypted_password)
                    if server.encrypted_password
                    else ""
                )
                try:
                    ssh = await asyncio.to_thread(
                        ssh_service.create_ssh_client,
                        server.host,
                        server.port,
                        server.username,
                        password,
                    )
                    await asyncio.to_thread(
                        ssh_service.execute_command,
                        ssh,
                        f"kill {task.remote_pid} 2>/dev/null || true",
                    )
                    ssh.close()
                except Exception as exc:
                    task.error_message = f"remote stop warning: {exc}"
        else:
            try:
                os.kill(task.remote_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except Exception as exc:
                task.error_message = f"stop warning: {exc}"
    task.status = "stopped"
    task.finished_at = datetime.utcnow()
    await db.commit()
    return ApiResponse(
        message="task stopped", data=LoadTaskOut.model_validate(task).model_dump()
    )


@router.get("/{task_id}/logs")
async def get_task_logs(task_id: int):
    log_path = LOGS_DIR / f"task_{task_id}.log"
    if log_path.exists():
        return ApiResponse(
            data={"content": log_path.read_text(encoding="utf-8", errors="replace")}
        )
    return ApiResponse(data={"content": "no logs available"})


@router.get("/{task_id}/stats")
async def get_task_stats(task_id: int):
    stats_path = REPORTS_DIR / f"task_{task_id}" / "result_stats.csv"
    history_path = REPORTS_DIR / f"task_{task_id}" / "result_stats_history.csv"
    return ApiResponse(
        data={
            "summary": _parse_stats(stats_path),
            "history": _parse_history(history_path),
        }
    )


@router.get("/{task_id}/report")
async def view_report(task_id: int):
    report_path = REPORTS_DIR / f"task_{task_id}" / "report.html"
    if not report_path.exists():
        return HTMLResponse("<h3>report not found</h3>", status_code=404)
    return HTMLResponse(report_path.read_text(encoding="utf-8", errors="replace"))


@router.get("/{task_id}/report/download")
async def download_report(task_id: int):
    report_path = REPORTS_DIR / f"task_{task_id}" / "report.html"
    if not report_path.exists():
        raise HTTPException(404, "report not found")
    return FileResponse(report_path, filename=f"task_{task_id}_report.html")


async def _run_local_locust(task_id: int):
    async with async_session() as db:
        task = await db.get(LoadTask, task_id)
        if not task:
            return
        script = await db.get(ScriptFile, task.script_file_id)
        if not script:
            task.status = "failed"
            task.error_message = "script not found"
            task.finished_at = datetime.utcnow()
            await db.commit()
            return

    report_dir = REPORTS_DIR / f"task_{task_id}"
    report_dir.mkdir(parents=True, exist_ok=True)
    work_dir = report_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    script_filename = _script_filename(script)
    locust_file = work_dir / script_filename
    locust_file.write_text(script.content, encoding="utf-8")

    log_path = LOGS_DIR / f"task_{task_id}.log"
    csv_prefix = report_dir / "result"
    if task.run_mode == "web_ui":
        web_port = 8090 + task_id
        cmd = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            str(locust_file),
            "--web-host",
            "0.0.0.0",
            "--web-port",
            str(web_port),
            "--host",
            task.target_host,
            "--csv",
            str(csv_prefix),
            "--csv-full-history",
            "--loglevel",
            "INFO",
        ]
    else:
        web_port = None
        cmd = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            str(locust_file),
            "--headless",
            "-u",
            str(task.users),
            "-r",
            str(task.spawn_rate),
            "--run-time",
            task.run_time,
            "--host",
            task.target_host,
            "--html",
            str(report_dir / "report.html"),
            "--csv",
            str(csv_prefix),
            "--csv-full-history",
            "--loglevel",
            "INFO",
        ]
    log_path.write_text("$ " + " ".join(cmd) + "\n", encoding="utf-8")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async with async_session() as db:
            task = await db.get(LoadTask, task_id)
            if task:
                task.remote_pid = proc.pid
                task.web_port = web_port
                await db.commit()

        output = []
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode(errors="replace")
            output.append(text)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(text)
        if task.run_mode == "web_ui":
            return_code = await proc.wait()
        else:
            return_code = await proc.wait()

        async with async_session() as db:
            task = await db.get(LoadTask, task_id)
            if task:
                task.status = "success" if return_code == 0 else "failed"
                task.exit_code = return_code
                task.report_path = str(report_dir)
                task.error_message = (
                    "" if return_code == 0 else "locust exited with non-zero status"
                )
                task.finished_at = datetime.utcnow()
                await db.commit()
    except Exception as exc:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"\nERROR: {exc}\n")
        async with async_session() as db:
            task = await db.get(LoadTask, task_id)
            if task:
                task.status = "failed"
                task.error_message = str(exc)
                task.finished_at = datetime.utcnow()
                await db.commit()


async def _run_remote_locust(task_id: int):
    async with async_session() as db:
        task = await db.get(LoadTask, task_id)
        if not task:
            return
        script = await db.get(ScriptFile, task.script_file_id)
        server = await db.get(SshServer, task.server_id)
        if not script or not server:
            if task:
                task.status = "failed"
                task.error_message = "script or server not found"
                task.finished_at = datetime.utcnow()
                await db.commit()
            return
        password = (
            decrypt(server.encrypted_password) if server.encrypted_password else ""
        )

    report_dir = REPORTS_DIR / f"task_{task_id}"
    report_dir.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"task_{task_id}.log"
    remote_base = (server.work_dir or "/opt/locust-platform").rstrip("/")
    remote_dir = f"{remote_base}/tasks/task_{task_id}"
    script_filename = _script_filename(script)
    quoted_script_filename = shlex.quote(script_filename)
    script_path = f"{remote_dir}/{script_filename}"
    csv_prefix = f"{remote_dir}/result"
    web_port = 8090 + task_id if task.run_mode == "web_ui" else None

    if task.run_mode == "web_ui":
        command = (
            f"cd {remote_dir} && nohup python3 -m locust -f {quoted_script_filename} "
            f"--web-host 0.0.0.0 --web-port {web_port} --host {task.target_host} "
            f"--csv result --csv-full-history --loglevel INFO > stdout.log 2>&1 & echo $!"
        )
    else:
        command = (
            f"cd {remote_dir} && nohup python3 -m locust -f {quoted_script_filename} --headless "
            f"-u {task.users} -r {task.spawn_rate} --run-time {task.run_time} --host {task.target_host} "
            f"--html report.html --csv result --csv-full-history --loglevel INFO > stdout.log 2>&1 & echo $!"
        )
    log_path.write_text(f"remote={server.host}\n$ {command}\n", encoding="utf-8")

    try:
        ssh = await asyncio.to_thread(
            ssh_service.create_ssh_client,
            server.host,
            server.port,
            server.username,
            password,
        )
        await asyncio.to_thread(
            ssh_service.execute_command, ssh, f"mkdir -p {remote_dir}"
        )
        await asyncio.to_thread(
            ssh_service.upload_file, ssh, script.content, script_path
        )
        result = await asyncio.to_thread(ssh_service.execute_command, ssh, command)
        pid = (
            (result.get("stdout") or "").strip().splitlines()[-1]
            if result.get("stdout")
            else ""
        )

        async with async_session() as db:
            task_db = await db.get(LoadTask, task_id)
            if task_db:
                task_db.remote_pid = int(pid) if pid.isdigit() else None
                task_db.web_port = web_port
                task_db.report_path = str(report_dir)
                await db.commit()

        if task.run_mode == "web_ui":
            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"Locust Web UI: http://{server.host}:{web_port}\n")
            ssh.close()
            return

        await asyncio.sleep(_parse_run_time(task.run_time) + 5)
        await _collect_remote_files(ssh, remote_dir, report_dir, log_path)
        ssh.close()

        async with async_session() as db:
            task_db = await db.get(LoadTask, task_id)
            if task_db:
                task_db.status = "success"
                task_db.finished_at = datetime.utcnow()
                task_db.report_path = str(report_dir)
                await db.commit()
    except Exception as exc:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"\nERROR: {exc}\n")
        async with async_session() as db:
            task_db = await db.get(LoadTask, task_id)
            if task_db:
                task_db.status = "failed"
                task_db.error_message = str(exc)
                task_db.finished_at = datetime.utcnow()
                await db.commit()


async def _collect_remote_files(ssh, remote_dir: str, report_dir: Path, log_path: Path):
    files = [
        "report.html",
        "result_stats.csv",
        "result_stats_history.csv",
        "result_failures.csv",
        "result_exceptions.csv",
    ]
    for name in files:
        data = await asyncio.to_thread(
            ssh_service.download_file, ssh, f"{remote_dir}/{name}"
        )
        if data:
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            (report_dir / name).write_text(data, encoding="utf-8")
    stdout = await asyncio.to_thread(
        ssh_service.download_file, ssh, f"{remote_dir}/stdout.log"
    )
    if stdout:
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        log_path.write_text(stdout, encoding="utf-8")


def _remote_precheck(server: SshServer, password: str) -> list[dict]:
    checks = []
    try:
        ssh = ssh_service.create_ssh_client(
            server.host, server.port, server.username, password
        )
        checks.append(
            {"name": "ssh_connection", "success": True, "detail": server.host}
        )
        commands = {
            "python3": "python3 --version",
            "locust": "python3 -m locust --version",
            "work_dir": f"mkdir -p {(server.work_dir or '/opt/locust-platform').rstrip('/')}/tasks/precheck && test -w {(server.work_dir or '/opt/locust-platform').rstrip('/')}/tasks/precheck && echo writable",
        }
        for name, cmd in commands.items():
            result = ssh_service.execute_command(ssh, cmd)
            detail = (result.get("stdout") or result.get("stderr") or "").strip()
            checks.append(
                {
                    "name": name,
                    "success": result.get("exit_code") == 0,
                    "detail": detail,
                }
            )
        ssh.close()
    except Exception as exc:
        checks.append({"name": "ssh_connection", "success": False, "detail": str(exc)})
    return checks


def _run_cmd(cmd: list[str], cwd: Path) -> dict:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def _script_filename(script: ScriptFile) -> str:
    name = Path(script.name or "stress_test.py").name
    return name if name.endswith(".py") else f"{name}.py"


def _parse_run_time(run_time: str) -> int:
    run_time = run_time.strip()
    if run_time.endswith("s"):
        return int(run_time[:-1])
    if run_time.endswith("m"):
        return int(run_time[:-1]) * 60
    if run_time.endswith("h"):
        return int(run_time[:-1]) * 3600
    try:
        return int(run_time)
    except ValueError:
        return 300


def _parse_stats(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    total = next(
        (row for row in rows if row.get("Name") == "Aggregated"),
        rows[-1] if rows else {},
    )
    return total


def _parse_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    return rows[-60:]
