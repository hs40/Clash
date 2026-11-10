"""配置工程的基础测试。

运行：.venv\Scripts\python.exe -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# 公共配置文件 → 必须出现的顶层键
COMMON_FILES = {
    "general.yaml": ("mode", "log-level", "ipv6"),
    "proxies.yaml": ("proxies",),
    "proxy-groups.yaml": ("proxy-groups",),
    "dns.yaml": ("dns",),
    "rules.yaml": ("rules",),
}


def load_yaml(path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class SourceFilesTest(unittest.TestCase):
    """源文件必须存在且非空（空文件不能冒充有效配置）。"""

    def test_common_sources_exist(self):
        for name in COMMON_FILES:
            path = ROOT / "configs" / "common" / name
            with self.subTest(file=name):
                self.assertTrue(path.is_file(), "缺少源文件：%s" % path)
                self.assertGreater(path.stat().st_size, 0, "源文件为空：%s" % path)

    def test_common_sources_are_valid_yaml_with_expected_keys(self):
        for name, expected in COMMON_FILES.items():
            path = ROOT / "configs" / "common" / name
            with self.subTest(file=name):
                try:
                    data = load_yaml(path)
                except yaml.YAMLError as exc:
                    self.fail("%s 不是合法 YAML：%s" % (path, exc))
                self.assertIsInstance(data, dict, "%s 顶层必须是映射" % path)
                self.assertEqual(
                    set(data), set(expected),
                    "%s 的顶层键应为 %s，实际为 %s"
                    % (path, sorted(expected), sorted(data)),
                )



if __name__ == "__main__":
    unittest.main()