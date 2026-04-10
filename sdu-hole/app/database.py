from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import inspect, text

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI 依赖注入：获取数据库 session"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_user_nickname_column)
        await conn.run_sync(_migrate_user_is_admin_column)
        await conn.run_sync(_migrate_comment_parent_id_column)


def _migrate_user_nickname_column(sync_conn):
    """
    轻量迁移：确保 users.nickname 列存在（兼容旧库）。
    """
    inspector = inspect(sync_conn)
    if "users" not in inspector.get_table_names():
        return

    cols = [c["name"] for c in inspector.get_columns("users")]
    if "nickname" not in cols:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(10)"))


def _migrate_user_is_admin_column(sync_conn):
    """
    轻量迁移：确保 users.is_admin 列存在（兼容旧库）。
    """
    inspector = inspect(sync_conn)
    if "users" not in inspector.get_table_names():
        return

    cols = [c["name"] for c in inspector.get_columns("users")]
    if "is_admin" not in cols:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))


def _migrate_comment_parent_id_column(sync_conn):
    """
    轻量迁移：确保 comments.parent_id 列存在（兼容旧库）。
    """
    inspector = inspect(sync_conn)
    if "comments" not in inspector.get_table_names():
        return

    cols = [c["name"] for c in inspector.get_columns("comments")]
    if "parent_id" not in cols:
        sync_conn.execute(text("ALTER TABLE comments ADD COLUMN parent_id INTEGER"))
