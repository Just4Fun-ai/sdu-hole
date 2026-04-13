from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import os
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.report import Report
from app.models.moderation_log import ModerationLog
from app.models.uploaded_image import UploadedImage
from app.models.appeal import Appeal
from app.utils.security import get_current_user, ensure_admin
from app.schemas.auth import AppealResolveRequest
from app.services.moderation import log_moderation_hit

router = APIRouter(prefix="/api/admin", tags=["管理"])


class AdminActionPayload(BaseModel):
    reason: str = ""


class ReportResolvePayload(BaseModel):
    action: str = "ignore"  # ignore | warn_author | delete_post | delete_comment | ban_author
    reason: str = ""        # 管理员内部备注
    feedback: str = ""      # 给举报者的处理反馈


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


@router.post("/reports/{report_id}/resolve", summary="处理举报（管理员）")
async def resolve_report(
    report_id: int,
    payload: ReportResolvePayload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    action = (payload.action or "ignore").strip().lower()
    reason = (payload.reason or "").strip()
    feedback = (payload.feedback or "").strip()

    if action not in {"ignore", "warn_author", "delete_post", "delete_comment", "ban_author"}:
        raise HTTPException(status_code=400, detail="不支持的处理动作")
    if not feedback:
        raise HTTPException(status_code=400, detail="请填写给举报者的反馈")

    report_result = await db.execute(select(Report).where(Report.id == report_id))
    report = report_result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="举报记录不存在")

    target_user_id: int | None = None
    target_desc = f"{report.target_type}:{report.target_id}"
    action_label = "已处理"

    if report.target_type == "post":
        post_result = await db.execute(select(Post).where(Post.id == report.target_id))
        post = post_result.scalar_one_or_none()
        if not post:
            raise HTTPException(status_code=404, detail="被举报帖子不存在")
        target_user_id = post.user_id

        if action == "warn_author":
            action_label = "已警告作者"
            await log_moderation_hit(
                db,
                user_id=target_user_id,
                scene="admin_warn_user",
                content=f"post:{post.id}",
                reason=reason or "管理员已警告，请注意文明发言",
            )
        elif action == "delete_post":
            action_label = "已删除帖子"
            post.is_deleted = True
            img_result = await db.execute(select(UploadedImage).where(UploadedImage.post_id == post.id))
            for img in img_result.scalars().all():
                try:
                    if img.file_path and os.path.exists(img.file_path):
                        os.remove(img.file_path)
                except Exception:
                    pass
                await db.delete(img)
            await log_moderation_hit(
                db,
                user_id=target_user_id,
                scene="admin_delete_post",
                content=f"post:{post.id}",
                reason=reason or "管理员删除帖子",
            )
        elif action == "ban_author":
            user_result = await db.execute(select(User).where(User.id == post.user_id))
            target = user_result.scalar_one_or_none()
            if not target:
                raise HTTPException(status_code=404, detail="作者不存在")
            if target.is_admin:
                raise HTTPException(status_code=400, detail="管理员账号不可禁言")
            target.is_banned = True
            action_label = "已禁言作者"
            await log_moderation_hit(
                db,
                user_id=target.id,
                scene="admin_ban_user",
                content=f"user:{target.id} by_post:{post.id}",
                reason=reason or "管理员禁言账号",
            )
        elif action == "delete_comment":
            raise HTTPException(status_code=400, detail="帖子举报不支持“删评论”动作")
        else:
            action_label = "已处理（未处罚）"

    elif report.target_type == "comment":
        comment_result = await db.execute(select(Comment).where(Comment.id == report.target_id))
        comment = comment_result.scalar_one_or_none()
        if not comment:
            raise HTTPException(status_code=404, detail="被举报评论不存在")
        target_user_id = comment.user_id

        if action == "warn_author":
            action_label = "已警告作者"
            await log_moderation_hit(
                db,
                user_id=target_user_id,
                scene="admin_warn_user",
                content=f"comment:{comment.id}",
                reason=reason or "管理员已警告，请注意文明发言",
            )
        elif action == "delete_comment":
            action_label = "已删除评论"
            comment.is_deleted = True
            await log_moderation_hit(
                db,
                user_id=target_user_id,
                scene="admin_delete_comment",
                content=f"comment:{comment.id}",
                reason=reason or "管理员删除评论",
            )
        elif action == "ban_author":
            user_result = await db.execute(select(User).where(User.id == comment.user_id))
            target = user_result.scalar_one_or_none()
            if not target:
                raise HTTPException(status_code=404, detail="作者不存在")
            if target.is_admin:
                raise HTTPException(status_code=400, detail="管理员账号不可禁言")
            target.is_banned = True
            action_label = "已禁言作者"
            await log_moderation_hit(
                db,
                user_id=target.id,
                scene="admin_ban_user",
                content=f"user:{target.id} by_comment:{comment.id}",
                reason=reason or "管理员禁言账号",
            )
        elif action == "delete_post":
            raise HTTPException(status_code=400, detail="评论举报不支持“删帖”动作")
        else:
            action_label = "已处理（未处罚）"
    else:
        raise HTTPException(status_code=400, detail="不支持的举报对象类型")

    reporter_feedback = f"{action_label}：{feedback}"
    await log_moderation_hit(
        db,
        user_id=report.user_id,
        scene="admin_report_result",
        content=f"report:{report.id} target:{target_desc}",
        reason=reporter_feedback,
    )

    await db.delete(report)
    return {
        "message": "举报已处理并反馈举报人",
        "id": report.id,
        "action": action,
        "action_label": action_label,
        "target_type": report.target_type,
        "target_id": report.target_id,
        "target_user_id": target_user_id,
    }


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
    payload: AdminActionPayload | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    reason = (payload.reason if payload else "").strip()
    post.is_deleted = True
    img_result = await db.execute(select(UploadedImage).where(UploadedImage.post_id == post_id))
    for img in img_result.scalars().all():
        try:
            if img.file_path and os.path.exists(img.file_path):
                os.remove(img.file_path)
        except Exception:
            pass
        await db.delete(img)
    await log_moderation_hit(
        db,
        user_id=post.user_id,
        scene="admin_delete_post",
        content=f"post:{post.id}",
        reason=reason or "管理员删除帖子",
    )
    return {"message": "帖子已删除"}


@router.post("/posts/{post_id}/ban-author", summary="禁言帖子作者（管理员）")
async def ban_post_author(
    post_id: int,
    payload: AdminActionPayload | None = None,
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

    reason = (payload.reason if payload else "").strip()
    target.is_banned = True
    await log_moderation_hit(
        db,
        user_id=target.id,
        scene="admin_ban_user",
        content=f"user:{target.id} by_post:{post.id}",
        reason=reason or "管理员禁言账号",
    )
    return {"message": "已禁言该帖子作者", "user_id": target.id}


@router.delete("/comments/{comment_id}", summary="管理员删除评论")
async def admin_delete_comment(
    comment_id: int,
    payload: AdminActionPayload | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(select(Comment).where(Comment.id == comment_id, Comment.is_deleted == False))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    ids_to_delete = [comment.id]
    if comment.parent_id is None:
        child_result = await db.execute(
            select(Comment.id).where(
                Comment.parent_id == comment.id,
                Comment.is_deleted == False,
            )
        )
        ids_to_delete.extend(child_result.scalars().all())

    reason = (payload.reason if payload else "").strip()
    await db.execute(
        Comment.__table__.update()
        .where(Comment.id.in_(ids_to_delete))
        .values(is_deleted=True)
    )
    post_result = await db.execute(select(Post).where(Post.id == comment.post_id))
    post = post_result.scalar_one_or_none()
    if post:
        post.comment_count = max(0, int(post.comment_count or 0) - len(ids_to_delete))
    await log_moderation_hit(
        db,
        user_id=comment.user_id,
        scene="admin_delete_comment",
        content=f"comment:{comment.id}",
        reason=reason or "管理员删除评论",
    )
    return {"message": "评论已删除", "deleted_count": len(ids_to_delete)}


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
    payload: AdminActionPayload | None = None,
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
    reason = (payload.reason if payload else "").strip()
    target.is_banned = True
    await log_moderation_hit(
        db,
        user_id=target.id,
        scene="admin_ban_user",
        content=f"user:{target.id}",
        reason=reason or "管理员禁言账号",
    )
    return {"message": "已禁言", "user_id": user_id}


@router.post("/users/{user_id}/unban", summary="解除禁言（管理员）")
async def unban_user(
    user_id: int,
    payload: AdminActionPayload | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    reason = (payload.reason if payload else "").strip()
    target.is_banned = False
    await log_moderation_hit(
        db,
        user_id=target.id,
        scene="admin_unban_user",
        content=f"user:{target.id}",
        reason=reason or "管理员解除禁言",
    )
    return {"message": "已解除禁言", "user_id": user_id}


@router.get("/appeals", summary="查看申诉列表（管理员）")
async def list_appeals(
    status: str = Query("all", description="all/pending/approved/rejected"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    query = select(Appeal).order_by(desc(Appeal.created_at))
    if status in ("pending", "approved", "rejected"):
        query = query.where(Appeal.status == status)
    query = query.offset((page - 1) * size).limit(size)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "moderation_log_id": a.moderation_log_id,
            "content": a.content,
            "status": a.status,
            "admin_reply": a.admin_reply or "",
            "resolved_by": a.resolved_by,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        }
        for a in rows
    ]


@router.post("/appeals/{appeal_id}/resolve", summary="处理申诉（管理员）")
async def resolve_appeal(
    appeal_id: int,
    req: AppealResolveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_admin(user)
    result = await db.execute(select(Appeal).where(Appeal.id == appeal_id))
    appeal = result.scalar_one_or_none()
    if not appeal:
        raise HTTPException(status_code=404, detail="申诉不存在")
    status = (req.status or "").strip().lower()
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态仅支持 approved/rejected")
    appeal.status = status
    appeal.admin_reply = (req.admin_reply or "").strip()
    appeal.resolved_by = user.id
    return {"message": "申诉已处理", "id": appeal.id, "status": appeal.status}
