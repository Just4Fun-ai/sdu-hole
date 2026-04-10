from sqlalchemy.ext.asyncio import AsyncSession

from app.models.moderation_log import ModerationLog


def _clip(text: str, max_len: int = 200) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t[:max_len]


async def log_moderation_hit(
    db: AsyncSession,
    *,
    user_id: int | None,
    scene: str,
    content: str,
    reason: str,
):
    db.add(
        ModerationLog(
            user_id=user_id,
            scene=scene,
            content_preview=_clip(content, 200),
            reason=_clip(reason, 200),
        )
    )

