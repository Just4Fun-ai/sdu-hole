from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.like import Like
from app.models.favorite import Favorite
from app.models.report import Report
from app.schemas.post import PostCreate, PostResponse, CommentCreate, CommentResponse, ReportCreate
from app.utils.security import get_current_user
from app.services.filter import check_content
from app.services.moderation import log_moderation_hit

router = APIRouter(prefix="/api/posts", tags=["帖子"])

VALID_TAGS = [
    "课程评价", "校园活动", "美食推荐", "游玩推荐",
    "生活吐槽", "求助", "表白墙", "二手交易", "考研交流", "失物招领",
]


def normalize_display_name(name: str | None, fallback: str) -> str:
    display = (name or "").strip() or fallback
    if display.startswith("匿名") and len(display) > 2:
        display = display[2:]
    return display


def ensure_nickname_bound(user: User):
    if not (user.nickname or "").strip():
        raise HTTPException(status_code=403, detail="请先完成匿名昵称绑定")


@router.get("/", summary="获取帖子列表")
async def list_posts(
    tag: Optional[str] = Query(None, description="按标签筛选"),
    order: str = Query("new", description="排序: new=最新, hot=最热"),
    mine: bool = Query(False, description="仅看我的帖子"),
    favorited: bool = Query(False, description="仅看收藏"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    query = select(Post).where(Post.is_deleted == False)

    if tag:
        query = query.where(Post.tag == tag)
    if mine:
        query = query.where(Post.user_id == user.id)
    if favorited:
        query = query.join(Favorite, Favorite.post_id == Post.id).where(Favorite.user_id == user.id)

    if order == "hot":
        query = query.order_by(desc(Post.like_count))
    else:
        query = query.order_by(desc(Post.created_at))

    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    posts = result.scalars().all()

    # 查询当前用户的点赞状态
    post_ids = [p.id for p in posts]
    liked_result = await db.execute(
        select(Like.target_id).where(
            Like.user_id == user.id,
            Like.target_type == "post",
            Like.target_id.in_(post_ids),
        )
    )
    liked_ids = set(liked_result.scalars().all())
    favorited_result = await db.execute(
        select(Favorite.post_id).where(
            Favorite.user_id == user.id,
            Favorite.post_id.in_(post_ids),
        )
    )
    favorited_ids = set(favorited_result.scalars().all())

    return [
        PostResponse(
            id=p.id,
            anon_name=normalize_display_name(p.anon_name, f"同学{p.user_id}"),
            content=p.content,
            tag=p.tag,
            like_count=p.like_count,
            comment_count=p.comment_count,
            created_at=p.created_at,
            is_liked=p.id in liked_ids,
            is_mine=p.user_id == user.id,
            is_favorited=p.id in favorited_ids,
        )
        for p in posts
    ]


@router.post("/", response_model=PostResponse, summary="发表帖子")
async def create_post(
    req: PostCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    # 标签（支持用户自定义）
    tag = req.tag.strip()
    if not tag:
        raise HTTPException(400, "标签不能为空")
    if len(tag) > 20:
        raise HTTPException(400, "标签不能超过20个字")
    tag_ok, tag_msg = check_content(tag)
    if not tag_ok:
        await log_moderation_hit(
            db,
            user_id=user.id,
            scene="tag",
            content=tag,
            reason=tag_msg or "标签命中敏感词",
        )
        raise HTTPException(400, tag_msg)

    # 内容检查
    content = req.content.strip()
    if len(content) < 2:
        raise HTTPException(400, "内容太短了，至少2个字")
    if len(content) > 2000:
        raise HTTPException(400, "内容不能超过2000字")

    ok, msg = check_content(content)
    if not ok:
        await log_moderation_hit(
            db,
            user_id=user.id,
            scene="post_content",
            content=content,
            reason=msg or "帖子命中敏感词",
        )
        raise HTTPException(400, msg)

    post = Post(
        user_id=user.id,
        anon_name=user.nickname or f"同学{user.id}",
        content=content,
        tag=tag,
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)

    return PostResponse(
        id=post.id,
        anon_name=normalize_display_name(post.anon_name, f"同学{post.user_id}"),
        content=post.content,
        tag=post.tag,
        like_count=0,
        comment_count=0,
        created_at=post.created_at,
        is_liked=False,
        is_mine=True,
        is_favorited=False,
    )


@router.get("/{post_id}", response_model=PostResponse, summary="帖子详情")
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "帖子不存在")

    # 点赞状态
    liked = await db.execute(
        select(Like).where(Like.user_id == user.id, Like.target_type == "post", Like.target_id == post_id)
    )
    is_liked = liked.scalar_one_or_none() is not None
    favored = await db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.post_id == post_id)
    )

    return PostResponse(
        id=post.id, anon_name=normalize_display_name(post.anon_name, f"同学{post.user_id}"), content=post.content,
        tag=post.tag, like_count=post.like_count, comment_count=post.comment_count,
        created_at=post.created_at, is_liked=is_liked, is_mine=post.user_id == user.id,
        is_favorited=favored.scalar_one_or_none() is not None,
    )


@router.post("/{post_id}/like", summary="点赞/取消点赞")
async def toggle_like(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    # 检查帖子存在
    post_result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "帖子不存在")

    # 检查是否已点赞
    like_result = await db.execute(
        select(Like).where(Like.user_id == user.id, Like.target_type == "post", Like.target_id == post_id)
    )
    existing = like_result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        post.like_count = max(0, post.like_count - 1)
        return {"liked": False, "like_count": post.like_count}
    else:
        db.add(Like(user_id=user.id, target_type="post", target_id=post_id))
        post.like_count += 1
        return {"liked": True, "like_count": post.like_count}


@router.post("/{post_id}/favorite", summary="收藏/取消收藏")
async def toggle_favorite(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    post_result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "帖子不存在")

    fav_result = await db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.post_id == post_id)
    )
    existing = fav_result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        return {"favorited": False}

    db.add(Favorite(user_id=user.id, post_id=post_id))
    return {"favorited": True}


@router.delete("/{post_id}", summary="删除自己的帖子")
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "帖子不存在")
    if post.user_id != user.id:
        raise HTTPException(403, "只能删除自己的帖子")

    post.is_deleted = True
    return {"message": "已删除"}


# ---- 评论 ----


@router.get("/{post_id}/comments", summary="获取评论列表")
async def list_comments(
    post_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    result = await db.execute(
        select(Comment)
        .where(Comment.post_id == post_id, Comment.is_deleted == False)
        .order_by(Comment.created_at)
        .offset((page - 1) * size)
        .limit(size)
    )
    comments = result.scalars().all()

    comment_ids = [c.id for c in comments]
    liked_result = await db.execute(
        select(Like.target_id).where(
            Like.user_id == user.id,
            Like.target_type == "comment",
            Like.target_id.in_(comment_ids),
        )
    )
    liked_ids = set(liked_result.scalars().all())

    return [
        CommentResponse(
            id=c.id, post_id=c.post_id, parent_id=c.parent_id,
            anon_name=normalize_display_name(c.anon_name, f"同学{c.user_id}"),
            content=c.content, like_count=c.like_count,
            created_at=c.created_at, is_liked=c.id in liked_ids,
        )
        for c in comments
    ]


@router.post("/{post_id}/comments", response_model=CommentResponse, summary="发表评论")
async def create_comment(
    post_id: int,
    req: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    # 检查帖子
    post_result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "帖子不存在")

    parent_id = req.parent_id
    if parent_id is not None:
        parent_result = await db.execute(
            select(Comment).where(
                Comment.id == parent_id,
                Comment.post_id == post_id,
                Comment.is_deleted == False,
            )
        )
        if parent_result.scalar_one_or_none() is None:
            raise HTTPException(400, "回复目标不存在")

    content = req.content.strip()
    if len(content) < 1 or len(content) > 500:
        raise HTTPException(400, "评论长度需在1-500字之间")

    ok, msg = check_content(content)
    if not ok:
        await log_moderation_hit(
            db,
            user_id=user.id,
            scene="comment_content",
            content=content,
            reason=msg or "评论命中敏感词",
        )
        raise HTTPException(400, msg)

    comment = Comment(
        post_id=post_id,
        user_id=user.id,
        parent_id=parent_id,
        anon_name=user.nickname or f"同学{user.id}",
        content=content,
    )
    db.add(comment)
    post.comment_count += 1
    await db.flush()
    await db.refresh(comment)

    return CommentResponse(
        id=comment.id, post_id=comment.post_id, parent_id=comment.parent_id,
        anon_name=normalize_display_name(comment.anon_name, f"同学{comment.user_id}"),
        content=comment.content, like_count=0, created_at=comment.created_at,
        is_liked=False,
    )


@router.post("/comments/{comment_id}/like", summary="点赞/取消点赞评论")
async def toggle_comment_like(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    comment_result = await db.execute(select(Comment).where(Comment.id == comment_id, Comment.is_deleted == False))
    comment = comment_result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "评论不存在")

    like_result = await db.execute(
        select(Like).where(Like.user_id == user.id, Like.target_type == "comment", Like.target_id == comment_id)
    )
    existing = like_result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        comment.like_count = max(0, comment.like_count - 1)
        return {"liked": False, "like_count": comment.like_count}
    else:
        db.add(Like(user_id=user.id, target_type="comment", target_id=comment_id))
        comment.like_count += 1
        return {"liked": True, "like_count": comment.like_count}


@router.post("/{post_id}/report", summary="举报帖子")
async def report_post(
    post_id: int,
    req: ReportCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    post_result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "帖子不存在")

    existing = await db.execute(
        select(Report).where(
            Report.user_id == user.id, Report.target_type == "post", Report.target_id == post_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "你已经举报过该帖子")

    db.add(
        Report(
            user_id=user.id,
            target_type="post",
            target_id=post_id,
            reason=(req.reason or "").strip()[:200],
        )
    )
    return {"message": "举报已提交，我们会尽快处理"}


@router.post("/comments/{comment_id}/report", summary="举报评论")
async def report_comment(
    comment_id: int,
    req: ReportCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_nickname_bound(user)
    comment_result = await db.execute(select(Comment).where(Comment.id == comment_id, Comment.is_deleted == False))
    comment = comment_result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "评论不存在")

    existing = await db.execute(
        select(Report).where(
            Report.user_id == user.id, Report.target_type == "comment", Report.target_id == comment_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "你已经举报过该评论")

    db.add(
        Report(
            user_id=user.id,
            target_type="comment",
            target_id=comment_id,
            reason=(req.reason or "").strip()[:200],
        )
    )
    return {"message": "举报已提交，我们会尽快处理"}
