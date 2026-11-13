"""平台规则接缝：dsh-pocket 隧道与 Tailscale 必须直连。

S2/规则：只调用 build.compile_rules，不读取产物文件，不访问网络。
"""

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402
import verge_global  # noqa: E402


def compiled_rules():
    rules = yaml.safe_load(
        (ROOT / "configs" / "common" / "rules.yaml").read_text(encoding="utf-8")
    )["rules"]
    return build.compile_rules(
        rules,
        set(verge_global.GROUP_ORDER),
        {"geosite-cn", "geosite-private"},
    )


class PlatformRuleTest(unittest.TestCase):
    def test_tunnel_and_tailscale_rules_are_special_direct_rules(self):
        rules = compiled_rules()
        expected = [
            "DOMAIN-SUFFIX,argotunnel.com,DIRECT",
            "DOMAIN-SUFFIX,trycloudflare.com,DIRECT",
            "IP-CIDR,198.41.192.0/24,DIRECT,no-resolve",
            "DOMAIN-SUFFIX,tailscale.com,DIRECT",
            "DOMAIN-SUFFIX,tailscale.io,DIRECT",
            "DOMAIN-SUFFIX,ts.net,DIRECT",
        ]
        self.assertEqual(rules[:2], [
            "DOMAIN-SUFFIX,local,DIRECT",
            "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
        ])
        self.assertEqual(rules[2:8], expected)

    def test_compiled_rule_count_and_match_last(self):
        rules = compiled_rules()
        self.assertEqual(len(rules), 33)
        self.assertEqual(rules[-1], "MATCH,PROXY")
        self.assertEqual(rules.count("MATCH,PROXY"), 1)

    def test_rule_lines_are_unique(self):
        rules = compiled_rules()
        self.assertEqual(len(rules), len(set(rules)))


if __name__ == "__main__":
    unittest.main()
