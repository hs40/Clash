"""配置工程的基础测试。

运行：.venv/Scripts/python.exe -m unittest discover -s tests -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))
import build  # noqa: E402

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
                     "rule-providers", "mode", "log-level", "ipv6")

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


EXPECTED_WINDOWS_KEYS = [
    "mode", "log-level", "ipv6", "mixed-port", "allow-lan",
    "tun", "dns", "rule-providers", "proxies", "proxy-groups", "rules",
]
EXPECTED_OPENCLASH_KEYS = [
    "mode", "log-level", "ipv6", "port", "allow-lan", "bind-address",
    "dns", "rule-providers", "proxies", "proxy-groups", "rules",
]


class BuilderMergeTest(unittest.TestCase):
    """S2 接缝：build_platform(platform, root) 的合并结果。"""

    def test_build_platform_merges_common_and_platform(self):
        cfg = build.build_platform("windows", ROOT)
        self.assertEqual(list(cfg), EXPECTED_WINDOWS_KEYS)
        self.assertEqual(cfg["mixed-port"], 7897)
        self.assertFalse(cfg["allow-lan"])
        self.assertEqual(cfg["tun"]["stack"], "gvisor")
        self.assertEqual(cfg["dns"]["enhanced-mode"], "fake-ip")
        self.assertEqual(set(cfg["rule-providers"]), {"geosite-cn", "geosite-private"})
        self.assertEqual(cfg["rule-providers"]["geosite-private"]["type"], "inline")
        self.assertEqual(len(cfg["proxies"]), 7)
        self.assertEqual(cfg["rules"][-1], "MATCH,PROXY")

    def test_openclash_uses_http_port_without_windows_keys(self):
        cfg = build.build_platform("openclash", ROOT)
        self.assertEqual(list(cfg), EXPECTED_OPENCLASH_KEYS)
        self.assertEqual(cfg["port"], 7893)
        self.assertEqual(cfg["bind-address"], "*")
        self.assertNotIn("mixed-port", cfg)
        self.assertNotIn("tun", cfg)

    def test_dump_yaml_is_deterministic(self):
        cfg = build.build_platform("windows", ROOT)
        self.assertEqual(build.dump_yaml(cfg), build.dump_yaml(cfg))
        self.assertTrue(build.dump_yaml(cfg).endswith("\n"))


def make_fixture_tree(root_dir):
    """在临时目录里复制一份真实源文件树，供错误注入测试使用。"""
    for platform in ("windows", "openclash"):
        (root_dir / "configs" / platform).mkdir(parents=True)
        for src in (ROOT / "configs" / platform).glob("*.yaml"):
            shutil.copy(src, root_dir / "configs" / platform / src.name)
    (root_dir / "configs" / "common").mkdir(parents=True)
    for src in (ROOT / "configs" / "common").glob("*.yaml"):
        shutil.copy(src, root_dir / "configs" / "common" / src.name)
    shutil.copytree(ROOT / "providers", root_dir / "providers")


class MergeContractTest(unittest.TestCase):
    """S2 接缝的错误路径：合并契约被破坏时必须报错并指出位置。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_fixture_tree(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def platform_file(self, platform="windows"):
        return self.root / "configs" / platform / "platform.yaml"

    def test_unknown_top_level_key_is_rejected(self):
        path = self.platform_file()
        path.write_text(path.read_text(encoding="utf-8") + "foo-bar: true\n",
                        encoding="utf-8")
        with self.assertRaises(build.ConfigError) as ctx:
            build.build_platform("windows", self.root)
        message = str(ctx.exception)
        self.assertIn("foo-bar", message)
        self.assertIn("platform.yaml", message)

    def test_key_owned_by_common_cannot_appear_in_platform(self):
        path = self.platform_file()
        path.write_text(path.read_text(encoding="utf-8") + "mode: global\n",
                        encoding="utf-8")
        with self.assertRaises(build.ConfigError) as ctx:
            build.build_platform("windows", self.root)
        self.assertIn("mode", str(ctx.exception))

    def test_duplicate_key_in_one_file_is_rejected(self):
        path = self.platform_file("openclash")
        path.write_text(path.read_text(encoding="utf-8") + "port: 7999\n",
                        encoding="utf-8")
        with self.assertRaises(build.ConfigError) as ctx:
            build.build_platform("openclash", self.root)
        message = str(ctx.exception)
        self.assertIn("port", message)
        self.assertIn("openclash", message)

    def test_missing_platform_key_is_rejected(self):
        path = self.platform_file()
        text = path.read_text(encoding="utf-8")
        path.write_text(text.split("tun:")[0].rstrip("\n") + "\n",
                        encoding="utf-8")
        with self.assertRaises(build.ConfigError) as ctx:
            build.build_platform("windows", self.root)
        self.assertIn("tun", str(ctx.exception))

    def test_common_change_reflects_in_both_platforms(self):
        dns_path = self.root / "configs" / "common" / "dns.yaml"
        dns_path.write_text(
            dns_path.read_text(encoding="utf-8").replace("198.18.0.1/16", "198.19.0.1/16"),
            encoding="utf-8",
        )
        for platform in ("windows", "openclash"):
            self.assertEqual(
                build.build_platform(platform, self.root)["dns"]["fake-ip-range"],
                "198.19.0.1/16",
                "公共配置修改未反映到 %s" % platform,
            )

    def test_platform_change_only_affects_that_platform(self):
        base_windows = build.build_platform("windows", self.root)
        base_openclash = build.build_platform("openclash", self.root)
        path = self.platform_file()
        path.write_text(
            path.read_text(encoding="utf-8").replace("mixed-port: 7897", "mixed-port: 7898"),
            encoding="utf-8",
        )
        self.assertEqual(build.build_platform("windows", self.root)["mixed-port"], 7898)
        self.assertNotEqual(build.build_platform("windows", self.root), base_windows)
        self.assertEqual(build.build_platform("openclash", self.root), base_openclash)

    def test_unknown_platform_is_rejected(self):
        with self.assertRaises(build.ConfigError) as ctx:
            build.build_platform("linux", self.root)
        self.assertIn("linux", str(ctx.exception))


class CommandLineTest(unittest.TestCase):
    """S1 接缝：命令行入口。"""

    def run_cli(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build.py"), *args],
            capture_output=True, text=True, encoding="utf-8", env=env,
        )

    def test_platform_all_writes_both_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("--platform", "all", "--out", tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            for platform in ("windows", "openclash"):
                path = Path(tmp) / platform / "config.yaml"
                self.assertTrue(path.is_file(), "缺少产物：%s" % path)
                cfg = load_yaml(path)
                self.assertEqual(
                    cfg.keys() & {"proxies", "proxy-groups", "rules", "dns", "rule-providers"},
                    {"proxies", "proxy-groups", "rules", "dns", "rule-providers"},
                )

    def test_output_is_byte_identical_across_runs(self):
        with tempfile.TemporaryDirectory() as first, \
                tempfile.TemporaryDirectory() as second:
            self.assertEqual(self.run_cli("--platform", "all", "--out", first).returncode, 0)
            self.assertEqual(self.run_cli("--platform", "all", "--out", second).returncode, 0)
            for platform in ("windows", "openclash"):
                self.assertEqual(
                    (Path(first) / platform / "config.yaml").read_bytes(),
                    (Path(second) / platform / "config.yaml").read_bytes(),
                    "%s 两次构建结果不一致" % platform,
                )

    def test_config_error_returns_nonzero_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_fixture_tree(root)
            platform_path = root / "configs" / "windows" / "platform.yaml"
            platform_path.write_text(
                platform_path.read_text(encoding="utf-8") + "foo-bar: true\n",
                encoding="utf-8",
            )
            result = self.run_cli(
                "--platform", "windows", "--root", str(root),
                "--out", str(root / "out"),
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("foo-bar", result.stderr)

    def test_invalid_platform_argument_fails(self):
        result = self.run_cli("--platform", "linux")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()