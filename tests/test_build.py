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



# 平台配置文件 → 必须出现的顶层键（docs/REQUIREMENTS.md §11、§13）
PLATFORM_FILES = {
    "windows": ("mixed-port", "allow-lan", "tun"),
    "openclash": ("port", "allow-lan", "bind-address"),
}

# 公共独占键：出现在平台配置中即视为合并契约破坏
COMMON_OWNED_KEYS = ("proxies", "proxy-groups", "rules", "dns",
                     "mode", "log-level", "ipv6")

# OpenClash 运行时注入的键，MVP 不得写入（§11 约束 4）
RUNTIME_INJECTED_KEYS = ("redir-port", "tproxy-port", "external-controller",
                         "secret", "iptables")


class PlatformFilesTest(unittest.TestCase):
    """平台配置只拥有自己的顶层键，且不得侵入公共或运行时范畴。"""

    def test_platform_sources_exist(self):
        for platform in PLATFORM_FILES:
            path = ROOT / "configs" / platform / "platform.yaml"
            with self.subTest(platform=platform):
                self.assertTrue(path.is_file(), "缺少平台配置：%s" % path)
                self.assertGreater(path.stat().st_size, 0, "平台配置为空：%s" % path)

    def test_platform_keys_match_ownership(self):
        for platform, expected in PLATFORM_FILES.items():
            path = ROOT / "configs" / platform / "platform.yaml"
            with self.subTest(platform=platform):
                data = load_yaml(path)
                self.assertIsInstance(data, dict, "%s 顶层必须是映射" % path)
                self.assertEqual(
                    set(data), set(expected),
                    "%s 的顶层键应为 %s，实际为 %s"
                    % (path, sorted(expected), sorted(data)),
                )

    def test_platform_files_do_not_write_foreign_keys(self):
        for platform in PLATFORM_FILES:
            path = ROOT / "configs" / platform / "platform.yaml"
            keys = set(load_yaml(path))
            with self.subTest(platform=platform):
                self.assertEqual(
                    keys & set(COMMON_OWNED_KEYS), set(),
                    "%s 写入了公共独占键：%s" % (path, sorted(keys & set(COMMON_OWNED_KEYS))),
                )
                self.assertEqual(
                    keys & set(RUNTIME_INJECTED_KEYS), set(),
                    "%s 写入了运行时注入键：%s"
                    % (path, sorted(keys & set(RUNTIME_INJECTED_KEYS))),
                )


if __name__ == "__main__":
    unittest.main()