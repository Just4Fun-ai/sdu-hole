from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    anon_name = Column(String(32), nullable=False)   # 匿名昵称
    content = Column(Text, nullable=False)
    tag = Column(String(20), index=True)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
