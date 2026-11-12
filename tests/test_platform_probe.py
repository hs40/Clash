"""平台探针纯函数测试（S2）；不访问真实网络。"""

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import platform_probe  # noqa: E402


def dns_response(txid=0x1234, answers=("198.18.0.85",), rcode=0):
    header = struct.pack("!HHHHHH", txid, 0x8180 | rcode, 1, len(answers), 0, 0)
    question = b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)
    body = b""
    for value in answers:
        body += b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4)
        body += bytes(int(part) for part in value.split("."))
    return header + question + body


class DnsTest(unittest.TestCase):
    def test_build_query_has_header_and_question(self):
        query = platform_probe.build_dns_query("example.com", txid=0x1234)
        self.assertEqual(struct.unpack("!H", query[:2])[0], 0x1234)
        self.assertEqual(query[-4:], struct.pack("!HH", 1, 1))

    def test_parse_fake_ip_answer(self):
        result = platform_probe.parse_dns_response(dns_response())
        self.assertEqual(result["rcode"], 0)
        self.assertEqual(result["answers"], ["198.18.0.85"])
        self.assertTrue(platform_probe.is_fake_ip(result["answers"][0]))

    def test_parse_rcode(self):
        result = platform_probe.parse_dns_response(dns_response(answers=(), rcode=3))
        self.assertEqual(result["rcode"], 3)
        self.assertEqual(result["answers"], [])

    def test_invalid_response_is_rejected(self):
        with self.assertRaises(platform_probe.ProbeError):
            platform_probe.parse_dns_response(b"short")


class RegionTest(unittest.TestCase):
    def test_region_country_mapping(self):
        self.assertEqual(platform_probe.country_for_region("美国节点"), {"US"})
        self.assertIsNone(platform_probe.country_for_region("其他节点"))
        self.assertTrue(platform_probe.region_matches_country("日本节点", "JP"))
        self.assertFalse(platform_probe.region_matches_country("日本节点", "US"))
        self.assertIsNone(platform_probe.region_matches_country("其他节点", "US"))

    def test_fake_ip_range(self):
        self.assertTrue(platform_probe.is_fake_ip("198.18.0.1"))
        self.assertFalse(platform_probe.is_fake_ip("8.8.8.8"))
        self.assertFalse(platform_probe.is_fake_ip("not-an-ip"))


class HttpTest(unittest.TestCase):
    class Response:
        def __init__(self, payload=b"", status=204):
            self.payload = payload
            self.status = status

        def read(self):
            return self.payload

        def getcode(self):
            return self.status

        def close(self):
            pass

    def test_http_status_uses_injected_opener(self):
        def opener(request, timeout):
            self.assertEqual(timeout, 1.5)
            return self.Response(status=204)

        self.assertEqual(
            platform_probe.http_status("https://example.test", timeout=1.5, opener=opener),
            204,
        )

    def test_public_ip_info_parses_json(self):
        def opener(request, timeout):
            return self.Response(json.dumps({"ip": "203.0.113.9", "country": "jp"}).encode())

        info = platform_probe.public_ip_info(opener=opener)
        self.assertEqual(info["country"], "JP")
        self.assertEqual(info["ip"], "203.0.113.9")

    def test_public_ip_info_rejects_missing_ip(self):
        def opener(request, timeout):
            return self.Response(b"{}")

        with self.assertRaises(platform_probe.ProbeError):
            platform_probe.public_ip_info(opener=opener)


if __name__ == "__main__":
    unittest.main()
