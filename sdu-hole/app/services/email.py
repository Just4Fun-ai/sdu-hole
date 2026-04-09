import random
import socket
import time
from typing import Dict, Tuple

import aiosmtplib
from email.mime.text import MIMEText

from app.config import settings

# 内存缓存验证码: {email: (code, expire_timestamp)}
# 生产环境应替换为 Redis
_code_store: Dict[str, Tuple[str, float]] = {}


def generate_code() -> str:
    """生成6位数字验证码"""
    return "".join([str(random.randint(0, 9)) for _ in range(settings.CODE_LENGTH)])


async def send_verification_email(email: str, code: str):
    """根据配置选择发送方式"""
    if settings.EMAIL_MODE == "console":
        await _send_console(email, code)
    else:
        await _send_smtp(email, code)


async def _send_console(email: str, code: str):
    """控制台模式：直接打印验证码（开发用）"""
    print("\n" + "=" * 50)
    print(f"  📧 验证码邮件（控制台模式）")
    print(f"  收件人: {email}")
    print(f"  验证码: {code}")
    print(f"  有效期: {settings.CODE_EXPIRE_SECONDS // 60} 分钟")
    print("=" * 50 + "\n")


async def _send_smtp(email: str, code: str):
    """SMTP模式：真实发送邮件，自动适配山大邮箱和外部邮箱"""
    html = f"""
    <div style="max-width:420px;margin:0 auto;padding:24px;font-family:sans-serif;">
        <h2 style="color:#1a1a2e;margin-bottom:8px;">🕳️ 山大树洞</h2>
        <p style="color:#555;font-size:14px;">你正在登录山大树洞，验证码如下：</p>
        <div style="font-size:36px;font-weight:bold;letter-spacing:10px;
                    color:#c2410c;padding:24px;background:#fef3e8;
                    border-radius:12px;text-align:center;margin:20px 0;">
            {code}
        </div>
        <p style="color:#999;font-size:12px;">
            验证码 {settings.CODE_EXPIRE_SECONDS // 60} 分钟内有效。如非本人操作请忽略。
        </p>
    </div>
    """
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = f"【山大树洞】验证码：{code}"
    msg["From"] = f"山大树洞 <{settings.SMTP_USER}>"
    msg["To"] = email

    # 山大邮箱 smtp.sdu.edu.cn 端口25，不用TLS
    # 外部邮箱（163/QQ等）端口465，用TLS
    use_tls = settings.SMTP_PORT == 465
    start_tls = settings.SMTP_USE_STARTTLS  # 有些服务器需要 STARTTLS

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=use_tls,
            start_tls=start_tls,
        )
    except Exception as e:
        raise RuntimeError(_format_smtp_error(e)) from e


def _format_smtp_error(error: Exception) -> str:
    """把 SMTP 底层异常转换为前端可读提示。"""
    msg = str(error).lower()

    if isinstance(error, socket.gaierror) or "name or service not known" in msg:
        return "SMTP 服务器地址解析失败，请检查 SMTP_HOST 是否正确"

    if isinstance(error, TimeoutError) or "timed out" in msg:
        return "连接 SMTP 服务器超时，请检查网络环境（校内网）与端口是否可访问"

    if isinstance(error, ConnectionRefusedError) or "connection refused" in msg:
        return "SMTP 连接被拒绝，请检查 SMTP_HOST/SMTP_PORT 是否正确，或服务器是否限制访问"

    if any(k in msg for k in ["auth", "authentication", "535", "5.7.8"]):
        return "SMTP 登录失败：请检查 SMTP_USER / SMTP_PASSWORD 是否正确"

    if "starttls" in msg or "ssl" in msg or "tls" in msg:
        return "SMTP TLS 配置异常，请检查 SMTP_PORT 与 SMTP_USE_STARTTLS 是否匹配"

    return f"SMTP 发送失败：{error}"


async def create_and_send_code(email: str) -> str:
    """生成验证码 -> 缓存 -> 发送"""
    # 频率限制：60秒内不能重复发送
    if email in _code_store:
        _, expire_at = _code_store[email]
        remaining = expire_at - time.time()
        if remaining > settings.CODE_EXPIRE_SECONDS - 60:
            raise ValueError("请求过于频繁，请60秒后重试")

    code = generate_code()
    _code_store[email] = (code, time.time() + settings.CODE_EXPIRE_SECONDS)
    await send_verification_email(email, code)
    return code


def verify_code(email: str, code: str) -> bool:
    """校验验证码"""
    if email not in _code_store:
        return False

    stored_code, expire_at = _code_store[email]
    if time.time() > expire_at:
        del _code_store[email]
        return False

    if stored_code != code:
        return False

    # 验证成功，删除验证码（一次性）
    del _code_store[email]
    return True
