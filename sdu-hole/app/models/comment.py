from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    parent_id = Column(Integer, ForeignKey("comments.id"), index=True, nullable=True)
    anon_name = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    like_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
