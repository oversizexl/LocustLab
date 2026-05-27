from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(default="")
    method: Mapped[str] = mapped_column(default="GET")
    host: Mapped[str] = mapped_column(default="https://api.example.com")
    path: Mapped[str] = mapped_column(default="/")
    headers: Mapped[str] = mapped_column(default="{}")
    body: Mapped[str] = mapped_column(default="{}")
    last_response: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class SshServer(Base):
    __tablename__ = "ssh_servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(default="")
    host: Mapped[str] = mapped_column(default="")
    port: Mapped[int] = mapped_column(default=22)
    username: Mapped[str] = mapped_column(default="root")
    encrypted_password: Mapped[str] = mapped_column(default="")
    work_dir: Mapped[str] = mapped_column(default="/opt/locust-platform")
    env: Mapped[str] = mapped_column(default="test")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class ScriptFile(Base):
    __tablename__ = "script_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(default="")
    content: Mapped[str] = mapped_column(default="")
    storage_path: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class LoadTask(Base):
    __tablename__ = "load_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(default="")
    script_file_id: Mapped[int | None] = mapped_column(nullable=True)
    server_id: Mapped[int | None] = mapped_column(ForeignKey("ssh_servers.id"), nullable=True)
    target_host: Mapped[str] = mapped_column(default="https://api.example.com")
    users: Mapped[int] = mapped_column(default=100)
    spawn_rate: Mapped[int] = mapped_column(default=10)
    run_time: Mapped[str] = mapped_column(default="5m")
    run_mode: Mapped[str] = mapped_column(default="headless")
    web_port: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="draft")
    remote_pid: Mapped[int | None] = mapped_column(nullable=True)
    exit_code: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str] = mapped_column(default="")
    report_path: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
