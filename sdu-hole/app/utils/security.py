import hashlib
import ipaddress
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

security_scheme = HTTPBearer()

ALGORITHM = "HS256"
# 首选 Argon2id；兼容历史 bcrypt 哈希，登录时可平滑验证旧密码
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=19456,  # 19 MiB (OWASP 推荐基线之一)
    argon2__time_cost=2,
    argon2__parallelism=1,
)


def hash_student_id(student_id: str) -> str:
    """对学号做 SHA256 哈希，数据库不存明文"""
    return hashlib.sha256(f"sdu-hole:{student_id}".encode()).hexdigest()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def _extract_client_ip(request: Request) -> str:
    direct_ip = (request.client.host if request.client and request.client.host else "") or "unknown"
    if not settings.TRUST_PROXY_HEADERS:
        return direct_ip

    trusted_proxies = set(settings.trusted_proxy_ips_list)
    if direct_ip not in trusted_proxies:
        return direct_ip

    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if not xff:
        return direct_ip

    # XFF 取最左侧客户端 IP；格式非法则回退直连 IP
    forwarded = xff.split(",")[0].strip()
    try:
        ipaddress.ip_address(forwarded)
        return forwarded
    except ValueError:
        return direct_ip


def _ip_network_fingerprint(ip_str: str) -> str:
    if not ip_str:
        return "unknown"
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return "unknown"
    if ip_obj.version == 4:
        parts = ip_str.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3]) + ".0/24"
        return "unknown"
    exploded = ip_obj.exploded.split(":")
    return ":".join(exploded[:4]) + "::/64"


def build_client_fingerprint(request: Request) -> dict:
    ua = (request.headers.get("user-agent") or "").strip().lower()
    ua_hash = hashlib.sha256(ua.encode()).hexdigest()[:24]
    ip_network = _ip_network_fingerprint(_extract_client_ip(request))
    return {"uah": ua_hash, "ipn": ip_network}


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Token 中解析当前用户"""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_sub = payload.get("sub")
        if user_sub is None:
            raise credentials_exception
        try:
            user_id = int(user_sub)
        except (TypeError, ValueError):
            raise credentials_exception
        token_uah = payload.get("uah")
        token_ipn = payload.get("ipn")
    except JWTError:
        raise credentials_exception

    # 绑定设备/网络：换设备或换网络需重新登录
    current_fp = build_client_fingerprint(request)
    if token_uah and token_uah != current_fp["uah"]:
        raise credentials_exception
    if token_ipn and token_ipn != current_fp["ipn"]:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if user.is_banned:
        raise HTTPException(status_code=403, detail="账号已被封禁")

    return user


def ensure_admin(user: User):
    if not bool(user.is_admin):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
