"""策略组生成与引用校验测试（ENG-01 接缝 S2/S3）。

S2：proxy-groups.yaml 的 include 指令由 build_platform 解析成真实成员。
S3：未知指令、无效引用、循环引用必须让构建失败。
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402


def make_fixture_tree(root_dir):
    for platform in ("windows", "openclash"):
        (root_dir / "configs" / platform).mkdir(parents=True)
        for src in (ROOT / "configs" / platform).glob("*.yaml"):
            shutil.copy(src, root_dir / "configs" / platform / src.name)
    (root_dir / "configs" / "common").mkdir(parents=True)
    for src in (ROOT / "configs" / "common").glob("*.yaml"):
        shutil.copy(src, root_dir / "configs" / "common" / src.name)


def load_yaml(path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class GeneratedGroupsTest(unittest.TestCase):
    """S2：真实仓库的构建结果必须包含自动生成成员。"""

    @classmethod
    def setUpClass(cls):
        cls.cfg = build.build_platform("windows", ROOT)
        cls.groups = {g["name"]: g for g in cls.cfg["proxy-groups"]}

    def test_group_names_are_fixed(self):
        self.assertEqual(
            list(self.groups),
            [
                "PROXY", "自动选择", "香港节点", "台湾节点", "日本节点",
                "韩国节点", "狮城节点", "美国节点", "其他节点", "Google",
                "OpenAI", "Claude", "Cursor",
            ],
        )

    def test_ai_groups_are_select_with_auto_and_regions(self):
        expected = [
            "自动选择", "香港节点", "台湾节点", "日本节点",
            "韩国节点", "狮城节点", "美国节点", "其他节点",
        ]
        for name in ("OpenAI", "Claude", "Cursor"):
            with self.subTest(group=name):
                self.assertEqual(self.groups[name]["type"], "select")
                self.assertEqual(self.groups[name]["proxies"], expected)

    def test_auto_select_contains_every_proxy(self):
        self.assertEqual(
            self.groups["自动选择"]["proxies"],
            [p["name"] for p in self.cfg["proxies"]],
        )

    def test_each_region_group_contains_its_nodes(self):
        expected = {
            "香港节点": ["占位-香港-01"],
            "台湾节点": ["占位-台湾-01"],
            "日本节点": ["占位-日本-01"],
            "韩国节点": ["占位-韩国-01"],
            "狮城节点": ["占位-狮城-01"],
            "美国节点": ["占位-美国-01"],
            "其他节点": ["占位-其他-01"],
        }
        for name, members in expected.items():
            with self.subTest(group=name):
                self.assertEqual(self.groups[name]["proxies"], members)

    def test_google_is_us_first_fallback_with_confirmed_order(self):
        google = self.groups["Google"]
        self.assertEqual(google["type"], "fallback")
        self.assertEqual(
            google["proxies"], ["美国节点", "狮城节点", "日本节点", "香港节点"]
        )

    def test_include_directive_does_not_leak_into_output(self):
        for group in self.cfg["proxy-groups"]:
            with self.subTest(group=group["name"]):
                self.assertNotIn("include", group)


class GroupFixtureTest(unittest.TestCase):
    """S2/S3：用临时仓库夹具验证生成与校验规则。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_fixture_tree(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def groups_path(self):
        return self.root / "configs" / "common" / "proxy-groups.yaml"

    def proxies_path(self):
        return self.root / "configs" / "common" / "proxies.yaml"

    def edit_groups(self, mutate):
        data = load_yaml(self.groups_path())
        mutate(data["proxy-groups"])
        self.groups_path().write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def edit_proxies(self, mutate):
        data = load_yaml(self.proxies_path())
        mutate(data["proxies"])
        self.proxies_path().write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def build(self):
        return build.build_platform("windows", self.root)

    def groups_of(self, cfg):
        return {g["name"]: g for g in cfg["proxy-groups"]}

    def test_empty_region_falls_back_to_auto_select(self):
        self.edit_proxies(lambda ps: ps.pop(1))  # 台湾
        groups = self.groups_of(self.build())
        self.assertEqual(groups["台湾节点"]["proxies"], ["自动选择"])

    def test_adding_a_node_appears_in_region_and_auto_select(self):
        self.edit_proxies(
            lambda ps: ps.append({
                "name": "香港-新增-01", "type": "ss", "server": "192.0.2.21",
                "port": 443, "cipher": "aes-128-gcm",
                "password": "PLACEHOLDER-NOT-REAL", "udp": False,
            })
        )
        groups = self.groups_of(self.build())
        self.assertIn("香港-新增-01", groups["香港节点"]["proxies"])
        self.assertIn("香港-新增-01", groups["自动选择"]["proxies"])

    def test_renaming_a_node_keeps_group_names_and_membership(self):
        self.edit_proxies(
            lambda ps: ps[0].update({"name": "香港-新-01"})
        )
        groups = self.groups_of(self.build())
        self.assertEqual(groups["香港节点"]["proxies"], ["香港-新-01"])
        self.assertEqual(
            list(groups),
            [
                "PROXY", "自动选择", "香港节点", "台湾节点", "日本节点",
                "韩国节点", "狮城节点", "美国节点", "其他节点", "Google",
                "OpenAI", "Claude", "Cursor",
            ],
        )

    def test_missing_region_group_is_rejected(self):
        def mutate(gs):
            gs[:] = [g for g in gs if g["name"] != "台湾节点"]
        self.edit_groups(mutate)
        with self.assertRaises(build.ConfigError) as ctx:
            self.build()
        self.assertIn("缺少地区入口", str(ctx.exception))

    def test_unknown_region_include_is_rejected(self):
        self.edit_groups(
            lambda gs: gs.append(
                {"name": "测试组", "type": "select", "include": "region:火星"}
            )
        )
        with self.assertRaises(build.ConfigError) as ctx:
            self.build()
        self.assertIn("火星", str(ctx.exception))

    def test_unknown_include_directive_is_rejected(self):
        self.edit_groups(
            lambda gs: gs.append(
                {"name": "测试组", "type": "select", "include": "everything"}
            )
        )
        with self.assertRaises(build.ConfigError) as ctx:
            self.build()
        self.assertIn("everything", str(ctx.exception))

    def test_include_and_explicit_proxies_conflict(self):
        self.edit_groups(
            lambda gs: gs.append(
                {"name": "测试组", "type": "select", "include": "all",
                 "proxies": ["占位-香港-01"]}
            )
        )
        with self.assertRaises(build.ConfigError) as ctx:
            self.build()
        self.assertIn("测试组", str(ctx.exception))

    def test_missing_node_reference_is_rejected(self):
        self.edit_groups(
            lambda gs: gs.append(
                {"name": "测试组", "type": "select", "proxies": ["不存在节点"]}
            )
        )
        with self.assertRaises(build.ConfigError) as ctx:
            self.build()
        self.assertIn("不存在节点", str(ctx.exception))

    def test_self_reference_is_rejected(self):
        self.edit_groups(
            lambda gs: gs.append(
                {"name": "测试组", "type": "select", "proxies": ["测试组"]}
            )
        )
        with self.assertRaises(build.ConfigError) as ctx:
            self.build()
        self.assertIn("测试组", str(ctx.exception))

    def test_two_group_cycle_is_rejected(self):
        def mutate(gs):
            gs.append({"name": "测试组A", "type": "select", "proxies": ["测试组B"]})
            gs.append({"name": "测试组B", "type": "select", "proxies": ["测试组A"]})
        self.edit_groups(mutate)
        with self.assertRaises(build.ConfigError) as ctx:
            self.build()
        message = str(ctx.exception)
        self.assertIn("测试组A", message)
        self.assertIn("测试组B", message)

    def test_unknown_group_key_is_rejected(self):
        self.edit_groups(
            lambda gs: gs.append(
                {"name": "测试组", "type": "select", "include": "all", "foo": 1}
            )
        )
        with self.assertRaises(build.ConfigError) as ctx:
            self.build()
        self.assertIn("foo", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
