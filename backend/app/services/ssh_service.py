import io
import paramiko
from pathlib import Path
from typing import Optional


def create_ssh_client(host: str, port: int, username: str, password: str) -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, port=port, username=username, password=password, timeout=10)
    return ssh


def execute_command(ssh: paramiko.SSHClient, command: str, timeout: int = 60) -> dict:
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    return {
        "stdout": stdout.read().decode(errors="ignore"),
        "stderr": stderr.read().decode(errors="ignore"),
        "exit_code": stdout.channel.recv_exit_status(),
    }


def upload_file(ssh: paramiko.SSHClient, local_content: str, remote_path: str):
    sftp = ssh.open_sftp()
    try:
        remote_dir = str(Path(remote_path).parent)
        execute_command(ssh, f"mkdir -p {remote_dir}")
        with sftp.file(remote_path, "w") as f:
            f.write(local_content)
    finally:
        sftp.close()


def download_file(ssh: paramiko.SSHClient, remote_path: str) -> str:
    sftp = ssh.open_sftp()
    try:
        with sftp.file(remote_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    finally:
        sftp.close()


def test_connection(host: str, port: int, username: str, password: str) -> dict:
    try:
        ssh = create_ssh_client(host, port, username, password)
        result = execute_command(ssh, "uname -a && python3 --version && locust --version 2>/dev/null || echo 'locust not installed'")
        ssh.close()
        return {"success": True, "detail": result["stdout"]}
    except Exception as e:
        return {"success": False, "error": str(e)}
