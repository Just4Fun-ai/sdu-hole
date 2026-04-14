from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, posts, admin
from app.services.filter import load_words_from_file


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库"""
    settings.validate_runtime_security()
    print(f"\n🕳️  {settings.APP_NAME} 正在启动...")
    print(f"📧 邮件模式: {settings.EMAIL_MODE}")
    print(f"🏫 邮箱后缀: {settings.ALLOWED_EMAIL_SUFFIX}")
    load_words_from_file(settings.SENSITIVE_WORDS_FILE)
    await init_db()
    print("✅ 数据库初始化完成")
    print(f"📖 API 文档: http://localhost:8000/docs\n")
    yield
    print(f"\n👋 {settings.APP_NAME} 已关闭")


app = FastAPI(
    title="山大树洞 API",
    description="SDU Hole - 山东大学匿名校园社区",
    version="0.1.0",
    lifespan=lifespan,
)

# 跨域配置（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(admin.router)


@app.get("/", tags=["首页"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "message": "欢迎来到山大树洞 🕳️",
    }


@app.get("/api/tags", tags=["标签"])
async def get_tags():
    return [
        "课程评价", "校园活动", "美食推荐", "游玩推荐",
        "生活吐槽", "求助", "表白墙", "二手交易", "考研交流", "失物招领",
    ]
