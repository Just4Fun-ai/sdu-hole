"""
简单的敏感词过滤服务。
生产环境建议使用更完善的方案（如 DFA 算法 + 敏感词库）。
"""

# 基础敏感词列表（你可以自行扩充）
_SENSITIVE_WORDS = [
    # 这里只放几个示例，实际使用时应加载完整敏感词库
]


def check_content(content: str) -> tuple[bool, str]:
    """
    检查内容是否包含敏感词。
    返回 (is_ok, message)
    """
    for word in _SENSITIVE_WORDS:
        if word in content:
            return False, f"内容包含违规词汇，请修改后重新发布"
    return True, ""


def load_words_from_file(filepath: str):
    """从文件加载敏感词库（每行一个词）"""
    global _SENSITIVE_WORDS
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            _SENSITIVE_WORDS = [line.strip() for line in f if line.strip()]
        print(f"✅ 已加载 {len(_SENSITIVE_WORDS)} 个敏感词")
    except FileNotFoundError:
        print(f"⚠️  敏感词文件 {filepath} 不存在，跳过加载")
