from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.report import Report
from app.utils.security import get_current_user, ensure_admin

router = APIRouter(prefix="/api/admin", tags=["管理"])


@router.get("/reports", summary="查看举报列表（管理员）")
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)

    result = await db.execute(
        select(Report)
        .order_by(desc(Report.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    reports = result.scalars().all()

    return [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason": r.reason,
            "report_user_id": r.user_id,
            "created_at": r.created_at,
        }
        for r in reports
    ]


@router.delete("/posts/{post_id}", summary="管理员删除帖子")
async def admin_delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.is_deleted = True
    return {"message": "帖子已删除"}


@router.delete("/comments/{comment_id}", summary="管理员删除评论")
async def admin_delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    comment.is_deleted = True
    return {"message": "评论已删除"}

