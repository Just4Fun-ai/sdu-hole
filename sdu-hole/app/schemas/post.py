from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PostCreate(BaseModel):
    content: str
    tag: str


class PostResponse(BaseModel):
    id: int
    anon_name: str
    content: str
    tag: str
    like_count: int
    comment_count: int
    created_at: datetime
    is_liked: bool = False
    is_mine: bool = False
    is_favorited: bool = False

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None


class CommentResponse(BaseModel):
    id: int
    post_id: int
    parent_id: Optional[int] = None
    anon_name: str
    content: str
    like_count: int
    created_at: datetime
    is_liked: bool = False
    is_author: bool = False

    class Config:
        from_attributes = True


class ReportCreate(BaseModel):
    reason: Optional[str] = None
