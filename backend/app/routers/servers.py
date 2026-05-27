import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import SshServer
from app.schemas import SshServerCreate, SshServerUpdate, SshServerOut, ApiResponse
from app.crypto import encrypt, decrypt
from app.services.ssh_service import test_connection

router = APIRouter(prefix="/api/servers", tags=["servers"])


@router.get("")
async def list_servers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SshServer).order_by(SshServer.id.desc()))
    items = []
    for row in result.scalars().all():
        item = SshServerOut.model_validate(row).model_dump()
        item["password"] = decrypt(row.encrypted_password) if row.encrypted_password else ""
        items.append(item)
    return ApiResponse(data={"items": items, "total": len(items)})


@router.post("")
async def create_server(body: SshServerCreate, db: AsyncSession = Depends(get_db)):
    obj = SshServer(
        name=body.name,
        host=body.host,
        port=body.port,
        username=body.username,
        encrypted_password=encrypt(body.password) if body.password else "",
        work_dir=body.work_dir,
        env=body.env,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return ApiResponse(data=SshServerOut.model_validate(obj).model_dump())


@router.get("/{server_id}")
async def get_server(server_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(SshServer, server_id)
    if not obj:
        raise HTTPException(404, "server not found")
    item = SshServerOut.model_validate(obj).model_dump()
    item["password"] = decrypt(obj.encrypted_password) if obj.encrypted_password else ""
    return ApiResponse(data=item)


@router.put("/{server_id}")
async def update_server(server_id: int, body: SshServerUpdate, db: AsyncSession = Depends(get_db)):
    obj = await db.get(SshServer, server_id)
    if not obj:
        raise HTTPException(404, "server not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        if key == "password":
            obj.encrypted_password = encrypt(value) if value else ""
        else:
            setattr(obj, key, value)
    await db.commit()
    await db.refresh(obj)
    return ApiResponse(data=SshServerOut.model_validate(obj).model_dump())


@router.delete("/{server_id}")
async def delete_server(server_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(SshServer, server_id)
    if not obj:
        raise HTTPException(404, "server not found")
    await db.delete(obj)
    await db.commit()
    return ApiResponse(message="deleted")


@router.post("/{server_id}/test")
async def test_server(server_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(SshServer, server_id)
    if not obj:
        raise HTTPException(404, "server not found")
    password = decrypt(obj.encrypted_password) if obj.encrypted_password else ""
    result = await asyncio.to_thread(test_connection, obj.host, obj.port, obj.username, password)
    return ApiResponse(data=result)
