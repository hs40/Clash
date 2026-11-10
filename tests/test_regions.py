"""地区识别测试（ENG-01 接缝 S1：纯函数 regions.classify_node）。

运行：.venv/Scripts/python.exe -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import regions  # noqa: E402


class RegionNamesTest(unittest.TestCase):
    """七个入口的名称与顺序由负责人确认，不得增删或改写。"""

    def test_region_groups_are_the_confirmed_seven(self):
        self.assertEqual(
            regions.REGION_GROUPS,
            ["香港节点", "台湾节点", "日本节点", "韩国节点", "狮城节点", "美国节点", "其他节点"],
        )


class ClassifyNodeTest(unittest.TestCase):
    """S1 接缝：节点名 → 地区入口。"""

    CASES = {
        "香港节点": ["占位-香港-01", "HK-01", "hk 01", "Hong Kong 01"],
        "台湾节点": ["占位-台湾-01", "台北-01", "台灣-01", "TW-01"],
        "日本节点": ["占位-日本-01", "东京-01", "大阪-01", "JP-01"],
        "韩国节点": ["占位-韩国-01", "首尔-01", "韓國-01", "KR-01"],
        "狮城节点": ["占位-狮城-01", "新加坡-01", "獅城-01", "SG-01"],
        "美国节点": [
            "占位-美国-01", "美國-01", "洛杉矶-01", "圣何塞-01",
            "纽约-01", "US-01", "USA-01", "us-01",
        ],
    }

    def test_known_nodes_are_classified(self):
        for group, names in self.CASES.items():
            for name in names:
                with self.subTest(node=name):
                    self.assertEqual(regions.classify_node(name), group)

    def test_unmatched_nodes_go_to_other(self):
        for name in ["占位-其他-01", "备用-01"]:
            with self.subTest(node=name):
                self.assertEqual(regions.classify_node(name), "其他节点")

    def test_ascii_codes_do_not_match_inside_words(self):
        self.assertEqual(regions.classify_node("RUSSIA-01"), "其他节点")
        self.assertEqual(regions.classify_node("JPEG-01"), "其他节点")

    def test_first_matching_region_wins(self):
        self.assertEqual(regions.classify_node("美国-香港-01"), "香港节点")
        self.assertEqual(regions.classify_node("日本-美国-01"), "日本节点")
        self.assertEqual(regions.classify_node("新加坡-韩国-01"), "韩国节点")

    def test_empty_name_falls_back_to_other(self):
        self.assertEqual(regions.classify_node(""), "其他节点")


if __name__ == "__main__":
    unittest.main()
