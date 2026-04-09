import random
import re

from app.services.filter import check_content

_NICK_RE = re.compile(r"^[A-Za-z0-9\u4e00-\u9fff]{1,10}$")

_PREFIX = ["清风", "暖阳", "知行", "青禾", "松影", "星河", "明月", "晨光", "远山", "云舟"]
_SUFFIX = ["同学", "旅人", "书生", "听风", "拾光", "行者", "青鸟", "流云", "未央", "知音"]


def validate_nickname(nickname: str) -> tuple[bool, str]:
    name = (nickname or "").strip()
    if not name:
        return False, "匿名昵称不能为空"
    if len(name) < 1 or len(name) > 10:
        return False, "匿名昵称长度需在1-10个字符之间"
    if not _NICK_RE.fullmatch(name):
        return False, "匿名昵称仅支持中文、英文、数字，不可使用标点符号"

    ok, msg = check_content(name)
    if not ok:
        return False, msg or "昵称包含违规内容，请修改后重试"
    return True, ""


def generate_random_nickname() -> str:
    return f"{random.choice(_PREFIX)}{random.choice(_SUFFIX)}"
