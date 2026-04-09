"""
内容安全过滤服务（基础版）。

目标：
1. 拦截辱骂/脏话/违规词汇；
2. 拦截常见政治敏感与违法违规导向词；
3. 支持外部词库文件动态扩充。

说明：
- 当前是本地词典方案，适合 MVP 与校园社区场景；
- 更高强度建议后续接入专业内容审核服务（文本审核 API）。
"""

from __future__ import annotations

import re
from typing import Iterable


# 词库按类别维护，便于后续运营同学扩词
_DEFAULT_WORDS = {
    "abuse": [
        "傻逼",
        "煞笔",
        "脑残",
        "弱智",
        "滚你妈",
        "去死",
        "废物",
        "妈的",
        "操你",
        "狗东西",
    ],
    "illegal": [
        "冰毒",
        "海洛因",
        "枪支",
        "炸药",
        "代开发票",
        "网赌",
        "洗钱",
        "出售公民信息",
    ],
    "political_sensitive": [
        "推翻政府",
        "暴力革命",
        "分裂国家",
        "煽动颠覆",
        "恐怖袭击",
    ],
}


_SENSITIVE_WORDS: set[str] = set()


def _normalize_text(text: str) -> str:
    """
    归一化文本，降低绕过率：
    - 小写化
    - 去除空白与常见符号
    """
    lowered = (text or "").lower()
    # 去除空白、下划线、常见中英文标点与分隔符
    return re.sub(r"[\s`~!@#$%^&*()\-_=+\[\]{}\\|;:'\",<.>/?，。！？；：“”‘’（）【】、《》…·]+", "", lowered)


def _iter_all_words() -> Iterable[str]:
    for word in _SENSITIVE_WORDS:
        if word:
            yield word


def _rebuild_word_set(extra_words: Iterable[str] | None = None):
    words = set()
    for _, group in _DEFAULT_WORDS.items():
        for w in group:
            w = w.strip()
            if w:
                words.add(w)
    if extra_words:
        for w in extra_words:
            w = w.strip()
            if w and not w.startswith("#"):
                words.add(w)
    # 同时存储原词与归一化词，兼顾可读与抗绕过
    normalized_words = {_normalize_text(w) for w in words if _normalize_text(w)}
    _SENSITIVE_WORDS.clear()
    _SENSITIVE_WORDS.update(words)
    _SENSITIVE_WORDS.update(normalized_words)


def check_content(content: str) -> tuple[bool, str]:
    """
    检查内容是否合规。
    返回: (is_ok, message)
    """
    if not content:
        return True, ""

    raw = content
    normalized = _normalize_text(content)

    for word in _iter_all_words():
        if word in raw or (normalized and word in normalized):
            return False, "内容包含违规词汇或不当表达，请修改后发布"
    return True, ""


def load_words_from_file(filepath: str):
    """
    从文件加载敏感词库（每行一个词，支持 # 注释）。
    """
    extras: list[str] = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                w = line.strip()
                if not w or w.startswith("#"):
                    continue
                extras.append(w)
        _rebuild_word_set(extras)
        print(f"✅ 已加载敏感词 {len(_SENSITIVE_WORDS)} 项（含内置+自定义）")
    except FileNotFoundError:
        _rebuild_word_set()
        print(f"⚠️  敏感词文件 {filepath} 不存在，已使用内置词库")
    except Exception as e:
        _rebuild_word_set()
        print(f"⚠️  加载敏感词失败（{e}），已回退到内置词库")


# 模块导入时先构建内置词库
_rebuild_word_set()

