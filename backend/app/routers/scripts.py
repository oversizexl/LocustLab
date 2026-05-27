from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ApiEndpoint, ScriptFile
from app.schemas import ScriptFileCreate, ScriptFileOut, ApiResponse
from app.services.locust_service import generate_locust_script
from app.config import SCRIPTS_DIR

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.get("")
async def list_scripts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScriptFile).order_by(ScriptFile.id.desc()))
    items = [
        ScriptFileOut.model_validate(row).model_dump() for row in result.scalars().all()
    ]
    return ApiResponse(data={"items": items, "total": len(items)})


@router.post("")
async def create_script(body: ScriptFileCreate, db: AsyncSession = Depends(get_db)):
    obj = ScriptFile(name=body.name, content=body.content)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)

    script_path = SCRIPTS_DIR / f"{obj.id}_{obj.name}"
    script_path.write_text(body.content, encoding="utf-8")
    obj.storage_path = str(script_path)
    await db.commit()

    return ApiResponse(data=ScriptFileOut.model_validate(obj).model_dump())


@router.get("/{script_id}")
async def get_script(script_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(ScriptFile, script_id)
    if not obj:
        raise HTTPException(404, "script not found")
    return ApiResponse(data=ScriptFileOut.model_validate(obj).model_dump())


@router.delete("/{script_id}")
async def delete_script(script_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(ScriptFile, script_id)
    if not obj:
        raise HTTPException(404, "script not found")
    await db.delete(obj)
    await db.commit()
    return ApiResponse(message="deleted")


@router.post("/generate")
async def generate_script(body: dict, db: AsyncSession = Depends(get_db)):
    endpoint_ids = body.get("endpoint_ids", [])
    filename = body.get("filename") or "stress_test.py"
    if not endpoint_ids:
        result = await db.execute(select(ApiEndpoint).order_by(ApiEndpoint.id.desc()))
        endpoints = result.scalars().all()
    else:
        result = await db.execute(
            select(ApiEndpoint).where(ApiEndpoint.id.in_(endpoint_ids))
        )
        endpoints = result.scalars().all()

    endpoint_dicts = [
        {
            "id": ep.id,
            "name": ep.name,
            "method": ep.method,
            "host": ep.host,
            "path": ep.path,
            "headers": ep.headers,
            "body": ep.body,
        }
        for ep in endpoints
    ]

    script_content = generate_locust_script(endpoint_dicts, filename=filename)
    return ApiResponse(data={"content": script_content})
