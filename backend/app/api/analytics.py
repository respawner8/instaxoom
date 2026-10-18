import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import SiteVisit, User
from app.api.deps import get_current_user_optional

logger = logging.getLogger("app.analytics")
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


class RecordVisitRequest(BaseModel):
    visitor_id: str = Field(..., min_length=1, max_length=64, description="Anonymous or persistent visitor identifier")
    path: Optional[str] = Field(default="/", max_length=255)
    referrer: Optional[str] = Field(default=None, max_length=1000)


@router.post("/visit")
async def record_site_visit(
    body: RecordVisitRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Records a page visit or session beacon ping.
    Supports both anonymous visitors and authenticated users.
    Returns quickly to avoid blocking frontend rendering.
    """
    try:
        user_agent = request.headers.get("user-agent", "")[:500] if request.headers.get("user-agent") else None
        clean_visitor_id = body.visitor_id.strip()[:64]
        if not clean_visitor_id:
            return {"status": "ignored", "reason": "empty_visitor_id"}

        visit = SiteVisit(
            visitor_id=clean_visitor_id,
            user_id=current_user.id if current_user else None,
            path=(body.path or "/")[:255],
            referrer=body.referrer[:1000] if body.referrer else None,
            user_agent=user_agent,
        )
        db.add(visit)
        await db.commit()
        return {"status": "recorded"}
    except Exception as e:
        await db.rollback()
        logger.warning(f"Failed to record site visit: {e}")
        return {"status": "error"}
