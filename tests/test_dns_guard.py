"""Windows 防火墙 DNS 泄漏护栏测试（接缝：规则规格 + runner 适配器）。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dns_guard  # noqa: E402


class RuleSpecTest(unittest.TestCase):
    def test_udp_rule_spec_is_exact(self):
        spec = dns_guard.rule_spec("UDP")
        self.assertEqual(spec["DisplayName"], "Clash DNS Guard - Block LAN DNS (UDP)")
        self.assertEqual(spec["Group"], "Clash DNS Guard")
        self.assertEqual(spec["Direction"], "Outbound")
        self.assertEqual(spec["Action"], "Block")
        self.assertEqual(spec["Protocol"], "UDP")
        self.assertEqual(spec["RemoteAddress"], "192.168.2.0/24")
        self.assertEqual(str(spec["RemotePort"]), "53")
        self.assertEqual(spec["Profile"], "Any")
        self.assertTrue(spec["Enabled"])

    def test_tcp_rule_spec_is_exact(self):
        spec = dns_guard.rule_spec("TCP")
        self.assertEqual(spec["Protocol"], "TCP")
        self.assertEqual(spec["DisplayName"], "Clash DNS Guard - Block LAN DNS (TCP)")

    def test_rejects_unknown_protocol(self):
        with self.assertRaises(ValueError):
            dns_guard.rule_spec("ICMP")


class FakeRunner:
    def __init__(self, status=""):
        self.status = status
        self.scripts = []

    def __call__(self, script):
        self.scripts.append(script)
        return self.status


class GuardActionsTest(unittest.TestCase):
    def test_list_rules_empty(self):
        runner = FakeRunner("")
        self.assertEqual(dns_guard.list_rules(runner=runner), [])
        self.assertEqual(len(runner.scripts), 1)
        self.assertIn("Get-NetFirewallRule", runner.scripts[0])

    def test_list_rules_propagates_runner_error(self):
        def runner(script):
            raise dns_guard.DnsGuardError("Access is denied")

        with self.assertRaises(dns_guard.DnsGuardError):
            dns_guard.list_rules(runner=runner)

    def test_apply_creates_missing_udp_and_tcp(self):
        runner = FakeRunner("")
        result = dns_guard.apply(runner=runner)
        self.assertEqual(result["created"], ["UDP", "TCP"])
        self.assertEqual(result["skipped"], [])
        self.assertEqual(len(runner.scripts), 3)
        self.assertIn("New-NetFirewallRule", runner.scripts[1])
        self.assertIn("New-NetFirewallRule", runner.scripts[2])
        self.assertIn("UDP", runner.scripts[1])
        self.assertIn("TCP", runner.scripts[2])

    def test_apply_skips_existing_rules(self):
        status = (
            '[{"DisplayName":"Clash DNS Guard - Block LAN DNS (UDP)",'
            '"Enabled":true,"Direction":"Outbound","Action":"Block",'
            '"Protocol":"UDP","RemoteAddress":"192.168.2.0/24","RemotePort":"53",'
            '"Profile":"Any"},'
            '{"DisplayName":"Clash DNS Guard - Block LAN DNS (TCP)",'
            '"Enabled":true,"Direction":"Outbound","Action":"Block",'
            '"Protocol":"TCP","RemoteAddress":"192.168.2.0/24","RemotePort":"53",'
            '"Profile":"Any"}]'
        )
        runner = FakeRunner(status)
        result = dns_guard.apply(runner=runner)
        self.assertEqual(result["created"], [])
        self.assertEqual(result["skipped"], ["UDP", "TCP"])
        self.assertEqual(len(runner.scripts), 1)

    def test_remove_removes_both_rules(self):
        runner = FakeRunner("")
        removed = dns_guard.remove(runner=runner)
        self.assertEqual(removed, ["UDP", "TCP"])
        self.assertEqual(len(runner.scripts), 2)
        self.assertIn("Remove-NetFirewallRule", runner.scripts[0])
        self.assertIn("Remove-NetFirewallRule", runner.scripts[1])


if __name__ == "__main__":
    unittest.main()
