"""Verge 全局迁移前的节点预检测试（接缝 P1/P2）。

P1：静态过滤 reality-opts.short-id 不是 8/16 位十六进制的节点。
P2：逐节点调用 mihomo -t，发现静态规则之外的坏节点；任何预检错误都中止迁移。
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verge_preflight  # noqa: E402

MIHOMO = Path(r"C:\Program Files\Clash Verge\verge-mihomo.exe")


def node(name, **extra):
    item = {
        "name": name,
        "type": "ss",
        "server": "192.0.2.1",
        "port": 443,
        "cipher": "aes-128-gcm",
        "password": "PLACEHOLDER-NOT-REAL",
    }
    item.update(extra)
    return item


class ShortIdTest(unittest.TestCase):
    def test_missing_empty_and_valid_lengths(self):
        for value in (None, "", "0123abcd", "0123456789abcdef"):
            with self.subTest(value=value):
                self.assertTrue(verge_preflight.valid_short_id(value))

    def test_invalid_lengths_and_non_hex(self):
        for value in ("6076", "01145141919810", "zzzzzzzz", 123):
            with self.subTest(value=value):
                self.assertFalse(verge_preflight.valid_short_id(value))

    def test_filter_reports_static_bad_nodes(self):
        proxies = [
            node("good"),
            node("valid8", **{"reality-opts": {"public-key": "x", "short-id": "0123abcd"}}),
            node("bad14", **{"reality-opts": {"public-key": "x", "short-id": "01145141919810"}}),
            node("bad4", **{"reality-opts": {"public-key": "x", "short-id": "6076"}}),
        ]
        good, bad = verge_preflight.filter_bad_short_ids(proxies)
        self.assertEqual([item["name"] for item in good], ["good", "valid8"])
        self.assertEqual([item["name"] for item in bad], ["bad14", "bad4"])


class PreflightTest(unittest.TestCase):
    def write_profile(self, directory, data):
        path = Path(directory) / "profile.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return path

    def test_runtime_bad_node_is_reported(self):
        proxies = [
            node("good-1"),
            node("runtime-bad"),
            node("good-2"),
            node("bad14", **{"reality-opts": {"public-key": "x", "short-id": "01145141919810"}}),
        ]

        def fake_runner(mihomo, config, workdir):
            name = config["proxies"][0]["name"]
            if name == "runtime-bad":
                return False, "proxy 0: invalid REALITY short ID"
            return True, "test is successful"

        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, {"proxies": proxies})
            result = verge_preflight.preflight(
                path, "mihomo.exe", Path(tmp), runner=fake_runner
            )

        self.assertEqual([item["name"] for item in result["static_bad"]], ["bad14"])
        self.assertEqual(result["runtime_bad"], ["runtime-bad"])
        self.assertEqual([item["name"] for item in result["usable"]], ["good-1", "good-2"])
        self.assertEqual(result["total"], 4)

    def test_proxy_providers_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(
                tmp,
                {
                    "proxies": [node("good")],
                    "proxy-providers": {"p": {"type": "http", "url": "https://example.invalid"}},
                },
            )
            with self.assertRaises(verge_preflight.PreflightError) as ctx:
                verge_preflight.preflight(path, "mihomo.exe", Path(tmp))
        self.assertIn("proxy-providers", str(ctx.exception))

    def test_missing_proxies_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, {"rules": ["MATCH,DIRECT"]})
            with self.assertRaises(verge_preflight.PreflightError) as ctx:
                verge_preflight.preflight(path, "mihomo.exe", Path(tmp))
        self.assertIn("proxies", str(ctx.exception))

    def test_all_nodes_bad_is_reported(self):
        proxies = [node("bad", **{"reality-opts": {"public-key": "x", "short-id": "bad"}})]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, {"proxies": proxies})
            with self.assertRaises(verge_preflight.PreflightError) as ctx:
                verge_preflight.preflight(path, "mihomo.exe", Path(tmp))
        self.assertIn("没有可用节点", str(ctx.exception))

    def test_probe_config_contains_only_one_node(self):
        cfg = verge_preflight.build_probe_config([node("a")])
        self.assertEqual([item["name"] for item in cfg["proxies"]], ["a"])
        self.assertEqual(cfg["rules"], ["MATCH,PROBE"])
        self.assertEqual(cfg["proxy-groups"][0]["proxies"], ["a"])


@unittest.skipUnless(MIHOMO.is_file(), "本机没有 Verge Mihomo 内核")
class RealMihomoPreflightTest(unittest.TestCase):
    def test_good_and_bad_short_id(self):
        good = node("good")
        bad = node(
            "bad",
            type="vless",
            uuid="00000000-0000-0000-0000-000000000000",
            network="tcp",
            tls=True,
            **{"reality-opts": {"public-key": "x", "short-id": "01145141919810"}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            ok, output = verge_preflight.run_mihomo(
                MIHOMO, verge_preflight.build_probe_config([good]), Path(tmp)
            )
            self.assertTrue(ok, output)
            ok, output = verge_preflight.run_mihomo(
                MIHOMO, verge_preflight.build_probe_config([bad]), Path(tmp)
            )
            self.assertFalse(ok)
            self.assertIn("REALITY", output)
