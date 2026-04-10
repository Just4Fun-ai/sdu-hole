from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class Appeal(Base):
    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    moderation_log_id = Column(Integer, ForeignKey("moderation_logs.id"), index=True, nullable=False)
    content = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="pending")  # pending/approved/rejected
    admin_reply = Column(Text, default="")
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
