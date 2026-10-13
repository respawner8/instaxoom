import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    google_sub = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    avatar_url = Column(Text, nullable=True)
    role = Column(String(32), default="user", nullable=False)  # "user" | "admin"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 1-to-1 relationship with credit balance
    credit = relationship("UserCredit", back_populates="user", uselist=False, cascade="all, delete-orphan")
    # 1-to-many relationship with transactions
    transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")
    # 1-to-many relationship with generated portraits
    generations = relationship("Generation", back_populates="user", cascade="all, delete-orphan", order_by="desc(Generation.created_at)")


class UserCredit(Base):
    __tablename__ = "user_credits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    balance = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="credit")


class PendingCredit(Base):
    __tablename__ = "pending_credits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), index=True, nullable=False)
    credits = Column(Integer, default=5, nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # "pending" | "claimed"
    granted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    amount = Column(Integer, nullable=False)  # e.g. +5, -1
    balance_after = Column(Integer, nullable=False)
    action = Column(String(32), nullable=False)  # "admin_grant" | "generation" | "purchase" | "refund"
    description = Column(Text, nullable=True)
    meta_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="transactions")


class Generation(Base):
    __tablename__ = "generations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    theme_id = Column(String(100), index=True, nullable=False)
    theme_title = Column(String(255), nullable=True)
    prompt = Column(Text, nullable=True)
    aspect_ratio = Column(String(16), default="4:5", nullable=False)
    engine = Column(String(32), default="azure", nullable=False)
    image_url = Column(Text, nullable=False)
    storage_provider = Column(String(32), default="azure_blob", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)

    user = relationship("User", back_populates="generations")

