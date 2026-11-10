"""ENG-05 敏感信息扫描测试（接缝：scan_text / scan_repository）。"""

import sys
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


class ScanRepositoryTest(unittest.TestCase):
    def test_repository_has_no_unallowlisted_secrets(self):
        findings = security_scan.scan_repository(ROOT)
        self.assertEqual(findings, [], "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
