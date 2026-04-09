import hashlib

# 山大特色元素作为匿名昵称
ANIMALS = [
    "松鼠", "白鹭", "银杏", "海棠", "泉水", "石榴", "明湖", "樱花",
    "蝴蝶", "翠鸟", "梧桐", "玉兰", "荷花", "柳树", "燕子", "白鸽",
    "喜鹊", "紫藤", "桂花", "青竹", "云雀", "杜鹃", "牡丹", "兰草",
    "丹顶鹤", "梅花", "芙蓉", "百灵", "水杉", "黄鹂", "凤仙", "锦鲤",
]


def generate_anon_name(user_id: int, post_id: int) -> str:
    """
    为用户在某个帖子下生成固定的匿名昵称。
    同一用户在同一帖子下始终显示相同昵称，
    但在不同帖子下昵称不同，保护隐私。
    """
    raw = f"sdu-hole-anon:{user_id}:{post_id}"
    hash_val = hashlib.sha256(raw.encode()).hexdigest()
    idx = int(hash_val[:8], 16) % len(ANIMALS)
    return f"匿名{ANIMALS[idx]}"


def generate_post_anon_name(user_id: int) -> str:
    """发帖时的匿名昵称（用时间戳做盐，每帖不同）"""
    import time
    raw = f"sdu-hole-post:{user_id}:{time.time_ns()}"
    hash_val = hashlib.sha256(raw.encode()).hexdigest()
    idx = int(hash_val[:8], 16) % len(ANIMALS)
    return f"匿名{ANIMALS[idx]}"
