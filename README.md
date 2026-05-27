# Locust Pressure Platform

压测管理平台：接口管理、压测机管理、Locust 脚本生成、压测任务执行。

## 项目结构

```
locust-pressure-platform/
  backend/           FastAPI 后端
    app/
      main.py        入口 + CORS
      config.py      路径、DB、SECRET_KEY
      database.py    SQLAlchemy async + SQLite
      models.py      ORM 模型
      schemas.py     Pydantic 请求/响应
      crypto.py      Fernet 密码加密
      routers/       endpoints / servers / scripts / tasks
      services/      ssh_service (Paramiko) / locust_service (Jinja2)
    storage/         SQLite DB + scripts + reports + logs
    requirements.txt
  src/               React 前端
  vite.config.ts     Vite dev proxy -> 0.0.0.0:8000
```

## 快速启动

### 1. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

启动后打开 http://0.0.0.0:8000/docs 查看 API 文档。

### 2. 启动前端

```bash
cd ..
npm install
npm run dev
```

浏览器打开 http://localhost:5173。

### 3. 使用流程

1. **接口管理**：添加被压测接口，点击“测试”发起真实 HTTP 请求
2. **压测机管理**：添加堡垒机可 SSH 到的压测机（Host/端口/用户名/密码/工作目录），点击“测试”通过 Paramiko 连接并检查环境
3. **脚本生成**：勾选接口，自动生成 Locust 脚本（Jinja2 模板），可编辑、复制、下载、保存到后端
4. **压测任务**：
   - 选择脚本文件
   - 执行位置选择“本机执行”或某台压测机
   - 运行模式选择 `Headless` 或 `Locust Web UI`
   - 设置并发用户数、启动速率、运行时长、目标 Host
   - 点击“预检”：检查脚本、目标 Host、Locust 环境、远程工作目录
   - 点击“启动”：
     - 本机执行：后端本机启动 `python -m locust`
     - 远程执行：堡垒机通过 Paramiko SSH 到压测机，SFTP 上传 `stress_test.py`，远程启动 Locust
5. 任务详情可查看日志、统计 CSV、HTML 报告；Web UI 模式会内嵌 Locust 原生页面

### 4. 压测机要求

```bash
python3 -m pip install locust
sudo mkdir -p /opt/locust-platform/tasks
sudo chown -R $USER:$USER /opt/locust-platform
```

压测机需满足：

- 堡垒机可以 SSH 访问
- 已安装 `python3` 和 `locust`
- 工作目录可写，默认 `/opt/locust-platform`
- 如果使用 `Locust Web UI` 模式，浏览器需要能访问 `http://压测机IP:8090+任务ID`

### 5. 环境变量（可选）

```bash
STORAGE_DIR=./backend/storage
SECRET_KEY=your-secret-key
```

## 技术栈

- 后端：FastAPI + SQLAlchemy async + SQLite + Paramiko + httpx + Jinja2
- 前端：React + TypeScript + Vite + lucide-react
