"""ENG-02 规则编译测试（接缝：纯函数 compile_rules + build_platform/CLI）。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402


class ProductionRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = build.build_platform("windows", ROOT)
        cls.rules = cls.cfg["rules"]

    def test_rules_are_flat_strings_and_match_is_last(self):
        self.assertTrue(self.rules)
        for rule in self.rules:
            self.assertIsInstance(rule, str)
        self.assertEqual(self.rules[-1], "MATCH,PROXY")
        self.assertEqual(sum(1 for r in self.rules if r.startswith("MATCH")), 1)

    def test_every_rule_target_exists(self):
        names = {g["name"] for g in self.cfg["proxy-groups"]} | set(
            build.BUILTIN_POLICIES
        )
        for rule in self.rules:
            parts = rule.split(",")
            target = parts[1] if parts[0] == "MATCH" else parts[2]
            self.assertIn(target, names, rule)
            if parts[0] == "RULE-SET":
                self.assertIn(parts[1], self.cfg["rule-providers"], rule)

    def test_tailscale_cgnat_is_direct_before_lan_geoip(self):
        rule = "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve"
        self.assertIn(rule, self.rules)
        self.assertLess(
            self.rules.index(rule),
            self.rules.index("GEOIP,LAN,DIRECT,no-resolve"),
        )

    def test_provider_rules_are_present(self):
        self.assertIn("RULE-SET,geosite-private,DIRECT", self.rules)
        self.assertIn("RULE-SET,geosite-cn,DIRECT", self.rules)
        self.assertEqual(
            set(self.cfg["rule-providers"]), {"geosite-cn", "geosite-private"}
        )

    def test_business_routes_follow_baseline(self):
        expected = {
            "google.com": "Google",
            "openai.com": "OpenAI",
            "chatgpt.com": "OpenAI",
            "claude.ai": "Claude",
            "cursor.com": "Cursor",
            "apple.com": "DIRECT",
            "icbc.com.cn": "DIRECT",
        }
        by_suffix = {}
        for rule in self.rules:
            parts = rule.split(",")
            if parts[0] == "DOMAIN-SUFFIX":
                by_suffix[parts[1]] = parts[2]
        for domain, target in expected.items():
            self.assertEqual(by_suffix.get(domain), target, domain)
        self.assertIn("DOMAIN-KEYWORD,tracker,DIRECT", self.rules)


def make_rules():
    return {
        "special": [{"priority": 100, "rule": "DOMAIN-SUFFIX,local,DIRECT"}],
        "business": [
            {"priority": 100, "rule": "DOMAIN-SUFFIX,example.com,PROXY"}
        ],
        "base": [{"priority": 100, "rule": "GEOIP,CN,DIRECT"}],
        "fallback": [{"priority": 100, "rule": "MATCH,PROXY"}],
    }


class CompileRulesTest(unittest.TestCase):
    def test_layers_compile_in_fixed_order_and_sort_by_priority(self):
        rules = {
            "fallback": [{"priority": 900, "rule": "MATCH,PROXY"}],
            "business": [
                {"priority": 200, "rule": "DOMAIN-SUFFIX,b.example,PROXY"},
                {"priority": 100, "rule": "DOMAIN-SUFFIX,a.example,PROXY"},
            ],
            "special": [{"priority": 50, "rule": "DOMAIN,local,DIRECT"}],
            "base": [{"priority": 300, "rule": "GEOIP,CN,DIRECT"}],
        }
        self.assertEqual(
            build.compile_rules(rules, ["PROXY"]),
            [
                "DOMAIN,local,DIRECT",
                "DOMAIN-SUFFIX,a.example,PROXY",
                "DOMAIN-SUFFIX,b.example,PROXY",
                "GEOIP,CN,DIRECT",
                "MATCH,PROXY",
            ],
        )

    def test_builtin_policy_target_is_allowed(self):
        self.assertEqual(
            build.compile_rules(make_rules(), ["PROXY"]),
            [
                "DOMAIN-SUFFIX,local,DIRECT",
                "DOMAIN-SUFFIX,example.com,PROXY",
                "GEOIP,CN,DIRECT",
                "MATCH,PROXY",
            ],
        )


def first_match(rules, host):
    """按 Mihomo 的首条匹配语义模拟域名匹配，仅覆盖本测试用到的类型。"""
    for rule in rules:
        parts = rule.split(",")
        kind = parts[0]
        if kind == "DOMAIN" and host == parts[1]:
            return parts[2]
        if kind == "DOMAIN-SUFFIX" and (
            host == parts[1] or host.endswith("." + parts[1])
        ):
            return parts[2]
        if kind == "MATCH":
            return parts[1]
    return None


class ConflictTest(unittest.TestCase):
    def test_special_rule_wins_over_business(self):
        rules = {
            "special": [
                {"priority": 100, "rule": "DOMAIN,api.example.com,DIRECT"}
            ],
            "business": [
                {"priority": 100, "rule": "DOMAIN-SUFFIX,example.com,PROXY"}
            ],
            "base": [{"priority": 100, "rule": "GEOIP,CN,DIRECT"}],
            "fallback": [{"priority": 100, "rule": "MATCH,PROXY"}],
        }
        compiled = build.compile_rules(rules, ["PROXY"])
        self.assertEqual(first_match(compiled, "api.example.com"), "DIRECT")
        self.assertEqual(first_match(compiled, "www.example.com"), "PROXY")
        self.assertEqual(first_match(compiled, "unmatched.test"), "PROXY")


class CompileRulesValidationTest(unittest.TestCase):
    def assert_error(self, rules, fragment, groups=None, provider_names=()):
        with self.assertRaises(build.ConfigError) as ctx:
            build.compile_rules(rules, groups or ["PROXY"], provider_names)
        self.assertIn(fragment, str(ctx.exception))

    def test_unknown_layer_is_rejected(self):
        rules = make_rules()
        rules["extra"] = []
        self.assert_error(rules, "未知的规则层")

    def test_missing_layer_is_rejected(self):
        rules = make_rules()
        rules.pop("base")
        self.assert_error(rules, "缺少规则层")

    def test_duplicate_priority_within_layer_is_rejected(self):
        rules = make_rules()
        rules["business"].append(
            {"priority": 100, "rule": "DOMAIN-SUFFIX,other.example,PROXY"}
        )
        self.assert_error(rules, "priority 重复")

    def test_unknown_entry_key_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["prio"] = 100
        self.assert_error(rules, "未登记的键")

    def test_non_mapping_entry_is_rejected(self):
        rules = make_rules()
        rules["business"] = ["DOMAIN-SUFFIX,example.com,PROXY"]
        self.assert_error(rules, "映射")

    def test_bool_priority_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["priority"] = True
        self.assert_error(rules, "priority")

    def test_non_integer_priority_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["priority"] = "100"
        self.assert_error(rules, "priority")

    def test_missing_rule_text_is_rejected(self):
        rules = make_rules()
        rules["business"][0].pop("rule")
        self.assert_error(rules, "rule")

    def test_unknown_rule_type_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["rule"] = "FOO,example.com,PROXY"
        self.assert_error(rules, "不受支持")

    def test_malformed_rule_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["rule"] = "DOMAIN-SUFFIX,example.com"
        self.assert_error(rules, "格式错误")

    def test_unknown_target_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["rule"] = "DOMAIN-SUFFIX,example.com,Missing"
        self.assert_error(rules, "Missing")

    def test_rule_set_with_known_provider_is_allowed(self):
        rules = make_rules()
        rules["business"][0]["rule"] = "RULE-SET,trusted-set,PROXY"
        self.assertEqual(
            build.compile_rules(rules, ["PROXY"], ["trusted-set"]),
            [
                "DOMAIN-SUFFIX,local,DIRECT",
                "RULE-SET,trusted-set,PROXY",
                "GEOIP,CN,DIRECT",
                "MATCH,PROXY",
            ],
        )

    def test_rule_set_with_unknown_provider_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["rule"] = "RULE-SET,trusted-set,PROXY"
        self.assert_error(rules, "trusted-set", provider_names=["other-set"])

    def test_malformed_rule_set_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["rule"] = "RULE-SET,trusted-set,PROXY,extra"
        self.assert_error(rules, "格式错误", provider_names=["trusted-set"])

    def test_match_outside_fallback_is_rejected(self):
        rules = make_rules()
        rules["business"][0]["rule"] = "MATCH,PROXY"
        self.assert_error(rules, "MATCH")

    def test_match_must_be_last(self):
        rules = make_rules()
        rules["fallback"] = [
            {"priority": 100, "rule": "MATCH,PROXY"},
            {"priority": 110, "rule": "DOMAIN,example.com,DIRECT"},
        ]
        self.assert_error(rules, "最后")

    def test_missing_match_is_rejected(self):
        rules = make_rules()
        rules["fallback"] = [{"priority": 100, "rule": "DOMAIN,example.com,DIRECT"}]
        self.assert_error(rules, "MATCH")

    def test_duplicate_match_is_rejected(self):
        rules = make_rules()
        rules["fallback"] = [
            {"priority": 100, "rule": "MATCH,PROXY"},
            {"priority": 110, "rule": "MATCH,DIRECT"},
        ]
        self.assert_error(rules, "MATCH")


if __name__ == "__main__":
    unittest.main()
