"""OpenClash 适配器测试（S3）：命令顺序、失败回滚和脱敏。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import platform_openclash  # noqa: E402
from platform_ssh import SshError  # noqa: E402


def node_source(path):
    data = {
        "proxies": [
            {"name": "香港 01", "type": "ss", "server": "203.0.113.9", "port": 443,
             "cipher": "aes-128-gcm", "password": "REAL-SECRET"},
            {"name": "坏节点", "type": "vless", "server": "203.0.113.10", "port": 443,
             "uuid": "REAL-UUID", "reality-opts": {"short-id": "12345678901234"}},
        ]
    }
    Path(path).write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                          encoding="utf-8")


class FakeSsh:
    def __init__(self, state_text="", fail=None, files=None):
        self.calls = []
        self.puts = []
        self.fail = fail or (lambda command: False)
        self.state_text = state_text
        self.files = files or {}

    def run(self, command, input_text=None, timeout=None):
        self.calls.append(command)
        if self.fail(command):
            raise SshError("boom")
        if "uci -q get openclash.config.config_path" in command:
            return self.state_text
        if "sha256sum" in command:
            return self.state_text
        if "ss -ltn" in command:
            return "yes\n"
        if "curl" in command:
            return "204\n"
        return "ok\n"

    def put_file(self, path, content):
        self.puts.append((path, content))
        return path

    def read_file(self, path):
        return self.files.get(path, "")


def builder(*args, **kwargs):
    proxies = kwargs.get("proxies") or []
    return {
        "port": 7893,
        "allow-lan": True,
        "bind-address": "*",
        "dns": {"listen": kwargs.get("dns_listen")},
        "proxies": proxies,
        "proxy-groups": [{"name": "PROXY", "type": "select"}],
        "rules": ["MATCH,PROXY"],
    }


class BuildTest(unittest.TestCase):
    def test_filters_bad_short_id_and_keeps_inline_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "FIB.yaml"
            node_source(source)
            result = platform_openclash.build_openclash_config(
                ROOT, source, builder=builder
            )
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["usable"], 1)
        self.assertEqual(result["static_bad"], ["坏节点"])
        self.assertIn("香港 01", result["text"])
        self.assertNotIn("坏节点", result["text"])
        self.assertEqual(result["config"]["dns"]["listen"], "127.0.0.1:7874")

    def test_rejects_proxy_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "FIB.yaml"
            source.write_text("proxy-providers:\n  FIB: {type: http}\n", encoding="utf-8")
            with self.assertRaises(platform_openclash.OpenClashError):
                platform_openclash.build_openclash_config(ROOT, source, builder=builder)


class PlanTest(unittest.TestCase):
    def state_text(self):
        return "\n".join([
            "CONFIG_PATH=/etc/openclash/config/FIB.yaml",
            "ENABLE=1",
            "DNS_PORT=7874",
            "NEW_EXISTS=no",
            "CURRENT_SHA=" + "a" * 64,
        ])

    def test_plan_redacts_real_nodes_and_reports_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "FIB.yaml"
            node_source(source)
            ssh = FakeSsh(
                self.state_text(),
                files={"/etc/openclash/config/FIB.yaml": yaml.safe_dump({
                    "port": 7890,
                    "proxies": [{"name": "老节点", "type": "ss",
                                 "password": "OLD-SECRET", "server": "203.0.113.8"}],
                    "proxy-groups": [{"name": "PROXY"}],
                    "rules": ["MATCH,PROXY"],
                }, allow_unicode=True)},
            )
            plan = platform_openclash.plan_openclash(ROOT, source, ssh, builder=builder)
        self.assertEqual(plan["state"]["config_path"], "/etc/openclash/config/FIB.yaml")
        self.assertEqual(plan["summary"]["proxies"]["added"], ["香港 01"])
        self.assertEqual(plan["summary"]["proxies"]["removed"], ["老节点"])
        self.assertNotIn("OLD-SECRET", plan["diff"])
        self.assertNotIn("REAL-SECRET", plan["diff"])
        self.assertEqual(plan["summary"]["files"], [platform_openclash.NEW_CONFIG])


class ApplyTest(unittest.TestCase):
    def state(self):
        return {
            "config_path": "/etc/openclash/config/FIB.yaml",
            "CURRENT_SHA": "a" * 64,
            "new_exists": False,
            "ENABLE": "1",
            "DNS_PORT": "7874",
        }

    def plan(self):
        text = "port: 7893\nrules:\n  - MATCH,PROXY\n"
        return {"built": {"text": text, "usable": 1, "static_bad": ["坏"]},
                "state": self.state(),
                "summary": {}}

    def good_fake(self):
        def fail(command):
            return False
        return FakeSsh(fail=fail)

    def test_apply_tests_before_switch_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            ssh = self.good_fake()
            result = platform_openclash.apply_openclash(
                ssh, self.plan(), Path(tmp), sleep=lambda seconds: None
            )
            manifest = json.loads((Path(tmp) / "openclash.json").read_text(encoding="utf-8"))
        commands = "\n".join(ssh.calls)
        self.assertIn("clash_meta -t -f", commands)
        self.assertLess(commands.index("-t -f"), commands.index("mv "))
        self.assertLess(commands.index("mv "), commands.index("uci set openclash.config.config_path"))
        self.assertEqual(ssh.puts[0][0], platform_openclash.TEMP_CONFIG)
        self.assertEqual(manifest["old_config_path"], "/etc/openclash/config/FIB.yaml")
        self.assertEqual(result["port"], 7893)

    def test_test_failure_restores_old_path_without_switching(self):
        def fail(command):
            return "-t -f" in command

        with tempfile.TemporaryDirectory() as tmp:
            ssh = FakeSsh(fail=fail)
            with self.assertRaises(platform_openclash.OpenClashError):
                platform_openclash.apply_openclash(
                    ssh, self.plan(), Path(tmp), sleep=lambda seconds: None
                )
            manifest = json.loads((Path(tmp) / "openclash.json").read_text(encoding="utf-8"))
        commands = "\n".join(ssh.calls)
        self.assertNotIn("mv /etc/openclash/config/.clash-platform.yaml.tmp", commands)
        self.assertIn("uci set openclash.config.config_path=/etc/openclash/config/FIB.yaml", commands)
        self.assertIn("rm -f /etc/openclash/config/clash-platform.yaml", commands)
        self.assertFalse(manifest["new_exists"])


class VerifyTest(unittest.TestCase):
    def test_checks_proxy_dns_http_and_device_curl(self):
        queried = []

        def dns(name, server):
            queried.append(server)
            return {"answers": ["198.18.0.85"]}

        result = platform_openclash.verify_openclash(
            FakeSsh(),
            http_check={"status": 204, "expected": 204, "passed": True},
            dns_query=dns,
            ip_info=lambda: {"ip": "203.0.113.9", "country": "US"},
        )
        self.assertTrue(result["passed"])
        self.assertEqual(queried, ["192.168.2.10"])
        self.assertTrue(result["device_http"]["passed"])
        self.assertTrue(result["http"]["passed"])
        self.assertTrue(result["dns"]["fake_ip"]["passed"])
        self.assertNotIn("lan", result["dns"])


class RollbackTest(unittest.TestCase):
    def test_rollback_restores_previous_file_and_uci(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup = Path(tmp) / "run"
            backup.mkdir()
            (backup / "openclash.json").write_text(json.dumps({
                "remote_backup": "/etc/openclash/platform-backups/run",
                "old_config_path": "/etc/openclash/config/FIB.yaml",
                "new_exists": True,
            }), encoding="utf-8")
            ssh = FakeSsh()
            platform_openclash.rollback_openclash(ssh, backup)
        commands = "\n".join(ssh.calls)
        self.assertIn("cp -p /etc/openclash/platform-backups/run/previous-platform.yaml", commands)
        self.assertIn("uci set openclash.config.config_path=/etc/openclash/config/FIB.yaml", commands)
        self.assertIn("/etc/init.d/openclash restart", commands)


if __name__ == "__main__":
    unittest.main()
