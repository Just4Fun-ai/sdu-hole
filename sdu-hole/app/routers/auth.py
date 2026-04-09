from fastapi import APIRouter, HTTPException, Depends, Request
import random
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    SendCodeRequest,
    VerifyRequest,
    TokenResponse,
    RandomNicknameResponse,
    BindNicknameRequest,
    UserProfileResponse,
)
from app.services.email import create_and_send_code, verify_code
from app.utils.security import hash_student_id, create_access_token, get_current_user
from app.utils.nickname import validate_nickname, generate_random_nickname
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["认证"])


# 轻量防刷缓存（单进程内存版）
_send_ip_hits: dict[str, list[float]] = {}
_send_sid_hits: dict[str, list[float]] = {}
_verify_fail_hits: dict[str, list[float]] = {}
_verify_block_until: dict[str, float] = {}


def _extract_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


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


@router.get("/random-nickname", response_model=RandomNicknameResponse, summary="生成随机匿名昵称")
async def random_nickname(db: AsyncSession = Depends(get_db)):
    for _ in range(30):
        name = generate_random_nickname()
        existing = await db.execute(select(User.id).where(User.nickname == name))
        if existing.scalar_one_or_none() is None:
            return RandomNicknameResponse(nickname=name)
    return RandomNicknameResponse(nickname=f"同学{random.randint(1000, 9999)}")


@router.post("/send-code", summary="发送验证码")
async def send_code(req: SendCodeRequest, request: Request):
    """
    输入学号，系统自动拼接 @mail.sdu.edu.cn 并发送验证码。
    开发模式下验证码会打印在控制台。
    """
    sid = req.student_id.strip()
    now = time.time()
    client_ip = _extract_client_ip(request)

    if not sid.isdigit() or len(sid) < 6 or len(sid) > 14:
        raise HTTPException(status_code=400, detail="学号格式不正确，请输入6-14位数字学号")

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
        await create_and_send_code(email)
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
async def verify(req: VerifyRequest, db: AsyncSession = Depends(get_db)):
    """验证码校验通过后，创建或获取用户，返回 JWT Token"""
    sid = req.student_id.strip()
    email = f"{sid}{settings.ALLOWED_EMAIL_SUFFIX}"
    now = time.time()

    # 验证码错误次数过多 -> 临时封禁
    blocked_until = _verify_block_until.get(email, 0)
    if blocked_until > now:
        wait_seconds = int(blocked_until - now)
        raise HTTPException(status_code=429, detail=f"验证失败次数过多，请{wait_seconds}秒后再试")

    if not verify_code(email, req.code):
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
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    # 验证成功，清理失败计数
    _verify_fail_hits.pop(email, None)
    _verify_block_until.pop(email, None)

    sid_hash = hash_student_id(sid)
    is_admin_sid = sid in settings.admin_student_ids_list
    result = await db.execute(select(User).where(User.student_id_hash == sid_hash))
    user = result.scalar_one_or_none()
    must_bind_nickname = False

    if user is None:
        user = User(
            student_id_hash=sid_hash,
            email=email,
            nickname=None,
            is_admin=is_admin_sid,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        must_bind_nickname = True
        print(f"✅ 新用户注册: user_id={user.id}")
    else:
        # 允许通过配置自动提升管理员
        if is_admin_sid and not user.is_admin:
            user.is_admin = True
        must_bind_nickname = not bool((user.nickname or "").strip())
        print(f"✅ 用户登录: user_id={user.id}")

    # JWT 的 sub 建议使用字符串，避免部分解析器校验失败
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        must_bind_nickname=must_bind_nickname,
        nickname=user.nickname,
        is_admin=bool(user.is_admin),
    )


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
        is_admin=bool(user.is_admin),
    )
