"""平台配置摘要与完整 diff 的纯函数测试（S2）。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import platform_diff  # noqa: E402


def config(proxies, groups=None, rules=None, dns=None, **extra):
    body = {
        "proxies": [{"name": name, "type": "ss"} for name in proxies],
        "proxy-groups": [{"name": name, "type": "select"} for name in (groups or [])],
        "rules": list(rules or ["MATCH,PROXY"]),
        "dns": dict(dns or {}),
    }
    body.update(extra)
    return body


class SummaryTest(unittest.TestCase):
    def test_reports_added_and_removed_nodes(self):
        before = config(["a", "b"], ["PROXY"], ["MATCH,PROXY"])
        after = config(["b", "c"], ["PROXY", "Google"], ["MATCH,PROXY"], mixed_port=7897)
        summary = platform_diff.summarize_config(before, after, files=["Merge.yaml"])
        self.assertEqual(summary["proxies"]["added"], ["c"])
        self.assertEqual(summary["proxies"]["removed"], ["a"])
        self.assertEqual(summary["groups"]["added"], ["Google"])
        self.assertTrue(summary["has_changes"])
        self.assertEqual(summary["files"], ["Merge.yaml"])

    def test_same_config_is_no_change(self):
        before = config(["a"], ["PROXY"], ["MATCH,PROXY"])
        after = config(["a"], ["PROXY"], ["MATCH,PROXY"])
        summary = platform_diff.summarize_config(before, after)
        self.assertFalse(summary["has_changes"])
        self.assertIn("变更：否", platform_diff.render_summary(summary))

    def test_group_field_changes_are_detected_without_name_changes(self):
        before = config(["a"], ["PROXY", "香港节点"])
        after = config(["a"], ["PROXY", "香港节点"])
        after["proxy-groups"][1] = {
            "name": "香港节点", "type": "url-test",
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300, "tolerance": 50, "icon": "data:image/png;base64,AAAA",
        }
        summary = platform_diff.summarize_config(before, after)
        self.assertTrue(summary["has_changes"])
        self.assertEqual(summary["groups"]["added"], [])
        self.assertEqual(summary["groups"]["removed"], [])
        self.assertEqual(summary["groups"]["changed"], [{
            "name": "香港节点",
            "fields": ["icon", "interval", "tolerance", "type", "url"],
        }])
        text = platform_diff.render_summary(summary)
        self.assertIn("策略组内容变更", text)
        self.assertIn("香港节点", text)

    def test_identical_groups_are_not_a_change(self):
        before = {"proxy-groups": [{"name": "PROXY", "type": "select",
                                    "proxies": ["香港节点", "美国节点"]}]}
        after = {"proxy-groups": [{"name": "PROXY", "type": "select",
                                   "proxies": ["香港节点", "美国节点"]}]}
        summary = platform_diff.summarize_config(before, after)
        self.assertEqual(summary["groups"]["changed"], [])
        self.assertFalse(summary["has_changes"])

    def test_group_member_change_is_detected(self):
        before = {"proxy-groups": [{"name": "OpenAI", "type": "select",
                                    "proxies": ["美国节点"]}]}
        after = {"proxy-groups": [{"name": "OpenAI", "type": "fallback",
                                   "proxies": ["美国节点", "狮城节点"]}]}
        summary = platform_diff.summarize_config(before, after)
        self.assertTrue(summary["has_changes"])
        self.assertEqual(summary["groups"]["changed"][0]["name"], "OpenAI")
        self.assertEqual(summary["groups"]["changed"][0]["fields"], ["proxies", "type"])

    def test_dns_and_rule_hash_are_reported(self):
        before = config(["a"], ["PROXY"], ["MATCH,PROXY"], dns={"listen": "0.0.0.0:1053"})
        after = config(["a"], ["PROXY"], ["DOMAIN-SUFFIX,local,DIRECT", "MATCH,PROXY"],
                       dns={"listen": "127.0.0.1:7874"})
        summary = platform_diff.summarize_config(before, after)
        text = platform_diff.render_summary(summary, "windows")
        self.assertIn("DNS listen", text)
        self.assertIn("0.0.0.0:1053", text)
        self.assertIn("127.0.0.1:7874", text)
        self.assertIn("规则：1 -> 2 条，SHA-256", text)

    def test_full_diff_hides_nothing_but_is_unified(self):
        before = config(["a"])
        after = config(["b"])
        diff = platform_diff.render_diff(before, after)
        self.assertIn("--- before", diff)
        self.assertIn("+++ after", diff)
        self.assertIn("-- name: a", diff)
        self.assertIn("+- name: b", diff)

    def test_redact_config_removes_node_and_controller_secrets(self):
        before = {
            "proxies": [{
                "name": "香港 01", "type": "ss", "server": "203.0.113.9",
                "port": 443, "cipher": "aes-128-gcm", "password": "REAL-SECRET",
            }],
            "proxy-providers": {"FIB": {"type": "http", "url": "https://example.invalid/sub"}},
            "external-controller": "127.0.0.1:9097",
            "secret": "REAL-SECRET",
            "rule-providers": {
                "geosite-cn": {"type": "inline", "behavior": "domain",
                               "payload": ["+.example.cn"]},
            },
        }
        safe = platform_diff.redact_config(before)
        dumped = str(safe)
        self.assertNotIn("REAL-SECRET", dumped)
        self.assertNotIn("203.0.113.9", dumped)
        self.assertNotIn("example.invalid", dumped)
        self.assertEqual(safe["proxies"], [{"name": "香港 01", "type": "ss"}])
        self.assertEqual(safe["proxy-providers"], ["FIB"])
        self.assertEqual(safe["secret"], "[REDACTED]")
        self.assertEqual(safe["rule-providers"]["geosite-cn"]["payload_count"], 1)
        self.assertNotIn("payload", safe["rule-providers"]["geosite-cn"])
        self.assertEqual(before["proxies"][0]["password"], "REAL-SECRET")

    def test_render_diff_same_config(self):
        before = config(["a"])
        self.assertEqual(platform_diff.render_diff(before, before), "配置内容无变化\n")

    def test_render_diff_ignores_mapping_key_order(self):
        before = {"mixed-port": 7897, "dns": {"listen": "0.0.0.0:1053",
                                              "enhanced-mode": "fake-ip"}}
        after = {"dns": {"enhanced-mode": "fake-ip",
                         "listen": "0.0.0.0:1053"}, "mixed-port": 7897}
        self.assertEqual(platform_diff.render_diff(before, after), "配置内容无变化\n")

    def test_align_owned_drops_runtime_only_keys_and_keeps_expected(self):
        before = {
            "mixed-port": 7890,
            "redir-port": 7892,
            "external-controller": "127.0.0.1:9097",
            "secret": "REAL-SECRET",
            "tun": {"enable": True, "stack": "gvisor", "device": "Mihomo",
                    "mtu": 1500},
            "dns": {"listen": "0.0.0.0:53", "enhanced-mode": "fake-ip",
                    "cache-size": 4096},
            "proxies": [{"name": "香港 01", "type": "vless"}],
        }
        after = {
            "mixed-port": 7897,
            "tun": {"enable": True, "stack": "gvisor"},
            "dns": {"listen": "0.0.0.0:1053", "enhanced-mode": "fake-ip"},
            "proxies": [{"name": "香港 01", "type": "vless"}],
        }
        aligned = platform_diff.align_owned(before, after)
        self.assertEqual(aligned, {
            "mixed-port": 7890,
            "tun": {"enable": True, "stack": "gvisor"},
            "dns": {"listen": "0.0.0.0:53", "enhanced-mode": "fake-ip"},
            "proxies": [{"name": "香港 01", "type": "vless"}],
        })
        self.assertNotIn("redir-port", str(aligned))
        self.assertNotIn("secret", str(aligned))
        self.assertNotIn("device", str(aligned))


if __name__ == "__main__":
    unittest.main()
