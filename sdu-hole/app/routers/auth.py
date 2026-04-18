from fastapi import APIRouter, HTTPException, Depends, Request
import random
import time
from datetime import datetime, timedelta

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db
from app.models.user import User
from app.models.appeal import Appeal
from app.models.moderation_log import ModerationLog
from app.models.post import Post
from app.models.comment import Comment
from app.schemas.auth import (
    SendCodeRequest,
    VerifyRequest,
    PasswordLoginRequest,
    SetPasswordRequest,
    TokenResponse,
    RandomNicknameResponse,
    BindNicknameRequest,
    UserProfileResponse,
    AppealCreateRequest,
)
from app.services.email import create_and_send_code, verify_code
from app.utils.security import (
    hash_student_id,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
    build_client_fingerprint,
    _extract_client_ip as extract_client_ip,
)
from app.utils.nickname import validate_nickname, generate_random_nickname
from app.services.filter import check_content
from app.services.moderation import log_moderation_hit
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["认证"])


# 轻量防刷缓存（单进程内存版）
_send_ip_hits: dict[str, list[float]] = {}
_send_sid_hits: dict[str, list[float]] = {}
_verify_fail_hits: dict[str, list[float]] = {}
_verify_block_until: dict[str, float] = {}
_password_fail_hits: dict[str, list[float]] = {}
_password_block_until: dict[str, float] = {}

_COMMON_WEAK_PASSWORDS = {
    "123456",
    "12345678",
    "123456789",
    "123123",
    "111111",
    "000000",
    "password",
    "qwerty",
    "abc123",
    "admin",
    "iloveyou",
}


def _prune_hits(store: dict[str, list[float]], key: str, window_seconds: int, now: float):
    hits = store.get(key, [])
    if not hits:
        return []
    kept = [ts for ts in hits if now - ts <= window_seconds]
    if kept:
        store[key] = kept
    else:
        store.pop(key, None)
    return kept


def _validate_password_policy(password: str):
    if password is None:
        raise HTTPException(status_code=400, detail="密码不能为空")
    if len(password) < 6 or len(password) > 32:
        raise HTTPException(status_code=400, detail="密码长度需为 6-32 位")
    if any(ch.isspace() for ch in password):
        raise HTTPException(status_code=400, detail="密码不能包含空白字符")
    if password.lower() in _COMMON_WEAK_PASSWORDS:
        raise HTTPException(status_code=400, detail="密码过于简单，请更换更安全的密码")


def _validate_student_id_format(sid: str):
    """
    学号规则：
    - 研究生：9 位数字，前 4 位为年份（例 2025xxxxx）
    - 本科生：12 位数字，前 4 位为年份（例 2021xxxxxxxx）
    """
    if not sid.isdigit():
        raise HTTPException(status_code=400, detail="学号格式错误：仅支持数字")
    if len(sid) not in (9, 12):
        raise HTTPException(status_code=400, detail="学号格式错误：仅支持 9 位（研究生）或 12 位（本科生）")
    year = int(sid[:4])
    now_year = datetime.now().year
    if year < 2000 or year > now_year + 1:
        raise HTTPException(status_code=400, detail="学号格式错误：年份部分不合法")


@router.get("/random-nickname", response_model=RandomNicknameResponse, summary="生成随机匿名昵称")
async def random_nickname(db: AsyncSession = Depends(get_db)):
    for _ in range(30):
        name = generate_random_nickname()
        existing = await db.execute(select(User.id).where(User.nickname == name))
        if existing.scalar_one_or_none() is None:
            return RandomNicknameResponse(nickname=name)
    return RandomNicknameResponse(nickname=f"同学{random.randint(1000, 9999)}")


@router.post("/send-code", summary="发送验证码")
async def send_code(
    req: SendCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    输入学号，系统自动拼接 @mail.sdu.edu.cn 并发送验证码。
    开发模式下验证码会打印在控制台。
    """
    sid = req.student_id.strip()
    _validate_student_id_format(sid)
    now = time.time()
    client_ip = extract_client_ip(request)

    # IP 级限流
    ip_hits = _prune_hits(
        _send_ip_hits,
        client_ip,
        settings.SEND_CODE_IP_WINDOW_SECONDS,
        now,
    )
    if len(ip_hits) >= settings.SEND_CODE_MAX_PER_IP_WINDOW:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    # 学号级限流
    sid_hits = _prune_hits(
        _send_sid_hits,
        sid,
        settings.SEND_CODE_STUDENT_WINDOW_SECONDS,
        now,
    )
    if len(sid_hits) >= settings.SEND_CODE_MAX_PER_STUDENT_WINDOW:
        raise HTTPException(status_code=429, detail="该学号请求过于频繁，请稍后再试")

    email = f"{sid}{settings.ALLOWED_EMAIL_SUFFIX}"

    try:
        await create_and_send_code(db, email)
        _send_ip_hits.setdefault(client_ip, []).append(now)
        _send_sid_hits.setdefault(sid, []).append(now)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证码发送失败: {e}")

    return {
        "message": "验证码已发送",
        "email": email,
        "expire_seconds": settings.CODE_EXPIRE_SECONDS,
    }


@router.post("/verify", response_model=TokenResponse, summary="验证码登录")
async def verify(req: VerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """验证码校验通过后，创建或获取用户，返回 JWT Token"""
    sid = req.student_id.strip()
    _validate_student_id_format(sid)
    email = f"{sid}{settings.ALLOWED_EMAIL_SUFFIX}"
    now = time.time()

    # 验证码错误次数过多 -> 临时封禁
    blocked_until = _verify_block_until.get(email, 0)
    if blocked_until > now:
        wait_seconds = int(blocked_until - now)
        raise HTTPException(status_code=429, detail=f"验证失败次数过多，请{wait_seconds}秒后再试")

    ok_code, verify_reason = await verify_code(db, email, req.code)
    if not ok_code:
        fail_hits = _prune_hits(
            _verify_fail_hits,
            email,
            settings.VERIFY_FAIL_WINDOW_SECONDS,
            now,
        )
        fail_hits.append(now)
        _verify_fail_hits[email] = fail_hits
        if len(fail_hits) >= settings.VERIFY_MAX_FAIL_PER_EMAIL_WINDOW:
            _verify_block_until[email] = now + settings.VERIFY_BLOCK_SECONDS
            raise HTTPException(
                status_code=429,
                detail=f"验证失败次数过多，请{settings.VERIFY_BLOCK_SECONDS}秒后再试",
            )
        if verify_reason == "expired":
            raise HTTPException(status_code=400, detail="验证码已过期，请重新发送")
        raise HTTPException(status_code=400, detail="验证码错误，请检查后重试")

    # 验证成功，清理失败计数
    _verify_fail_hits.pop(email, None)
    _verify_block_until.pop(email, None)

    sid_hash = hash_student_id(sid)
    is_admin_sid = sid in settings.admin_student_ids_list
    result = await db.execute(select(User).where(User.student_id_hash == sid_hash))
    user = result.scalar_one_or_none()
    must_bind_nickname = False
    must_set_password = False

    if user is None:
        user = User(
            student_id_hash=sid_hash,
            email=email,
            nickname=None,
            password_hash=None,
            is_admin=is_admin_sid,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        must_bind_nickname = True
        must_set_password = True
        print(f"✅ 新用户注册: user_id={user.id}")
    else:
        # 允许通过配置自动提升管理员
        if is_admin_sid and not user.is_admin:
            user.is_admin = True
        must_bind_nickname = not bool((user.nickname or "").strip())
        must_set_password = not bool((user.password_hash or "").strip())
        print(f"✅ 用户登录: user_id={user.id}")

    # JWT 的 sub 建议使用字符串，避免部分解析器校验失败
    expires_delta = timedelta(days=1) if req.remember_me else None
    fp = build_client_fingerprint(request)
    token = create_access_token(data={"sub": str(user.id), "uah": fp["uah"], "ipn": fp["ipn"]}, expires_delta=expires_delta)
    return TokenResponse(
        access_token=token,
        must_bind_nickname=must_bind_nickname,
        must_set_password=must_set_password,
        nickname=user.nickname,
        is_admin=bool(user.is_admin),
    )


@router.post("/password-login", response_model=TokenResponse, summary="账号密码登录")
async def password_login(req: PasswordLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    sid = req.student_id.strip()
    _validate_student_id_format(sid)
    now = time.time()
    if not req.password:
        raise HTTPException(status_code=400, detail="请输入密码")
    if len(req.password) < 6 or len(req.password) > 32:
        raise HTTPException(status_code=400, detail="密码长度需为 6-32 位")

    sid_hash = hash_student_id(sid)
    result = await db.execute(select(User).where(User.student_id_hash == sid_hash))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="账号不存在，请先使用验证码首次登录")
    if user.is_banned:
        raise HTTPException(status_code=403, detail="账号已被封禁")
    if not (user.password_hash or "").strip():
        raise HTTPException(status_code=400, detail="该账号尚未设置密码，请先使用验证码登录并设置密码")

    lock_key = str(user.id)
    blocked_until = _password_block_until.get(lock_key, 0)
    if blocked_until > now:
        wait_seconds = int(blocked_until - now)
        raise HTTPException(status_code=429, detail=f"密码错误次数过多，请{wait_seconds}秒后再试")

    if not (user.password_hash and verify_password(req.password, user.password_hash)):
        fail_hits = _prune_hits(
            _password_fail_hits,
            lock_key,
            settings.VERIFY_FAIL_WINDOW_SECONDS,
            now,
        )
        fail_hits.append(now)
        _password_fail_hits[lock_key] = fail_hits
        if len(fail_hits) >= settings.VERIFY_MAX_FAIL_PER_EMAIL_WINDOW:
            _password_block_until[lock_key] = now + settings.VERIFY_BLOCK_SECONDS
            raise HTTPException(
                status_code=429,
                detail=f"密码错误次数过多，请{settings.VERIFY_BLOCK_SECONDS}秒后再试",
            )
        raise HTTPException(status_code=400, detail="密码错误")

    _password_fail_hits.pop(lock_key, None)
    _password_block_until.pop(lock_key, None)

    expires_delta = timedelta(days=1) if req.remember_me else None
    fp = build_client_fingerprint(request)
    token = create_access_token(data={"sub": str(user.id), "uah": fp["uah"], "ipn": fp["ipn"]}, expires_delta=expires_delta)
    must_bind_nickname = not bool((user.nickname or "").strip())
    return TokenResponse(
        access_token=token,
        must_bind_nickname=must_bind_nickname,
        must_set_password=False,
        nickname=user.nickname,
        is_admin=bool(user.is_admin),
    )


@router.post("/set-password", summary="设置或修改登录密码")
async def set_password(
    req: SetPasswordRequest,
    user: User = Depends(get_current_user),
):
    pwd = req.password or ""
    cpwd = req.confirm_password or ""
    _validate_password_policy(pwd)
    if pwd != cpwd:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")
    if user.password_hash and verify_password(pwd, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
    user.password_hash = hash_password(pwd)
    return {"message": "密码设置成功"}


@router.post("/bind-nickname", summary="绑定匿名昵称")
async def bind_nickname(
    req: BindNicknameRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 已绑定不可修改
    if (user.nickname or "").strip():
        raise HTTPException(status_code=400, detail="匿名昵称已绑定，不可修改")

    nickname = (req.nickname or "").strip()
    ok_filter, msg_filter = check_content(nickname)
    if not ok_filter:
        await log_moderation_hit(
            db,
            user_id=user.id,
            scene="nickname",
            content=nickname,
            reason=msg_filter or "昵称命中敏感词",
        )
        raise HTTPException(status_code=400, detail=msg_filter)

    ok, msg = validate_nickname(nickname)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    existing_name = await db.execute(select(User.id).where(User.nickname == nickname))
    if existing_name.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="该匿名昵称已被使用，请更换")

    user.nickname = nickname
    return {"message": "匿名昵称绑定成功", "nickname": nickname}


@router.get("/me", response_model=UserProfileResponse, summary="当前登录用户信息")
async def me(user: User = Depends(get_current_user)):
    nickname = (user.nickname or "").strip() or None
    return UserProfileResponse(
        nickname=nickname,
        must_bind_nickname=nickname is None,
        has_password=bool((user.password_hash or "").strip()),
        is_admin=bool(user.is_admin),
    )


@router.get("/notifications", summary="查看我的消息通知")
async def my_notifications(
    page: int = 1,
    size: int = 30,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    size = max(1, min(size, 100))
    page = max(1, page)

    # 1) 他人评论了我的帖子
    post_comment_rows = await db.execute(
        select(Comment, Post)
        .join(Post, Post.id == Comment.post_id)
        .where(
            Post.user_id == user.id,
            Post.is_deleted == False,
            Comment.is_deleted == False,
            Comment.user_id != user.id,
        )
        .order_by(desc(Comment.created_at))
        .limit(500)
    )

    # 2) 他人回复了我的评论
    reply_rows = await db.execute(
        select(Comment, Post)
        .join(Post, Post.id == Comment.post_id)
        .where(
            Comment.reply_to_user_id == user.id,
            Comment.is_deleted == False,
            Comment.user_id != user.id,
            Post.is_deleted == False,
        )
        .order_by(desc(Comment.created_at))
        .limit(500)
    )
    # 2.1) 兼容历史数据：若 reply_to_user_id 为空，则通过 parent_id 反查父评论作者
    parent_comment = aliased(Comment)
    reply_rows_legacy = await db.execute(
        select(Comment, Post)
        .join(Post, Post.id == Comment.post_id)
        .join(parent_comment, parent_comment.id == Comment.parent_id)
        .where(
            Comment.reply_to_user_id.is_(None),
            Comment.parent_id.is_not(None),
            Comment.is_deleted == False,
            Comment.user_id != user.id,
            Post.is_deleted == False,
            parent_comment.is_deleted == False,
            parent_comment.user_id == user.id,
        )
        .order_by(desc(Comment.created_at))
        .limit(500)
    )

    # 3) 管理处理反馈（沿用 moderation 日志）
    moderation_rows = await db.execute(
        select(ModerationLog)
        .where(
            ModerationLog.user_id == user.id,
            ModerationLog.scene == "admin_report_result",
        )
        .order_by(desc(ModerationLog.created_at))
        .limit(200)
    )

    items: list[dict] = []
    by_comment_notice_id: dict[str, dict] = {}

    # 通知里的名字也走帖内匿名代号，跨帖不可追踪
    from app.utils.anonymous import generate_anon_name as _gen_anon

    def _notify_name(user_id: int | None, post_id: int | None) -> str:
        if not user_id or not post_id:
            return "同学"
        return _gen_anon(int(user_id), int(post_id))

    for c, p in post_comment_rows.all():
        nid = f"c-{c.id}"
        by_comment_notice_id[nid] = {
            "id": nid,
            "type": "post_comment",
            "created_at": c.created_at,
            "post_id": c.post_id,
            "comment_id": c.id,
            "text": f"{_notify_name(c.user_id, c.post_id)} 评论了你的帖子",
        }

    for child, p in reply_rows.all():
        nid = f"c-{child.id}"
        # 同一条评论如果既是“评论帖子”又是“回复评论”，优先展示“回复评论”
        by_comment_notice_id[nid] = {
            "id": nid,
            "type": "comment_reply",
            "created_at": child.created_at,
            "post_id": child.post_id,
            "comment_id": child.id,
            "text": f"{_notify_name(child.user_id, child.post_id)} 回复了你的评论",
        }

    for child, p in reply_rows_legacy.all():
        nid = f"c-{child.id}"
        by_comment_notice_id[nid] = {
            "id": nid,
            "type": "comment_reply",
            "created_at": child.created_at,
            "post_id": child.post_id,
            "comment_id": child.id,
            "text": f"{_notify_name(child.user_id, child.post_id)} 回复了你的评论",
        }

    items.extend(by_comment_notice_id.values())

    for r in moderation_rows.scalars().all():
        items.append(
            {
                "id": f"m-{r.id}",
                "type": "report_result",
                "created_at": r.created_at,
                "post_id": None,
                "comment_id": None,
                "text": f"📩 举报处理反馈：{r.reason or '管理员已处理你的举报'}",
            }
        )

    items.sort(key=lambda x: x.get("created_at") or datetime.min, reverse=True)
    start = (page - 1) * size
    end = start + size
    return items[start:end]


@router.get("/moderation-events", summary="查看我的治理记录")
async def my_moderation_events(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    size = max(1, min(size, 100))
    page = max(1, page)
    result = await db.execute(
        select(ModerationLog)
        .where(ModerationLog.user_id == user.id)
        .where(ModerationLog.scene.like("admin_%"))
        .order_by(desc(ModerationLog.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "scene": r.scene,
            "reason": r.reason or "",
            "content_preview": r.content_preview or "",
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/appeals", summary="查看我的申诉")
async def my_appeals(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    size = max(1, min(size, 100))
    page = max(1, page)
    result = await db.execute(
        select(Appeal)
        .where(Appeal.user_id == user.id)
        .order_by(desc(Appeal.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = result.scalars().all()
    return [
        {
            "id": a.id,
            "moderation_log_id": a.moderation_log_id,
            "content": a.content,
            "status": a.status,
            "admin_reply": a.admin_reply or "",
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        }
        for a in rows
    ]


@router.post("/appeals", summary="提交申诉")
async def create_appeal(
    req: AppealCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = (req.content or "").strip()
    if len(content) < 5:
        raise HTTPException(status_code=400, detail="申诉内容至少 5 个字符")
    if len(content) > 1000:
        raise HTTPException(status_code=400, detail="申诉内容不能超过 1000 个字符")

    event_result = await db.execute(
        select(ModerationLog).where(
            ModerationLog.id == req.moderation_log_id,
            ModerationLog.user_id == user.id,
            ModerationLog.scene.like("admin_%"),
        )
    )
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="治理记录不存在")

    existing_result = await db.execute(
        select(Appeal).where(
            Appeal.user_id == user.id,
            Appeal.moderation_log_id == req.moderation_log_id,
            Appeal.status == "pending",
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="该记录已有待处理申诉")

    db.add(
        Appeal(
            user_id=user.id,
            moderation_log_id=req.moderation_log_id,
            content=content,
            status="pending",
        )
    )
    return {"message": "申诉已提交，等待管理员处理"}
