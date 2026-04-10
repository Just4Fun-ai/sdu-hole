from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    scene = Column(String(30), nullable=False)  # post_content/comment_content/nickname/tag
    content_preview = Column(String(200), default="")
    reason = Column(String(200), default="")
    created_at = Column(DateTime, server_default=func.now())

