from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "山大树洞"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./sdu_hole.db"
    # 例如:
    # - 本地: sqlite+aiosqlite:///./sdu_hole.db
    # - 线上: postgresql+asyncpg://user:pass@host:5432/dbname

    # 跨域配置，多个来源用英文逗号分隔
    # 例: https://sdu-hole.vercel.app,https://www.sduhole.com
    CORS_ORIGINS: str = "*"

    # 学校邮箱
    ALLOWED_EMAIL_SUFFIX: str = "@mail.sdu.edu.cn"

    # 邮件模式: "console" 打印到控制台 | "smtp" 真实发送
    EMAIL_MODE: str = "console"

    # SMTP 配置（EMAIL_MODE=smtp 时生效）
    # 山大邮箱: host=smtp.sdu.edu.cn, port=25, starttls=False
    # 163邮箱:  host=smtp.163.com, port=465, starttls=False
    # QQ邮箱:   host=smtp.qq.com, port=465, starttls=False
    SMTP_HOST: str = "smtp.sdu.edu.cn"
    SMTP_PORT: int = 25
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_STARTTLS: bool = False

    # 验证码
    CODE_EXPIRE_SECONDS: int = 300  # 5分钟
    CODE_LENGTH: int = 6

    class Config:
        env_file = ".env"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """兼容常见平台提供的 postgres URL 格式。"""
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql://", 1)
        if value.startswith("postgresql://") and "+asyncpg" not in value:
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
