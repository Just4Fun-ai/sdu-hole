from fastapi import APIRouter, HTTPException, Depends
import random

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


@router.get("/random-nickname", response_model=RandomNicknameResponse, summary="生成随机匿名昵称")
async def random_nickname(db: AsyncSession = Depends(get_db)):
    for _ in range(30):
        name = generate_random_nickname()
        existing = await db.execute(select(User.id).where(User.nickname == name))
        if existing.scalar_one_or_none() is None:
            return RandomNicknameResponse(nickname=name)
    return RandomNicknameResponse(nickname=f"同学{random.randint(1000, 9999)}")


@router.post("/send-code", summary="发送验证码")
async def send_code(req: SendCodeRequest):
    """
    输入学号，系统自动拼接 @mail.sdu.edu.cn 并发送验证码。
    开发模式下验证码会打印在控制台。
    """
    sid = req.student_id.strip()

    if not sid.isdigit() or len(sid) < 6 or len(sid) > 14:
        raise HTTPException(status_code=400, detail="学号格式不正确，请输入6-14位数字学号")

    email = f"{sid}{settings.ALLOWED_EMAIL_SUFFIX}"

    try:
        await create_and_send_code(email)
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

    if not verify_code(email, req.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    sid_hash = hash_student_id(sid)
    result = await db.execute(select(User).where(User.student_id_hash == sid_hash))
    user = result.scalar_one_or_none()
    must_bind_nickname = False

    if user is None:
        user = User(student_id_hash=sid_hash, email=email, nickname=None)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        must_bind_nickname = True
        print(f"✅ 新用户注册: user_id={user.id}")
    else:
        must_bind_nickname = not bool((user.nickname or "").strip())
        print(f"✅ 用户登录: user_id={user.id}")

    # JWT 的 sub 建议使用字符串，避免部分解析器校验失败
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        must_bind_nickname=must_bind_nickname,
        nickname=user.nickname,
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
    )
