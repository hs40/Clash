"""ENG-03 DNS、Fake-IP 与 IPv4 测试（接缝：validate_dns + build_platform/CLI）。"""

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402


class ProductionDnsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.windows = build.build_platform("windows", ROOT)
        cls.openclash = build.build_platform("openclash", ROOT)
        cls.dns = cls.windows["dns"]

    def test_both_platforms_share_identical_dns(self):
        self.assertEqual(self.windows["dns"], self.openclash["dns"])

    def test_fake_ip_baseline(self):
        self.assertTrue(self.dns["enable"])
        self.assertEqual(self.dns["enhanced-mode"], "fake-ip")
        self.assertEqual(self.dns["fake-ip-range"], "198.18.0.1/16")
        self.assertFalse(self.dns["ipv6"])

    def test_fake_ip_filter_is_minimal_and_unique(self):
        expected = [
            "*.lan",
            "*.local",
            "+.msftconnecttest.com",
            "+.msftncsi.com",
        ]
        self.assertEqual(self.dns["fake-ip-filter"], expected)
        self.assertEqual(len(set(expected)), len(expected))

    def test_ipv4_only(self):
        self.assertIs(self.windows["ipv6"], False)
        self.assertIs(self.openclash["ipv6"], False)
        self.assertIs(self.dns["ipv6"], False)
        for server in self.dns["default-nameserver"]:
            self.assertNotIn(":", server)
        self.assertEqual(self.dns["fake-ip-range"].count(":"), 0)

    def test_nameserver_split_is_domestic_and_foreign(self):
        self.assertEqual(
            self.dns["nameserver"],
            ["https://dns.alidns.com/dns-query", "https://doh.pub/dns-query"],
        )
        self.assertEqual(
            self.dns["proxy-server-nameserver"],
            ["https://doh.pub/dns-query", "https://dns.alidns.com/dns-query"],
        )
        self.assertEqual(
            self.dns["fallback"],
            [
                "https://1.1.1.1/dns-query#PROXY",
                "https://dns.google/dns-query#PROXY",
            ],
        )
        self.assertFalse(set(self.dns["nameserver"]) & set(self.dns["fallback"]))
        self.assertEqual(self.dns["fallback-filter"], {"geoip": True, "geoip-code": "CN"})

    def test_foreign_fallback_uses_proxy_to_avoid_blocking(self):
        # 境外 DoH 直连在中国大陆会被阻断；必须经 PROXY 组查询。
        for server in self.dns["fallback"]:
            self.assertTrue(server.endswith("#PROXY"), server)

    def test_no_known_forwarding_loop(self):
        host, port = self.dns["listen"].rsplit(":", 1)
        self_references = {host + ":" + port}
        if host == "0.0.0.0":
            self_references |= {"127.0.0.1:" + port, "localhost:" + port}
        for key in ("default-nameserver", "nameserver", "proxy-server-nameserver", "fallback"):
            for server in self.dns[key]:
                for reference in self_references:
                    self.assertNotIn(reference, server, (key, server))

    def test_windows_tun_hijacks_dns(self):
        self.assertIn("any:53", self.windows["tun"]["dns-hijack"])

    def test_openclash_uses_http_port_without_tun(self):
        self.assertEqual(self.openclash["port"], 7893)
        self.assertNotIn("mixed-port", self.openclash)
        self.assertNotIn("tun", self.openclash)
        self.assertIn("dns", self.openclash)


class ValidateDnsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid = build.build_platform("windows", ROOT)["dns"]

    def assert_error(self, mutate, fragment):
        dns = copy.deepcopy(self.valid)
        mutate(dns)
        with self.assertRaises(build.ConfigError) as ctx:
            build.validate_dns(dns)
        self.assertIn(fragment, str(ctx.exception))

    def test_valid_baseline_passes(self):
        self.assertEqual(build.validate_dns(copy.deepcopy(self.valid)), self.valid)

    def test_non_mapping_is_rejected(self):
        with self.assertRaises(build.ConfigError):
            build.validate_dns([])

    def test_missing_required_key_is_rejected(self):
        for key in ("enable", "listen", "ipv6", "enhanced-mode", "fake-ip-range",
                    "fake-ip-filter", "default-nameserver", "nameserver",
                    "proxy-server-nameserver", "fallback", "fallback-filter"):
            with self.subTest(key=key):
                dns = copy.deepcopy(self.valid)
                dns.pop(key)
                with self.assertRaises(build.ConfigError) as ctx:
                    build.validate_dns(dns)
                self.assertIn(key, str(ctx.exception))

    def test_disabled_dns_is_rejected(self):
        self.assert_error(lambda dns: dns.update(enable=False), "enable")

    def test_invalid_listen_is_rejected(self):
        for value in (
            "0.0.0.0",
            "0.0.0.0:0",
            "0.0.0.0:65536",
            "dns.local:1053",
            "::1:1053",
            "[::1]:1053",
            "0.0.0.0:abc",
        ):
            with self.subTest(value=value):
                self.assert_error(lambda dns, v=value: dns.update(listen=v), "listen")

    def test_ipv6_dns_is_rejected(self):
        self.assert_error(lambda dns: dns.update(ipv6=True), "ipv6")

    def test_non_fake_ip_mode_is_rejected(self):
        self.assert_error(lambda dns: dns.update({"enhanced-mode": "redir-host"}), "enhanced-mode")

    def test_invalid_fake_ip_range_is_rejected(self):
        for value in ("not-a-network", "2001:db8::/64", "0.0.0.0/0", "198.18.0.1/31"):
            with self.subTest(value=value):
                self.assert_error(lambda dns, v=value: dns.update({"fake-ip-range": v}),
                                  "fake-ip-range")

    def test_invalid_fake_ip_filter_is_rejected(self):
        for value in ([], "*.lan", ["*.lan", "*.lan"], ["*.lan", ""]):
            with self.subTest(value=value):
                self.assert_error(lambda dns, v=value: dns.update({"fake-ip-filter": v}),
                                  "fake-ip-filter")

    def test_invalid_default_nameserver_is_rejected(self):
        for value in ([], ["dns.alidns.com"], ["2001:4860:4860::8888"],
                      ["223.5.5.5", "223.5.5.5"]):
            with self.subTest(value=value):
                self.assert_error(lambda dns, v=value: dns.update({"default-nameserver": v}),
                                  "default-nameserver")

    def test_invalid_nameserver_is_rejected(self):
        for value in ([], ["https://doh.pub/dns-query", "https://doh.pub/dns-query"],
                      ["https://[::1]/dns-query"]):
            with self.subTest(value=value):
                self.assert_error(lambda dns, v=value: dns.update(nameserver=v), "nameserver")

    def test_nameserver_and_fallback_must_not_overlap(self):
        self.assert_error(
            lambda dns: dns["fallback"].append(dns["nameserver"][0]),
            "fallback",
        )

    def test_empty_proxy_server_nameserver_is_rejected(self):
        self.assert_error(lambda dns: dns.update({"proxy-server-nameserver": []}),
                          "proxy-server-nameserver")

    def test_empty_fallback_is_rejected(self):
        self.assert_error(lambda dns: dns.update({"fallback": []}), "fallback")

    def test_fallback_filter_requires_cn_geoip(self):
        for value in (
            {"geoip": False, "geoip-code": "CN"},
            {"geoip": True, "geoip-code": "US"},
            {"geoip": True},
            "geoip",
        ):
            with self.subTest(value=value):
                self.assert_error(lambda dns, v=value: dns.update({"fallback-filter": v}),
                                  "fallback-filter")

    def test_self_referencing_nameserver_is_rejected(self):
        for value in (
            "127.0.0.1:1053",
            "https://127.0.0.1:1053/dns-query",
        ):
            with self.subTest(value=value):
                self.assert_error(lambda dns, v=value: dns.update(nameserver=[v]), "循环")


def copy_repo_configs(destination):
    shutil.copytree(ROOT / "configs", destination / "configs")
    shutil.copytree(ROOT / "providers", destination / "providers")


def replace_in_file(path, old, new):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError("fixture text not found: %r" % old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class BuildIntegrationTest(unittest.TestCase):
    def test_invalid_dns_fails_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo_configs(root)
            replace_in_file(root / "configs" / "common" / "dns.yaml",
                            "  ipv6: false", "  ipv6: true")
            with self.assertRaises(build.ConfigError) as ctx:
                build.build_platform("windows", root)
            self.assertIn("ipv6", str(ctx.exception))

    def test_dns_listen_port_collision_fails_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo_configs(root)
            replace_in_file(root / "configs" / "common" / "dns.yaml",
                            "0.0.0.0:1053", "0.0.0.0:7897")
            with self.assertRaises(build.ConfigError) as ctx:
                build.build_platform("windows", root)
            self.assertIn("冲突", str(ctx.exception))

    def test_non_ipv4_top_level_fails_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo_configs(root)
            replace_in_file(root / "configs" / "common" / "general.yaml",
                            "ipv6: false", "ipv6: true")
            with self.assertRaises(build.ConfigError) as ctx:
                build.build_platform("windows", root)
            self.assertIn("ipv6", str(ctx.exception))

    def test_windows_missing_dns_hijack_fails_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo_configs(root)
            replace_in_file(root / "configs" / "windows" / "platform.yaml",
                            '- "any:53"', '- "any:5353"')
            with self.assertRaises(build.ConfigError) as ctx:
                build.build_platform("windows", root)
            self.assertIn("dns-hijack", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
