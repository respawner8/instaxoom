import ssl
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

logger = logging.getLogger("app.db")
Base = declarative_base()

# Determine SSL requirements: Neon and cloud Postgres require SSL
connect_args = {}
db_url = settings.async_database_url

if "neon.tech" in db_url or "sslmode=require" in db_url or "azure.com" in db_url:
    # Remove sslmode query param if present because asyncpg uses ssl context in connect_args
    if "?sslmode=" in db_url:
        db_url = db_url.split("?sslmode=")[0]
    elif "&sslmode=" in db_url:
        db_url = db_url.split("&sslmode=")[0]

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ctx

engine = create_async_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session for FastAPI endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initializes tables on startup if they don't already exist."""
    async with engine.begin() as conn:
        # Import models so Base has all definitions
        import app.models.user  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
        # Migrate existing tables: add thumbnail_url and free credits columns if missing
        from sqlalchemy import text
        for query in [
            "ALTER TABLE generations ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS free_credits_claimed BOOLEAN NOT NULL DEFAULT FALSE;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS free_credits_claimed_at TIMESTAMPTZ;",
            "CREATE INDEX IF NOT EXISTS ix_site_visits_created_at ON site_visits (created_at);",
            "CREATE INDEX IF NOT EXISTS ix_site_visits_visitor_id ON site_visits (visitor_id);",
        ]:
            try:
                await conn.execute(text(query))
            except Exception as e:
                logger.warning("Schema migration notice (%s): %s", query, e)

    # Seed default themes if theme_presets table is empty
    try:
        from app.models.user import ThemePreset
        from sqlalchemy import select, func
        async with AsyncSessionLocal() as session:
            count_stmt = select(func.count()).select_from(ThemePreset)
            res = await session.execute(count_stmt)
            count = res.scalar() or 0
            if count == 0:
                from app.api.trends import THEMES
                for idx, t in enumerate(THEMES):
                    preset = ThemePreset(
                        id=t["id"],
                        title=t["title"],
                        category=t.get("category", "General"),
                        tagline=t.get("tagline", ""),
                        prompt_template=t["prompt_template"],
                        hashtags=t.get("hashtags", []),
                        preview_image_url=t.get("preview_image_url"),
                        is_active=True,
                        order_index=idx,
                    )
                    session.add(preset)
                await session.commit()
                logger.info("Successfully seeded %d default theme presets.", len(THEMES))
    except Exception as e:
        logger.warning("Default theme seeding notice: %s", e)

