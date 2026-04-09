from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    student_id_hash = Column(String(64), unique=True, index=True)  # SHA256哈希，不存明文
    email = Column(String(100), unique=True, index=True)
    nickname = Column(String(10), unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, server_default=func.now(), onupdate=func.now())
