from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class ApiEndpointCreate(BaseModel):
    name: str = ""
    method: str = "GET"
    host: str = "https://api.example.com"
    path: str = "/"
    headers: str = "{}"
    body: str = "{}"


class ApiEndpointUpdate(BaseModel):
    name: Optional[str] = None
    method: Optional[str] = None
    host: Optional[str] = None
    path: Optional[str] = None
    headers: Optional[str] = None
    body: Optional[str] = None


class ApiEndpointOut(BaseModel):
    id: int
    name: str
    method: str
    host: str
    path: str
    headers: str
    body: str
    last_response: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SshServerCreate(BaseModel):
    name: str = ""
    host: str = ""
    port: int = 22
    username: str = "root"
    password: str = ""
    work_dir: str = "/opt/locust-platform"
    env: str = "test"


class SshServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    work_dir: Optional[str] = None
    env: Optional[str] = None


class SshServerOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    username: str
    work_dir: str = "/opt/locust-platform"
    env: str
    status: str = "unknown"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScriptFileCreate(BaseModel):
    name: str = "stress_test.py"
    content: str = ""


class ScriptFileOut(BaseModel):
    id: int
    name: str
    content: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoadTaskCreate(BaseModel):
    name: str = ""
    script_file_id: Optional[int] = None
    server_id: Optional[int] = None
    target_host: str = "https://api.example.com"
    users: int = 100
    spawn_rate: int = 10
    run_time: str = "5m"
    run_mode: str = "headless"


class LoadTaskUpdate(BaseModel):
    name: Optional[str] = None
    script_file_id: Optional[int] = None
    server_id: Optional[int] = None
    target_host: Optional[str] = None
    users: Optional[int] = None
    spawn_rate: Optional[int] = None
    run_time: Optional[str] = None
    run_mode: Optional[str] = None


class LoadTaskOut(BaseModel):
    id: int
    name: str
    script_file_id: Optional[int]
    server_id: Optional[int]
    target_host: str
    users: int
    spawn_rate: int
    run_time: str
    run_mode: str = "headless"
    web_port: Optional[int] = None
    status: str
    remote_pid: Optional[int]
    exit_code: Optional[int]
    error_message: str
    report_path: str
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[object] = None
