"""平台验收检查测试（S2）；fake DNS/HTTP，不访问真实网络。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import platform_probe  # noqa: E402
import platform_verify  # noqa: E402


class DnsLeakTest(unittest.TestCase):
    def test_fake_ip_and_blocked_lan_public_pass(self):
        def query(name, server):
            if server == "198.18.0.2":
                return {"answers": ["198.18.0.85"]}
            raise platform_probe.ProbeError("timeout")

        result = platform_verify.dns_no_leak(query)
        self.assertTrue(result["passed"])
        self.assertTrue(result["fake_ip"]["passed"])
        self.assertTrue(result["lan"]["passed"])
        self.assertTrue(result["public"]["passed"])

    def test_real_a_from_lan_fails(self):
        def query(name, server):
            if server == "198.18.0.2":
                return {"answers": ["198.18.0.85"]}
            if server == "192.168.2.1":
                return {"answers": ["93.184.216.34"]}
            raise platform_probe.ProbeError("timeout")

        result = platform_verify.dns_no_leak(query)
        self.assertFalse(result["passed"])
        self.assertFalse(result["lan"]["passed"])
        self.assertIn("93.184.216.34", result["lan"]["detail"])

    def test_non_fake_answer_from_proxy_dns_fails(self):
        def query(name, server):
            return {"answers": ["93.184.216.34"]}

        result = platform_verify.dns_no_leak(query)
        self.assertFalse(result["fake_ip"]["passed"])
        self.assertFalse(result["passed"])

    def test_fake_answer_from_lan_is_tolerated(self):
        def query(name, server):
            return {"answers": ["198.18.0.99"]}

        result = platform_verify.dns_no_leak(query)
        self.assertTrue(result["passed"])

    def test_openclash_mode_checks_only_proxy_dns(self):
        def query(name, server):
            if server == "192.168.2.10":
                return {"answers": ["198.18.0.85"]}
            raise AssertionError("不应查询 %s" % server)

        result = platform_verify.dns_no_leak(
            query, fake_server="192.168.2.10",
            lan_server=None, public_server=None,
        )
        self.assertTrue(result["passed"])
        self.assertNotIn("lan", result)
        self.assertNotIn("public", result)


class ExitCountryTest(unittest.TestCase):
    def test_matching_country(self):
        result = platform_verify.exit_country({"country": "jp"}, "日本节点")
        self.assertTrue(result["passed"])
        self.assertTrue(result["verified"])

    def test_mismatching_country(self):
        result = platform_verify.exit_country({"country": "US"}, "日本节点")
        self.assertFalse(result["passed"])

    def test_other_region_non_cn_passes_unverified(self):
        result = platform_verify.exit_country({"country": "US"}, "其他节点")
        self.assertTrue(result["passed"])
        self.assertFalse(result["verified"])
        self.assertIn("非 CN", result["detail"])

    def test_other_region_cn_fails(self):
        result = platform_verify.exit_country({"country": "CN"}, "其他节点")
        self.assertFalse(result["passed"])
        self.assertFalse(result["verified"])

    def test_no_selected_node_non_cn_passes_unverified(self):
        result = platform_verify.exit_country({"country": "HK"}, None)
        self.assertTrue(result["passed"])
        self.assertFalse(result["verified"])
        self.assertIn("未取得选中节点", result["detail"])

    def test_no_selected_node_cn_fails(self):
        result = platform_verify.exit_country({"country": "CN"}, None)
        self.assertFalse(result["passed"])
        self.assertFalse(result["verified"])

    def test_missing_country_degrades(self):
        result = platform_verify.exit_country({}, "美国节点")
        self.assertIsNone(result["passed"])
        self.assertFalse(result["verified"])


class SelectedNodeRegionTest(unittest.TestCase):
    """Q25：选中叶子节点名 -> 地区关键词 -> 国家码 -> 出口比对。

    期望值来自 docs/REQUIREMENTS.md §4.1 的关键词表，不复用实现里的常量。
    """

    def test_hong_kong_leaf_node_matches_hk_exit(self):
        result = platform_verify.exit_country_for_node(
            {"country": "HK"}, "香港 IX2 2倍|原生家宽"
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["group"], "香港节点")
        self.assertEqual(result["expected"], ["HK"])

    def test_hong_kong_leaf_node_with_jp_exit_fails(self):
        result = platform_verify.exit_country_for_node(
            {"country": "JP"}, "香港 IX2 2倍|原生家宽"
        )
        self.assertFalse(result["passed"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["group"], "香港节点")

    def test_singapore_leaf_node_matches_sg_exit(self):
        result = platform_verify.exit_country_for_node(
            {"country": "sg"}, "狮城 HX 2倍|家宽|原生家宽"
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["group"], "狮城节点")

    def test_unknown_leaf_node_degrades_to_non_cn(self):
        result = platform_verify.exit_country_for_node(
            {"country": "US"}, "RandomProxy-01"
        )
        self.assertTrue(result["passed"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["group"], "其他节点")

    def test_missing_selected_node_degrades_to_non_cn(self):
        result = platform_verify.exit_country_for_node({"country": "HK"}, None)
        self.assertTrue(result["passed"])
        self.assertFalse(result["verified"])

    def test_unknown_leaf_node_with_cn_exit_fails(self):
        result = platform_verify.exit_country_for_node(
            {"country": "CN"}, "RandomProxy-01"
        )
        self.assertFalse(result["passed"])


class SimpleCheckTest(unittest.TestCase):
    def test_http_ok(self):
        self.assertTrue(platform_verify.http_ok(204)["passed"])
        self.assertFalse(platform_verify.http_ok(200)["passed"])

    def test_ipv6_disabled(self):
        self.assertTrue(platform_verify.ipv6_disabled({"以太网": False})["passed"])
        self.assertFalse(platform_verify.ipv6_disabled({"以太网": True})["passed"])


if __name__ == "__main__":
    unittest.main()
