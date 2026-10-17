import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User, UserCredit, PendingCredit, CreditTransaction, ThemePreset
from app.api.deps import get_admin_user

router = APIRouter(prefix="/api/admin", tags=["Admin Portal"])


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned)


class ThemeCreateRequest(BaseModel):
    id: Optional[str] = None
    title: str
    category: Optional[str] = "General"
    tagline: Optional[str] = ""
    prompt_template: str
    hashtags: Optional[List[str]] = []
    preview_image_url: Optional[str] = None
    is_active: bool = True
    order_index: int = 0


class ThemeUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    tagline: Optional[str] = None
    prompt_template: Optional[str] = None
    hashtags: Optional[List[str]] = None
    preview_image_url: Optional[str] = None
    is_active: Optional[bool] = None
    order_index: Optional[int] = None



class AssignCreditRequest(BaseModel):
    email: EmailStr
    credits: int = 5
    description: Optional[str] = "Admin trial credit grant"


class AdminUserItem(BaseModel):
    id: str
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    role: str
    credits: int
    free_credits_claimed: bool = False
    created_at: str
    last_login_at: str


class AdminPendingCreditItem(BaseModel):
    id: str
    email: str
    credits: int
    status: str
    created_at: str


class AdminTransactionItem(BaseModel):
    id: str
    user_email: str
    amount: int
    balance_after: int
    action: str
    description: Optional[str]
    created_at: str


@router.post("/credits/assign")
async def assign_credits_to_email(
    body: AssignCreditRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assigns credits to any email address.
    If the user already exists, balance is incremented immediately.
    If the user has not signed up yet, creates a pending grant that automatically
    activates when the user logs in with Google.
    """
    if body.credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credit amount must be greater than zero.",
        )

    clean_email = body.email.strip().lower()

    # 1. Check if user already exists
    stmt = (
        select(User)
        .options(selectinload(User.credit))
        .where(func.lower(User.email) == clean_email)
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if user:
        # Existing user: credit directly
        if not user.credit:
            user.credit = UserCredit(user_id=user.id, balance=0)
            db.add(user.credit)
            await db.flush()

        user.credit.balance += body.credits

        tx = CreditTransaction(
            user_id=user.id,
            amount=body.credits,
            balance_after=user.credit.balance,
            action="admin_grant",
            description=body.description or f"Added by admin ({admin_user.email})",
            meta_data={"granted_by_admin": admin_user.email},
        )
        db.add(tx)
        await db.commit()

        return {
            "status": "credited_directly",
            "message": f"Successfully credited {body.credits} credits to {clean_email}.",
            "email": clean_email,
            "new_balance": user.credit.balance,
        }

    else:
        # User not signed up yet: queue in pending_credits
        pending = PendingCredit(
            email=clean_email,
            credits=body.credits,
            status="pending",
            granted_by_user_id=admin_user.id,
        )
        db.add(pending)
        await db.commit()

        return {
            "status": "pending_signup",
            "message": (
                f"{body.credits} trial credits reserved for {clean_email}. "
                f"They will automatically receive the credits upon their first Google sign-in."
            ),
            "email": clean_email,
            "credits": body.credits,
        }


@router.get("/users")
async def list_users(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists all registered users and their current credit balances."""
    stmt = (
        select(User)
        .options(selectinload(User.credit))
        .order_by(desc(User.created_at))
        .limit(200)
    )
    res = await db.execute(stmt)
    users = res.scalars().all()

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.name or u.email.split("@")[0],
            "avatar_url": u.avatar_url,
            "role": u.role,
            "credits": u.credit.balance if u.credit else 0,
            "free_credits_claimed": bool(u.free_credits_claimed),
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else "",
        }
        for u in users
    ]


@router.get("/pending-credits")
async def list_pending_credits(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists all pending invitations where credits are reserved waiting for signup."""
    stmt = (
        select(PendingCredit)
        .where(PendingCredit.status == "pending")
        .order_by(desc(PendingCredit.created_at))
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    return [
        {
            "id": str(p.id),
            "email": p.email,
            "credits": p.credits,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }
        for p in items
    ]


@router.get("/transactions")
async def list_recent_transactions(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns recent credit transactions across all users for auditing."""
    stmt = (
        select(CreditTransaction, User.email)
        .join(User, CreditTransaction.user_id == User.id)
        .order_by(desc(CreditTransaction.created_at))
        .limit(100)
    )
    res = await db.execute(stmt)
    rows = res.all()

    return [
        {
            "id": str(tx.id),
            "user_email": email,
            "amount": tx.amount,
            "balance_after": tx.balance_after,
            "action": tx.action,
            "description": tx.description,
            "created_at": tx.created_at.isoformat() if tx.created_at else "",
        }
        for tx, email in rows
    ]


@router.get("/themes")
async def list_admin_themes(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists all theme presets (both active and inactive) for admin management."""
    stmt = select(ThemePreset).order_by(ThemePreset.order_index, ThemePreset.created_at)
    res = await db.execute(stmt)
    presets = res.scalars().all()

    return [
        {
            "id": p.id,
            "title": p.title,
            "category": p.category,
            "tagline": p.tagline,
            "prompt_template": p.prompt_template,
            "hashtags": p.hashtags or [],
            "preview_image_url": p.preview_image_url,
            "is_active": p.is_active,
            "order_index": p.order_index,
            "created_at": p.created_at.isoformat() if p.created_at else "",
            "updated_at": p.updated_at.isoformat() if p.updated_at else "",
        }
        for p in presets
    ]


@router.post("/themes")
async def create_theme(
    body: ThemeCreateRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new prompt theme preset."""
    if not body.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Theme title is required.",
        )
    if not body.prompt_template.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt template is required.",
        )

    # Determine unique theme ID / slug
    raw_id = slugify(body.id.strip()) if body.id and body.id.strip() else slugify(body.title.strip())
    if not raw_id:
        raw_id = uuid.uuid4().hex[:8]
    if not raw_id.startswith("trend-"):
        raw_id = f"trend-{raw_id}"
    raw_slug = raw_id[:100]

    # Check for slug collision
    stmt = select(ThemePreset).where(ThemePreset.id == raw_slug)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        if body.id and body.id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A theme with ID '{raw_slug}' already exists. Please choose a unique ID.",
            )
        suffix = f"-{uuid.uuid4().hex[:6]}"
        raw_slug = f"{raw_slug[: 100 - len(suffix)]}{suffix}"

    preset = ThemePreset(
        id=raw_slug,
        title=body.title.strip(),
        category=body.category.strip() if body.category else "General",
        tagline=body.tagline.strip() if body.tagline else "",
        prompt_template=body.prompt_template.strip(),
        hashtags=[h.strip() for h in (body.hashtags or []) if h.strip()],
        preview_image_url=body.preview_image_url.strip() if body.preview_image_url else None,
        is_active=body.is_active,
        order_index=body.order_index,
    )
    db.add(preset)
    await db.commit()
    await db.refresh(preset)

    return {
        "status": "created",
        "message": f"Theme '{preset.title}' created successfully.",
        "theme": {
            "id": preset.id,
            "title": preset.title,
            "category": preset.category,
            "tagline": preset.tagline,
            "prompt_template": preset.prompt_template,
            "hashtags": preset.hashtags or [],
            "preview_image_url": preset.preview_image_url,
            "is_active": preset.is_active,
            "order_index": preset.order_index,
            "created_at": preset.created_at.isoformat() if preset.created_at else "",
            "updated_at": preset.updated_at.isoformat() if preset.updated_at else "",
        },
    }


@router.put("/themes/{theme_id}")
async def update_theme(
    theme_id: str,
    body: ThemeUpdateRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Updates an existing theme preset."""
    stmt = select(ThemePreset).where(ThemePreset.id == theme_id)
    res = await db.execute(stmt)
    preset = res.scalar_one_or_none()
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Theme preset '{theme_id}' not found.",
        )

    fields_set = body.model_fields_set

    if "title" in fields_set and body.title is not None:
        clean_title = body.title.strip()
        if not clean_title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Theme title cannot be empty.",
            )
        preset.title = clean_title

    if "category" in fields_set and body.category is not None:
        preset.category = body.category.strip()
    if "tagline" in fields_set and body.tagline is not None:
        preset.tagline = body.tagline.strip()
    if "prompt_template" in fields_set and body.prompt_template is not None:
        clean_prompt = body.prompt_template.strip()
        if not clean_prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt template cannot be empty.",
            )
        preset.prompt_template = clean_prompt
    if "hashtags" in fields_set and body.hashtags is not None:
        preset.hashtags = [h.strip() for h in body.hashtags if h.strip()]
    if "preview_image_url" in fields_set:
        preset.preview_image_url = body.preview_image_url.strip() if (body.preview_image_url and body.preview_image_url.strip()) else None
    if "is_active" in fields_set and body.is_active is not None:
        preset.is_active = body.is_active
    if "order_index" in fields_set and body.order_index is not None:
        preset.order_index = body.order_index

    await db.commit()
    await db.refresh(preset)

    return {
        "status": "updated",
        "message": f"Theme '{preset.title}' updated successfully.",
        "theme": {
            "id": preset.id,
            "title": preset.title,
            "category": preset.category,
            "tagline": preset.tagline,
            "prompt_template": preset.prompt_template,
            "hashtags": preset.hashtags or [],
            "preview_image_url": preset.preview_image_url,
            "is_active": preset.is_active,
            "order_index": preset.order_index,
            "created_at": preset.created_at.isoformat() if preset.created_at else "",
            "updated_at": preset.updated_at.isoformat() if preset.updated_at else "",
        },
    }


@router.delete("/themes/{theme_id}")
async def delete_theme(
    theme_id: str,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a theme preset."""
    stmt = select(ThemePreset).where(ThemePreset.id == theme_id)
    res = await db.execute(stmt)
    preset = res.scalar_one_or_none()
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Theme preset '{theme_id}' not found.",
        )

    theme_title = preset.title
    await db.delete(preset)
    await db.commit()

    return {
        "status": "deleted",
        "message": f"Theme '{theme_title}' has been deleted.",
        "id": theme_id,
    }

