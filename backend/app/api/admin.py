from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User, UserCredit, PendingCredit, CreditTransaction
from app.api.deps import get_admin_user

router = APIRouter(prefix="/api/admin", tags=["Admin Portal"])


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
