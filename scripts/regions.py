"""中文地区节点识别（ENG-01）。

规则来源：docs/REQUIREMENTS.md §4.1，以及项目负责人 2026-11-10 确认的关键词表。
- 七个入口名称固定，不得增删或改写；
- 按 REGION_GROUPS 的顺序匹配，先命中者优先；
- 纯 ASCII 关键词按整词匹配（前后不能紧邻英文字母），因此 RUSSIA 不会命中 US，
  HK01 仍然命中 HK；
- 未命中任何关键词的节点归入「其他节点」。
"""

import re

REGION_GROUPS = [
    "香港节点",
    "台湾节点",
    "日本节点",
    "韩国节点",
    "狮城节点",
    "美国节点",
    "其他节点",
]

OTHER_GROUP = "其他节点"

# 顺序即匹配优先级；「其他节点」是兜底组，不参与关键词匹配。
REGION_KEYWORDS = {
    "香港节点": ("香港", "HK", "Hong Kong"),
    "台湾节点": ("台湾", "台北", "台灣", "TW"),
    "日本节点": ("日本", "东京", "大阪", "JP"),
    "韩国节点": ("韩国", "首尔", "韓國", "KR"),
    "狮城节点": ("新加坡", "狮城", "獅城", "SG"),
    "美国节点": ("美国", "美國", "洛杉矶", "圣何塞", "纽约", "US", "USA"),
}


def _matches(name, keyword):
    """中文关键词按子串匹配；ASCII 关键词按整词匹配，避免 RUSSIA 命中 US。"""
    if keyword.isascii():
        pattern = r"(?<![A-Za-z])%s(?![A-Za-z])" % re.escape(keyword)
        return re.search(pattern, name, re.IGNORECASE) is not None
    return keyword in name


def classify_node(name):
    """返回节点所属的地区入口名称；无法识别时返回「其他节点」。"""
    if not isinstance(name, str) or not name:
        return OTHER_GROUP
    for group in REGION_GROUPS:
        for keyword in REGION_KEYWORDS.get(group, ()):
            if _matches(name, keyword):
                return group
    return OTHER_GROUP
