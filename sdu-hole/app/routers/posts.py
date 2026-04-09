from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.like import Like
from app.schemas.post import PostCreate, PostResponse, CommentCreate, CommentResponse
from app.utils.security import get_current_user
from app.utils.anonymous import generate_post_anon_name, generate_anon_name
from app.services.filter import check_content

router = APIRouter(prefix="/api/posts", tags=["帖子"])

VALID_TAGS = ["课程评价", "老师评价", "校园活动", "生活吐槽", "求助", "表白墙", "二手交易", "考研交流"]


@router.get("/", summary="获取帖子列表")
async def list_posts(
    tag: Optional[str] = Query(None, description="按标签筛选"),
    order: str = Query("new", description="排序: new=最新, hot=最热"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Post).where(Post.is_deleted == False)

    if tag and tag in VALID_TAGS:
        query = query.where(Post.tag == tag)

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

    return [
        PostResponse(
            id=p.id,
            anon_name=p.anon_name,
            content=p.content,
            tag=p.tag,
            like_count=p.like_count,
            comment_count=p.comment_count,
            created_at=p.created_at,
            is_liked=p.id in liked_ids,
        )
        for p in posts
    ]


@router.post("/", response_model=PostResponse, summary="发表帖子")
async def create_post(
    req: PostCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 校验标签
    if req.tag not in VALID_TAGS:
        raise HTTPException(400, f"无效标签，可选: {', '.join(VALID_TAGS)}")

    # 内容检查
    content = req.content.strip()
    if len(content) < 2:
        raise HTTPException(400, "内容太短了，至少2个字")
    if len(content) > 2000:
        raise HTTPException(400, "内容不能超过2000字")

    ok, msg = check_content(content)
    if not ok:
        raise HTTPException(400, msg)

    post = Post(
        user_id=user.id,
        anon_name=generate_post_anon_name(user.id),
        content=content,
        tag=req.tag,
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)

    return PostResponse(
        id=post.id,
        anon_name=post.anon_name,
        content=post.content,
        tag=post.tag,
        like_count=0,
        comment_count=0,
        created_at=post.created_at,
        is_liked=False,
    )


@router.get("/{post_id}", response_model=PostResponse, summary="帖子详情")
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "帖子不存在")

    # 点赞状态
    liked = await db.execute(
        select(Like).where(Like.user_id == user.id, Like.target_type == "post", Like.target_id == post_id)
    )
    is_liked = liked.scalar_one_or_none() is not None

    return PostResponse(
        id=post.id, anon_name=post.anon_name, content=post.content,
        tag=post.tag, like_count=post.like_count, comment_count=post.comment_count,
        created_at=post.created_at, is_liked=is_liked,
    )


@router.post("/{post_id}/like", summary="点赞/取消点赞")
async def toggle_like(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
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


@router.delete("/{post_id}", summary="删除自己的帖子")
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
            id=c.id, post_id=c.post_id, anon_name=c.anon_name,
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
    # 检查帖子
    post_result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "帖子不存在")

    content = req.content.strip()
    if len(content) < 1 or len(content) > 500:
        raise HTTPException(400, "评论长度需在1-500字之间")

    ok, msg = check_content(content)
    if not ok:
        raise HTTPException(400, msg)

    comment = Comment(
        post_id=post_id,
        user_id=user.id,
        anon_name=generate_anon_name(user.id, post_id),
        content=content,
    )
    db.add(comment)
    post.comment_count += 1
    await db.flush()
    await db.refresh(comment)

    return CommentResponse(
        id=comment.id, post_id=comment.post_id, anon_name=comment.anon_name,
        content=comment.content, like_count=0, created_at=comment.created_at,
        is_liked=False,
    )
