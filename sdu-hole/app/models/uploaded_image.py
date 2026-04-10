from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class UploadedImage(Base):
    __tablename__ = "uploaded_images"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), index=True, nullable=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(32), default="image/webp")
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
