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
import unicodedata
from typing import Iterable


# 词库按类别维护，便于后续运营同学扩词
_DEFAULT_WORDS = {
    "abuse": [
        "傻逼",
        "你这个逼",
        "你个逼",
        "shabi",
        "shab",
        "shabi啊",
        "傻b",
        "傻x",
        "sb",
        "cnm",
        "草泥马",
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
        "打倒共产党",
        "推翻共产党",
        "打倒中共",
        "推翻中共",
        "颠覆国家政权",
        "暴力革命",
        "分裂国家",
        "煽动颠覆",
        "恐怖袭击",
    ],
}


_SENSITIVE_WORDS: set[str] = set()
_SENSITIVE_PATTERNS = [
    # 常见辱骂拆字绕过（如: 傻-逼 / 傻 逼）
    re.compile(r"傻\W{0,3}逼"),
    re.compile(r"你\W{0,2}(?:这|个)\W{0,2}逼"),
    re.compile(r"s\W{0,2}h\W{0,2}a\W{0,2}b\W{0,2}i", re.IGNORECASE),
    re.compile(r"s\W{0,2}b", re.IGNORECASE),
    re.compile(r"c\W{0,2}n\W{0,2}m", re.IGNORECASE),
    re.compile(r"煞\W{0,3}笔"),
    re.compile(r"脑\W{0,3}残"),
    # 极端暴力导向
    re.compile(r"打倒\W{0,3}(?:共\W{0,2}产\W{0,2}党|中\W{0,2}共)"),
    re.compile(r"推翻\W{0,3}(?:共\W{0,2}产\W{0,2}党|中\W{0,2}共|政\W{0,2}府)"),
    re.compile(r"颠覆\W{0,3}国家\W{0,3}政权"),
    re.compile(r"分裂\W{0,3}国家"),
    re.compile(r"暴力\W{0,3}革命"),
    re.compile(r"推翻\W{0,3}政府"),
    re.compile(r"煽动\W{0,3}颠覆"),
]

# 组合规则：行动导向词 + 政治对象词 同时出现即拦截
_POLITICAL_ACTION_WORDS = [
    "打倒", "推翻", "颠覆", "推翻政权", "颠覆政权", "夺权", "起义", "暴动", "造反",
    "独立", "分裂", "煽动", "颠覆国家政权", "暴力革命",
]

_POLITICAL_TARGET_WORDS = [
    "共产党", "中共", "政府", "政权", "国家", "党中央", "体制", "制度", "国家政权",
]


def _normalize_text(text: str) -> str:
    """
    归一化文本，降低绕过率：
    - 小写化
    - 去除空白与常见符号
    """
    normalized = unicodedata.normalize("NFKC", text or "")
    lowered = normalized.lower()
    # 去掉零宽字符
    lowered = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]", "", lowered)
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

    # 先跑模式匹配，拦截拆字/加符号绕过
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(raw) or pattern.search(normalized):
            return False, "内容包含违规词汇或不当表达，请修改后发布"

    # 行为词 + 政治目标词组合拦截（更严格）
    hit_action = any(w in normalized for w in _POLITICAL_ACTION_WORDS)
    hit_target = any(w in normalized for w in _POLITICAL_TARGET_WORDS)
    if hit_action and hit_target:
        return False, "内容包含违规词汇或不当表达，请修改后发布"

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
