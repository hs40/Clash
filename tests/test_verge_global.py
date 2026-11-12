"""Verge 全局 Merge/Script 生成测试（VERGE-GLOBAL 接缝 G1/G2）。

G1：build_merge 只输出 store-selected 与两个 inline Provider。
G2：build_script 对任意订阅生成固定 13 组、27 条规则、MVP DNS，
    并过滤坏节点、保留 Verge 注入的 tun/external-controller/secret。
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402
import verge_global  # noqa: E402

def find_node():
    candidates = [os.environ.get("NODE"), shutil.which("node")]
    bundled = (
        Path.home() / ".dsh" / "dsh-runtimes" / "dsh-primary-runtime"
        / "dependencies" / "node" / "bin" / "node.exe"
    )
    candidates.append(str(bundled))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


NODE = find_node()


def proxy(name, **extra):
    item = {
        "name": name,
        "type": "ss",
        "server": "192.0.2.1",
        "port": 443,
        "cipher": "aes-128-gcm",
        "password": "PLACEHOLDER-NOT-REAL",
        "udp": False,
    }
    item.update(extra)
    return item


def bad_reality(name, short_id):
    return proxy(
        name,
        type="vless",
        uuid="00000000-0000-0000-0000-000000000000",
        network="tcp",
        tls=True,
        **{"reality-opts": {"public-key": "PLACEHOLDER", "short-id": short_id}},
    )


def sample_config():
    return {
        "proxies": [
            proxy("香港 01"),
            proxy("台湾 01"),
            proxy("日本 01"),
            proxy("韩国 01"),
            proxy("狮城 01"),
            proxy("美国 01"),
            proxy("未知地区 01"),
            proxy("香港 REALITY 良好 8", type="vless",
                  **{"reality-opts": {"public-key": "x", "short-id": "0123abcd"}}),
            proxy("美国 REALITY 良好 16", type="vless",
                  **{"reality-opts": {"public-key": "x", "short-id": "0123456789abcdef"}}),
            bad_reality("德国 REALITY 坏 14", "01145141919810"),
            bad_reality("美国 REALITY 坏 4", "6076"),
        ],
        "proxy-groups": [{"name": "旧组", "type": "select", "proxies": ["香港 01"]}],
        "rules": ["DOMAIN-SUFFIX,old.example,DIRECT"],
        "rule-providers": {
            "geosite-private": {"type": "inline", "behavior": "domain", "payload": ["private"]},
            "geosite-cn": {"type": "inline", "behavior": "domain", "payload": ["cn"]},
            "qx_old": {"type": "http", "behavior": "classical", "url": "https://example.invalid/x"},
        },
        "dns": {"listen": "0.0.0.0:53"},
        "mixed-port": 7890,
        "port": 7899,
        "socks-port": 7898,
        "mode": "global",
        "ipv6": True,
        "allow-lan": True,
        "tun": {"enable": False, "stack": "system"},
        "external-controller": "127.0.0.1:9",
        "secret": "keep-me",
        "profile": {"store-selected": True},
    }


def run_script(script, config, profile_name="FIB"):
    if NODE is None:
        raise unittest.SkipTest("node 不可用")
    code = script + "\nconst __cfg = " + json.dumps(config, ensure_ascii=False)
    code += "; const __out = main(__cfg, " + json.dumps(profile_name, ensure_ascii=False)
    code += "); process.stdout.write(JSON.stringify(__out));"
    proc = subprocess.run(
        [NODE, "-e", code], capture_output=True, text=True, encoding="utf-8"
    )
    if proc.returncode != 0:
        raise AssertionError("node 执行失败：%s\n%s" % (proc.stdout, proc.stderr))
    return json.loads(proc.stdout)


class MergeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = verge_global.build_merge(ROOT)
        cls.merge = yaml.safe_load(cls.text)

    def test_only_profile_and_two_inline_providers(self):
        self.assertEqual(set(self.merge), {"profile", "rule-providers"})
        self.assertEqual(self.merge["profile"], {"store-selected": True})
        self.assertEqual(
            list(self.merge["rule-providers"]), ["geosite-cn", "geosite-private"]
        )
        for name in ("geosite-cn", "geosite-private"):
            entry = self.merge["rule-providers"][name]
            self.assertEqual(entry["type"], "inline")
            self.assertEqual(entry["behavior"], "domain")
            self.assertTrue(entry["payload"])

    def test_payload_matches_repository_snapshot(self):
        from providers import load_provider_lock, read_provider_payload

        lock = load_provider_lock(ROOT)
        for name in ("geosite-cn", "geosite-private"):
            with self.subTest(provider=name):
                expected = read_provider_payload(lock["providers"][name], ROOT)
                self.assertEqual(
                    self.merge["rule-providers"][name]["payload"], expected
                )

    def test_does_not_write_groups_rules_proxies_or_dns(self):
        for key in ("proxy-groups", "rules", "proxies", "dns"):
            self.assertNotIn(key, self.merge)


class ScriptStructureTest(unittest.TestCase):
    def setUp(self):
        self.script = verge_global.build_script(ROOT)

    def test_group_order_is_fixed(self):
        self.assertEqual(
            verge_global.GROUP_ORDER,
            [
                "PROXY", "Google", "OpenAI", "Claude", "Cursor", "自动选择",
                "香港节点", "台湾节点", "日本节点", "韩国节点",
                "狮城节点", "美国节点", "其他节点",
            ],
        )

    def test_script_embeds_repository_rules_and_dns(self):
        self.assertIn("MATCH,PROXY", self.script)
        self.assertIn("0.0.0.0:1053", self.script)
        self.assertIn("geosite-private", self.script)
        self.assertIn("geosite-cn", self.script)

    def test_script_writes_no_tun_controller_or_secret(self):
        for word in ("external-controller", "secret", "tun"):
            with self.subTest(word=word):
                self.assertNotIn('config["%s"]' % word, self.script)
                self.assertNotIn("config['%s']" % word, self.script)

    def test_exclusion_marker_is_valid_and_used(self):
        text = verge_global.build_script(ROOT, exclusions={"FIB": ["坏节点"]})
        self.assertIn("/* MVP-EXCLUDED-BEGIN */", text)
        self.assertIn("/* MVP-EXCLUDED-END */", text)
        self.assertIn("坏节点", text)


@unittest.skipIf(NODE is None, "node 不可用")
class ScriptBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = verge_global.build_script(ROOT)
        cls.result = run_script(cls.script, sample_config())
        cls.groups = {group["name"]: group for group in cls.result["proxy-groups"]}

    def test_group_names_and_types_follow_fixed_order(self):
        self.assertEqual(
            [group["name"] for group in self.result["proxy-groups"]],
            verge_global.GROUP_ORDER,
        )
        self.assertEqual(self.groups["PROXY"]["type"], "select")
        self.assertEqual(self.groups["Google"]["type"], "fallback")
        self.assertEqual(self.groups["自动选择"]["type"], "url-test")
        for name in ("OpenAI", "Claude", "Cursor") + tuple(verge_global.REGION_GROUPS):
            self.assertEqual(self.groups[name]["type"], "select")

    def test_proxy_and_google_members(self):
        self.assertEqual(
            self.groups["PROXY"]["proxies"],
            ["自动选择"] + list(verge_global.REGION_GROUPS) + ["DIRECT"],
        )
        self.assertEqual(
            self.groups["Google"]["proxies"],
            ["美国节点", "狮城节点", "日本节点", "香港节点"],
        )

    def test_ai_groups_include_auto_and_all_regions(self):
        expected = ["自动选择"] + list(verge_global.REGION_GROUPS)
        for name in ("OpenAI", "Claude", "Cursor"):
            self.assertEqual(self.groups[name]["proxies"], expected)

    def test_auto_select_contains_only_good_nodes(self):
        self.assertEqual(
            self.groups["自动选择"]["proxies"],
            [
                "香港 01", "台湾 01", "日本 01", "韩国 01", "狮城 01",
                "美国 01", "未知地区 01", "香港 REALITY 良好 8",
                "美国 REALITY 良好 16",
            ],
        )

    def test_bad_reality_nodes_are_filtered(self):
        self.assertNotIn("德国 REALITY 坏 14", self.groups["自动选择"]["proxies"])
        self.assertNotIn("美国 REALITY 坏 4", self.groups["自动选择"]["proxies"])
        self.assertEqual(
            [item["name"] for item in self.result["proxies"]],
            self.groups["自动选择"]["proxies"],
        )

    def test_region_groups_use_classified_nodes(self):
        self.assertEqual(self.groups["香港节点"]["proxies"], ["香港 01", "香港 REALITY 良好 8"])
        self.assertEqual(self.groups["美国节点"]["proxies"], ["美国 01", "美国 REALITY 良好 16"])
        self.assertEqual(self.groups["其他节点"]["proxies"], ["未知地区 01"])

    def test_rules_are_repository_rules_and_last_is_match(self):
        expected = build.compile_rules(
            yaml.safe_load((ROOT / "configs" / "common" / "rules.yaml").read_text(encoding="utf-8"))["rules"],
            set(verge_global.GROUP_ORDER),
            {"geosite-cn", "geosite-private"},
        )
        self.assertEqual(self.result["rules"], expected)
        self.assertEqual(len(expected), 33)
        self.assertEqual(self.result["rules"][-1], "MATCH,PROXY")

    def test_only_mvp_providers_remain(self):
        self.assertEqual(
            sorted(self.result["rule-providers"]), ["geosite-cn", "geosite-private"]
        )

    def test_dns_is_exact_repository_dns(self):
        expected = yaml.safe_load(
            (ROOT / "configs" / "common" / "dns.yaml").read_text(encoding="utf-8")
        )["dns"]
        self.assertEqual(self.result["dns"], expected)

    def test_fixed_runtime_keys_and_deleted_ports(self):
        self.assertEqual(self.result["mixed-port"], 7897)
        self.assertNotIn("port", self.result)
        self.assertNotIn("socks-port", self.result)
        self.assertEqual(self.result["mode"], "rule")
        self.assertIs(self.result["ipv6"], False)
        self.assertIs(self.result["allow-lan"], False)

    def test_verge_injected_keys_are_preserved(self):
        self.assertEqual(self.result["tun"], {"enable": False, "stack": "system"})
        self.assertEqual(self.result["external-controller"], "127.0.0.1:9")
        self.assertEqual(self.result["secret"], "keep-me")
        self.assertEqual(self.result["profile"], {"store-selected": True})

    def test_old_groups_and_rules_are_replaced(self):
        self.assertNotIn("旧组", self.groups)
        self.assertNotIn("DOMAIN-SUFFIX,old.example,DIRECT", self.result["rules"])

    def test_empty_region_falls_back_to_auto_select(self):
        cfg = sample_config()
        cfg["proxies"] = [proxy("美国 01")]
        result = run_script(self.script, cfg)
        groups = {group["name"]: group for group in result["proxy-groups"]}
        self.assertEqual(groups["香港节点"]["proxies"], ["自动选择"])

    def test_profile_exclusion_removes_specific_node(self):
        script = verge_global.build_script(ROOT, exclusions={"FIB": ["香港 01"]})
        result = run_script(script, sample_config(), "FIB")
        groups = {group["name"]: group for group in result["proxy-groups"]}
        self.assertNotIn("香港 01", groups["自动选择"]["proxies"])
        self.assertNotIn("香港 01", groups["香港节点"]["proxies"])

    def test_provider_guard_rejects_proxy_providers(self):
        cfg = sample_config()
        cfg["proxy-providers"] = {"p": {"type": "http", "url": "https://example.invalid"}}
        with self.assertRaises(AssertionError):
            run_script(self.script, cfg)