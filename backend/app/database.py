from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import DB_URL

engine = create_async_engine(DB_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite 暂未接入 Alembic，做最小字段迁移，别让旧库直接炸。
        columns = await conn.execute(text("PRAGMA table_info(load_tasks)"))
        existing = {row[1] for row in columns.fetchall()}
        if "run_mode" not in existing:
            await conn.execute(
                text(
                    "ALTER TABLE load_tasks ADD COLUMN run_mode VARCHAR DEFAULT 'headless'"
                )
            )
        if "web_port" not in existing:
            await conn.execute(
                text("ALTER TABLE load_tasks ADD COLUMN web_port INTEGER")
            )
        server_columns = await conn.execute(text("PRAGMA table_info(ssh_servers)"))
        existing_server = {row[1] for row in server_columns.fetchall()}
        if "work_dir" not in existing_server:
            await conn.execute(
                text(
                    "ALTER TABLE ssh_servers ADD COLUMN work_dir VARCHAR DEFAULT '/opt/locust-platform'"
                )
            )


async def get_db():
    async with async_session() as session:
        yield session
