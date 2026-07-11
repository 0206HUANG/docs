"""
Public open-tracking endpoint. Returns a 1x1 transparent PNG and bumps the
open counters for the matching scheduled email. Deliberately unauthenticated
(email clients fetch it), and it leaks nothing beyond the pixel itself.
"""
import base64
import uuid

from fastapi import APIRouter, Response

from app.api.deps import DB

router = APIRouter()

# 1x1 transparent PNG
_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@router.get("/open/{tracking_id}")
async def track_open(tracking_id: str, db: DB):
    try:
        tid = uuid.UUID(tracking_id)
    except ValueError:
        tid = None
    if tid is not None:
        from app.services.outbox import record_open
        try:
            await record_open(db, tid)
        except Exception:
            pass  # tracking must never fail the pixel response
    return Response(
        content=_PIXEL,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
