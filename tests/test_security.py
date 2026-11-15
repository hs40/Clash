"""ENG-05 敏感信息扫描测试（接缝：scan_text / scan_repository）。"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import security_scan  # noqa: E402


class ScanTextTest(unittest.TestCase):
    def scan(self, text):
        return security_scan.scan_text(text, "sample.txt")

    def assert_finding(self, text, fragment):
        findings = self.scan(text)
        self.assertTrue(findings)
        self.assertTrue(
            any(fragment in finding for finding in findings),
            "未找到 %r：%r" % (fragment, findings),
        )

    def test_placeholder_value_is_ignored(self):
        self.assertEqual(self.scan("password: PLACEHOLDER-NOT-REAL\n"), [])

    def test_passphrase_assignment_is_detected(self):
        self.assert_finding("pass" + "phrase = 4D001452\n", "密钥")

    def test_p12_certificate_is_detected(self):
        self.assert_finding("p12 " + "= MIILuQIBAzCC\n", "密钥")

    def test_private_key_block_is_detected(self):
        self.assert_finding(
            "-----BEGIN " + "RSA PRIVATE KEY-----\n", "私钥"
        )

    def test_github_token_is_detected(self):
        self.assert_finding("gh" + "p_" + "A" * 36, "GitHub")

    def test_aws_access_key_is_detected(self):
        self.assert_finding("AKIA" + "A" * 16, "AWS")

    def test_generic_secret_assignment_is_detected(self):
        self.assert_finding(
            "api_key = " + '"' + "0123456789abcdef" + '"', "密钥"
        )

    def test_subscription_url_token_is_detected(self):
        self.assert_finding(
            "https://example.com/sub?token=" + "a" * 32, "订阅"
        )

    def test_clash_subscription_url_is_detected(self):
        self.assert_finding(
            "https://example.com/sub?clash=" + "a" * 32, "订阅"
        )


class ScanRepositoryTest(unittest.TestCase):
    def test_repository_has_no_unallowlisted_secrets(self):
        findings = security_scan.scan_repository(ROOT)
        self.assertEqual(findings, [], "\n".join(findings))


class ConfSuffixTest(unittest.TestCase):
    """QuantumultX 产物是 .conf，必须纳入仓库敏感扫描（Q3）。"""

    def test_conf_file_with_secret_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "QuanX.conf").write_text(
                "pass" + "phrase = 4D001452\n", encoding="utf-8", newline="\n"
            )
            findings = security_scan.scan_repository(root)
            self.assertTrue(
                any("QuanX.conf" in finding for finding in findings),
                findings,
            )

    def test_committed_conf_is_scanned_and_clean(self):
        path = ROOT / "quantumultx" / "QuanX.conf"
        self.assertTrue(path.is_file(), "缺少入库产物 quantumultx/QuanX.conf")
        self.assertEqual(
            security_scan.scan_text(
                path.read_text(encoding="utf-8"), "quantumultx/QuanX.conf"
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
