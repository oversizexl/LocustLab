from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ApiEndpoint
from app.schemas import ApiEndpointCreate, ApiEndpointUpdate, ApiEndpointOut, ApiResponse
import httpx
import time
import gzip
import zlib
import brotli

router = APIRouter(prefix="/api/endpoints", tags=["endpoints"])


@router.get("")
async def list_endpoints(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiEndpoint).order_by(ApiEndpoint.id.desc()))
    items = [ApiEndpointOut.model_validate(row).model_dump() for row in result.scalars().all()]
    return ApiResponse(data={"items": items, "total": len(items)})


@router.post("")
async def create_endpoint(body: ApiEndpointCreate, db: AsyncSession = Depends(get_db)):
    obj = ApiEndpoint(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return ApiResponse(data=ApiEndpointOut.model_validate(obj).model_dump())


@router.get("/{endpoint_id}")
async def get_endpoint(endpoint_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(ApiEndpoint, endpoint_id)
    if not obj:
        raise HTTPException(404, "endpoint not found")
    return ApiResponse(data=ApiEndpointOut.model_validate(obj).model_dump())


@router.put("/{endpoint_id}")
async def update_endpoint(endpoint_id: int, body: ApiEndpointUpdate, db: AsyncSession = Depends(get_db)):
    obj = await db.get(ApiEndpoint, endpoint_id)
    if not obj:
        raise HTTPException(404, "endpoint not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await db.commit()
    await db.refresh(obj)
    return ApiResponse(data=ApiEndpointOut.model_validate(obj).model_dump())


@router.delete("/{endpoint_id}")
async def delete_endpoint(endpoint_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(ApiEndpoint, endpoint_id)
    if not obj:
        raise HTTPException(404, "endpoint not found")
    await db.delete(obj)
    await db.commit()
    return ApiResponse(message="deleted")


@router.post("/{endpoint_id}/test")
async def test_endpoint(endpoint_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(ApiEndpoint, endpoint_id)
    if not obj:
        raise HTTPException(404, "endpoint not found")

    url = f"{obj.host.rstrip('/')}{obj.path}"
    try:
        import json as _json
        headers = _json.loads(obj.headers) if obj.headers else {}
        # 避免目标服务返回 br/gzip 后前端看到一坨压缩二进制乱码。
        # 用户传了 Accept-Encoding 也强制改成 identity，压测脚本里仍会保留原 header。
        headers["Accept-Encoding"] = "identity"
    except Exception:
        headers = {}

    try:
        started = time.time()
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            if obj.method == "POST":
                resp = await client.post(url, headers=headers, content=obj.body or "")
            else:
                resp = await client.get(url, headers=headers)
        elapsed = int((time.time() - started) * 1000)
        body_text = format_response_body(decode_response_body(resp))
        result = {
            "ok": resp.is_success,
            "status": resp.status_code,
            "duration_ms": elapsed,
            "headers": dict(resp.headers),
            "body": body_text[:50000],
        }
        obj.last_response = _json.dumps(result, ensure_ascii=False, indent=2)
        await db.commit()
        return ApiResponse(data=result)
    except Exception as e:
        return ApiResponse(code=500, message=str(e), data={"ok": False, "error": str(e)})


def decode_response_body(resp: httpx.Response) -> str:
    encoding = (resp.headers.get("content-encoding") or "").lower()
    content = resp.content

    try:
        if "br" in encoding:
            content = brotli.decompress(content)
        elif "gzip" in encoding:
            content = gzip.decompress(content)
        elif "deflate" in encoding:
            content = zlib.decompress(content)
    except Exception:
        # httpx 可能已经解过压，再手动解会失败；失败就继续按原 content 解码。
        content = resp.content

    charset = resp.encoding or "utf-8"
    try:
        return content.decode(charset, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


def format_response_body(body: str) -> str:
    try:
        parsed = __import__("json").loads(body)
        return __import__("json").dumps(parsed, ensure_ascii=False, indent=2)
    except Exception:
        return body
