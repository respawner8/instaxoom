from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import verify_google_id_token, create_access_token
from app.core.app_metrics import user_logins, user_login_failures
from app.models.user import User, UserCredit, PendingCredit, CreditTransaction
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class GoogleAuthRequest(BaseModel):
    credential: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    credits: int


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/google", response_model=AuthResponse)
async def login_with_google(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Verifies Google ID token, logs in or registers user in PostgreSQL,
    claims any pending admin-granted credits, and issues an App JWT token.
    """
    try:
        google_data = verify_google_id_token(body.credential)
    except Exception as e:
        user_login_failures.add(1, {"provider": "google", "reason": "token_verification_failed"})
        raise

    email = google_data["email"].strip().lower()
    sub = google_data["sub"]

    # 1. Check if user already exists
    stmt = (
        select(User)
        .options(selectinload(User.credit))
        .where((User.email == email) | (User.google_sub == sub))
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    is_admin = email in settings.admin_emails_list

    if not user:
        # Create brand-new user record
        user = User(
            email=email,
            google_sub=sub,
            name=google_data.get("name"),
            avatar_url=google_data.get("picture"),
            role="admin" if is_admin else "user",
        )
        db.add(user)
        await db.flush()  # flush to generate user.id

        # Initialize credit balance (default 0)
        credit = UserCredit(user_id=user.id, balance=0)
        db.add(credit)
        await db.flush()

        # Check for any pending credits assigned by admin before signup
        p_stmt = select(PendingCredit).where(
            func.lower(PendingCredit.email) == email,
            PendingCredit.status == "pending",
        )
        p_res = await db.execute(p_stmt)
        pending_grants = p_res.scalars().all()

        for grant in pending_grants:
            credit.balance += grant.credits
            grant.status = "claimed"
            grant.claimed_at = datetime.now(timezone.utc)

            # Log audit transaction
            tx = CreditTransaction(
                user_id=user.id,
                amount=grant.credits,
                balance_after=credit.balance,
                action="admin_grant",
                description=f"Claimed pending credit grant ({grant.credits} credits)",
                meta_data={"pending_grant_id": str(grant.id)},
            )
            db.add(tx)

        await db.commit()
        await db.refresh(user)
        await db.refresh(credit)
        user.credit = credit

    else:
        # Update existing user profile
        user.last_login_at = datetime.now(timezone.utc)
        if google_data.get("name"):
            user.name = google_data["name"]
        if google_data.get("picture"):
            user.avatar_url = google_data["picture"]
        if is_admin and user.role != "admin":
            user.role = "admin"

        if not user.credit:
            user.credit = UserCredit(user_id=user.id, balance=0)
            db.add(user.credit)
            await db.flush()

        # Check if new pending credits were added while user was offline
        p_stmt = select(PendingCredit).where(
            func.lower(PendingCredit.email) == email,
            PendingCredit.status == "pending",
        )
        p_res = await db.execute(p_stmt)
        pending_grants = p_res.scalars().all()

        for grant in pending_grants:
            user.credit.balance += grant.credits
            grant.status = "claimed"
            grant.claimed_at = datetime.now(timezone.utc)

            tx = CreditTransaction(
                user_id=user.id,
                amount=grant.credits,
                balance_after=user.credit.balance,
                action="admin_grant",
                description=f"Claimed pending credit grant ({grant.credits} credits)",
                meta_data={"pending_grant_id": str(grant.id)},
            )
            db.add(tx)

        await db.commit()
        await db.refresh(user)

    # Record successful login metric
    user_logins.add(1, {"provider": "google", "role": user.role})

    # Issue JWT token
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
    })

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            role=user.role,
            credits=user.credit.balance if user.credit else 0,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile and current credit balance."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        role=current_user.role,
        credits=current_user.credit.balance if current_user.credit else 0,
    )
