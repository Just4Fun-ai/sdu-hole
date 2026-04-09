from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    target_type = Column(String(10), nullable=False)  # "post" or "comment"
    target_id = Column(Integer, nullable=False)
    reason = Column(String(200), default="")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_user_report"),
    )
