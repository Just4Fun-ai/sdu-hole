from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.report import Report
from app.models.moderation_log import ModerationLog
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


@router.get("/moderation-hits", summary="查看敏感词命中记录（管理员）")
async def list_moderation_hits(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(
        select(ModerationLog)
        .order_by(desc(ModerationLog.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "scene": r.scene,
            "content_preview": r.content_preview,
            "reason": r.reason,
            "created_at": r.created_at,
        }
        for r in rows
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


@router.post("/posts/{post_id}/ban-author", summary="禁言帖子作者（管理员）")
async def ban_post_author(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    post_result = await db.execute(select(Post).where(Post.id == post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    user_result = await db.execute(select(User).where(User.id == post.user_id))
    target = user_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="作者不存在")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="管理员账号不可禁言")

    target.is_banned = True
    return {"message": "已禁言该帖子作者", "user_id": target.id}


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


@router.get("/users", summary="查询用户（管理员）")
async def list_users(
    keyword: str = Query("", description="按昵称或邮箱模糊搜索"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    query = select(User).order_by(desc(User.id))
    kw = (keyword or "").strip()
    if kw:
        like_kw = f"%{kw}%"
        query = query.where((User.nickname.like(like_kw)) | (User.email.like(like_kw)))
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "nickname": u.nickname,
            "email": u.email,
            "is_admin": bool(u.is_admin),
            "is_banned": bool(u.is_banned),
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/users/{user_id}/ban", summary="禁言用户（管理员）")
async def ban_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="管理员账号不可禁言")
    target.is_banned = True
    return {"message": "已禁言", "user_id": user_id}


@router.post("/users/{user_id}/unban", summary="解除禁言（管理员）")
async def unban_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    target.is_banned = False
    return {"message": "已解除禁言", "user_id": user_id}
