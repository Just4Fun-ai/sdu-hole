from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import SendCodeRequest, VerifyRequest, TokenResponse
from app.services.email import create_and_send_code, verify_code
from app.utils.security import hash_student_id, create_access_token
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["认证"])


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

    if user is None:
        user = User(student_id_hash=sid_hash, email=email)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        print(f"✅ 新用户注册: user_id={user.id}")
    else:
        print(f"✅ 用户登录: user_id={user.id}")

    # JWT 的 sub 建议使用字符串，避免部分解析器校验失败
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)
