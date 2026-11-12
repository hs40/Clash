"""Windows 适配器测试（S3）：命令、差异摘要和回滚边界。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import platform_windows  # noqa: E402
import verge_apply  # noqa: E402


def bindings_json(rows):
    return json.dumps(rows, ensure_ascii=False)


class Ipv6Test(unittest.TestCase):
    def fake_runner(self, calls):
        def runner(script):
            calls.append(script)
            if "Get-NetAdapter -Physical" in script:
                return bindings_json([
                    {"Name": "以太网", "Description": "Intel", "Enabled": True},
                    {"Name": "Wi-Fi", "Description": "Intel", "Enabled": False},
                ])
            return ""
        return runner

    def test_disables_only_enabled_physical_adapters(self):
        calls = []
        result = platform_windows.disable_ipv6(self.fake_runner(calls))
        self.assertEqual(result["changed"], ["以太网"])
        self.assertEqual(result["previous"], {"以太网": True, "Wi-Fi": False})
        self.assertEqual(
            [script for script in calls if "Disable-NetAdapterBinding" in script],
            ["Disable-NetAdapterBinding -Name '以太网' -ComponentID 'ms_tcpip6' -Confirm:$false"],
        )

    def test_partial_disable_failure_restores_earlier_adapter(self):
        calls = []

        def runner(script):
            calls.append(script)
            if "Get-NetAdapter -Physical" in script:
                return bindings_json([
                    {"Name": "A", "Description": "Intel", "Enabled": True},
                    {"Name": "B", "Description": "Intel", "Enabled": True},
                ])
            if "Disable-NetAdapterBinding -Name 'B'" in script:
                raise platform_windows.WindowsError("denied")
            return ""

        with self.assertRaises(platform_windows.WindowsError):
            platform_windows.disable_ipv6(runner)
        self.assertTrue(any("Enable-NetAdapterBinding -Name 'A'" in s for s in calls))

    def test_restore_only_enables_previously_enabled(self):
        calls = []
        platform_windows.restore_ipv6({"以太网": True, "Wi-Fi": False},
                                      self.fake_runner(calls))
        commands = [script for script in calls if "Enable-NetAdapterBinding" in script]
        self.assertEqual(
            commands,
            ["Enable-NetAdapterBinding -Name '以太网' -ComponentID 'ms_tcpip6' -Confirm:$false"],
        )


def runtime_config():
    return {
        "proxies": [{"name": "香港 01", "type": "ss", "password": "REAL-SECRET",
                     "server": "203.0.113.9"}],
        "proxy-groups": [{"name": "PROXY", "type": "select"}],
        "rules": ["MATCH,PROXY"],
        "mixed-port": 7890,
        "dns": {"listen": "0.0.0.0:53"},
    }


def planned_config():
    return {
        "proxies": [{"name": "香港 01", "type": "ss"}],
        "proxy-groups": [
            {"name": "PROXY", "type": "select"},
            {"name": "Google", "type": "fallback"},
        ],
        "rules": ["DOMAIN-SUFFIX,local,DIRECT", "MATCH,PROXY"],
        "mixed-port": 7897,
        "dns": {"listen": "0.0.0.0:1053"},
    }


class PlanTest(unittest.TestCase):
    def test_plan_redacts_secrets_and_reports_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = Path(tmp) / "app"
            (appdir / "profiles").mkdir(parents=True)
            (appdir / "clash-verge.yaml").write_text(
                yaml.safe_dump(runtime_config(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            before_bytes = (appdir / "clash-verge.yaml").read_bytes()
            prepare = lambda *args: {
                "merge": "profile:\n  store-selected: true\n",
                "script": "// generated\n",
                "profile_uid": "FIB",
                "profile_name": "FIB",
                "settings": {},
                "expected_proxies": 1,
                "proxy_names": ["香港 01"],
                "expected_rules": 33,
            }
            builder = lambda *args, **kwargs: planned_config()
            plan = platform_windows.plan_windows(
                appdir, ROOT, "mihomo.exe", Path(tmp), prepare=prepare,
                builder=builder, dns_list=[],
                runner=lambda script: bindings_json([
                    {"Name": "以太网", "Description": "Intel", "Enabled": True},
                ]),
            )
            self.assertEqual(plan["summary"]["proxies"]["after"], 1)
            self.assertEqual(plan["summary"]["groups"]["added"], ["Google"])
            self.assertTrue(plan["summary"]["has_changes"])
            self.assertTrue(plan["ipv6_enabled"])
            self.assertFalse(plan["dns_guard_ok"])
            self.assertNotIn("REAL-SECRET", plan["diff"])
            self.assertNotIn("203.0.113.9", plan["diff"])
            self.assertEqual(plan["verge"]["profile_uid"], "FIB")
            self.assertEqual((appdir / "clash-verge.yaml").read_bytes(), before_bytes)

    def test_diff_uses_real_proxies_and_ignores_runtime_only_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = Path(tmp) / "app"
            (appdir / "profiles").mkdir(parents=True)
            runtime = {
                "proxies": [{"name": "香港 01", "type": "vless",
                             "server": "203.0.113.9", "uuid": "REAL-SECRET"}],
                "proxy-groups": [{"name": "PROXY", "type": "select"}],
                "rules": ["MATCH,PROXY"],
                "mixed-port": 7890,
                "tun": {"enable": True, "stack": "gvisor", "device": "Mihomo"},
                "dns": {"listen": "0.0.0.0:53"},
                "redir-port": 7892,
                "external-controller": "127.0.0.1:9097",
                "secret": "REAL-SECRET",
                "unified-delay": True,
            }
            (appdir / "clash-verge.yaml").write_text(
                yaml.safe_dump(runtime, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            prepare = lambda *args: {
                "merge": "", "script": "", "profile_uid": "FIB",
                "profile_name": "FIB", "settings": {},
                "expected_proxies": 1,
                "proxy_names": ["香港 01"],
                "proxies": [{"name": "香港 01", "type": "vless",
                             "server": "203.0.113.9", "uuid": "REAL-SECRET"}],
                "expected_rules": 1,
            }
            seen = []

            def builder(platform, root, proxies=None, **kwargs):
                seen.extend(proxies or [])
                return {
                    "proxies": proxies,
                    "proxy-groups": [{"name": "PROXY", "type": "select"}],
                    "rules": ["MATCH,PROXY"],
                    "mixed-port": 7897,
                    "tun": {"enable": True, "stack": "gvisor"},
                    "dns": {"listen": "0.0.0.0:1053"},
                }

            plan = platform_windows.plan_windows(
                appdir, ROOT, "mihomo.exe", Path(tmp), prepare=prepare,
                builder=builder, dns_list=[],
                runner=lambda script: bindings_json([]),
            )
        self.assertEqual(seen[0]["type"], "vless")
        self.assertIn("mixed-port", plan["diff"])
        self.assertIn("0.0.0.0:1053", plan["diff"])
        self.assertNotIn("type: ss", plan["diff"])
        self.assertNotIn("redir-port", plan["diff"])
        self.assertNotIn("external-controller", plan["diff"])
        self.assertNotIn("device:", plan["diff"])
        self.assertNotIn("unified-delay", plan["diff"])
        self.assertNotIn("REAL-SECRET", plan["diff"])

    def test_projection_orders_groups_like_verge_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = Path(tmp) / "app"
            (appdir / "profiles").mkdir(parents=True)
            (appdir / "clash-verge.yaml").write_text(
                yaml.safe_dump(runtime_config(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            prepare = lambda *args: {
                "merge": "", "script": "", "profile_uid": "FIB",
                "profile_name": "FIB", "settings": {},
                "expected_proxies": 1, "proxy_names": ["香港 01"],
                "proxies": [{"name": "香港 01", "type": "ss"}],
                "expected_rules": 1,
            }
            common_order = ["PROXY", "自动选择", "Google", "OpenAI"]
            builder = lambda *a, **k: {
                "proxies": [{"name": "香港 01", "type": "ss"}],
                "proxy-groups": [{"name": name, "type": "select"}
                                 for name in common_order],
                "rules": ["MATCH,PROXY"],
                "mixed-port": 7897,
                "dns": {"listen": "0.0.0.0:1053"},
            }
            plan = platform_windows.plan_windows(
                appdir, ROOT, "mihomo.exe", Path(tmp), prepare=prepare,
                builder=builder, dns_list=[],
                runner=lambda script: bindings_json([]),
            )
        self.assertEqual(
            [group["name"] for group in plan["after"]["proxy-groups"]],
            ["PROXY", "Google", "OpenAI", "自动选择"],
        )

    def test_projection_keeps_google_probe_fields_from_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = Path(tmp) / "app"
            (appdir / "profiles").mkdir(parents=True)
            (appdir / "clash-verge.yaml").write_text(
                yaml.safe_dump(runtime_config(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            prepare = lambda *args: {
                "merge": "", "script": "", "profile_uid": "FIB",
                "profile_name": "FIB", "settings": {},
                "expected_proxies": 1,
                "proxies": [{"name": "香港 01", "type": "ss"}],
                "expected_rules": 1,
            }
            builder = lambda *a, **k: {
                "proxies": [{"name": "香港 01", "type": "ss"}],
                "proxy-groups": [{
                    "name": "Google", "type": "fallback",
                    "proxies": ["美国节点", "狮城节点", "日本节点", "香港节点"],
                }],
                "rules": ["MATCH,PROXY"],
                "mixed-port": 7897,
                "dns": {"listen": "0.0.0.0:1053"},
            }
            plan = platform_windows.plan_windows(
                appdir, ROOT, "mihomo.exe", Path(tmp), prepare=prepare,
                builder=builder, dns_list=[],
                runner=lambda script: bindings_json([]),
            )
        google = plan["after"]["proxy-groups"][0]
        self.assertEqual(google["url"], "https://www.gstatic.com/generate_204")
        self.assertEqual(google["interval"], 300)

    def test_plan_works_without_admin_for_dns_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = Path(tmp) / "app"
            (appdir / "profiles").mkdir(parents=True)
            (appdir / "clash-verge.yaml").write_text(
                yaml.safe_dump(runtime_config(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            prepare = lambda *args: {
                "merge": "", "script": "", "profile_uid": "FIB", "profile_name": "FIB",
                "settings": {}, "expected_proxies": 1, "proxy_names": ["香港 01"],
                "expected_rules": 33,
            }
            with mock.patch.object(
                    platform_windows.dns_guard, "list_rules",
                    side_effect=platform_windows.dns_guard.DnsGuardError("Access is denied")):
                plan = platform_windows.plan_windows(
                    appdir, ROOT, "mihomo.exe", Path(tmp), prepare=prepare,
                    builder=lambda *a, **k: planned_config(),
                    runner=lambda script: bindings_json([]),
                )
        self.assertFalse(plan["dns_guard_ok"])
        self.assertIn("Access is denied", plan["dns_guard_error"])


class StatusTest(unittest.TestCase):
    def test_status_reports_counts_ipv6_and_dns_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = Path(tmp) / "app"
            appdir.mkdir()
            path = appdir / "clash-verge.yaml"
            path.write_text(
                yaml.safe_dump(runtime_config(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            before = path.read_bytes()
            result = platform_windows.status_windows(
                appdir,
                runner=lambda script: bindings_json([
                    {"Name": "以太网", "Description": "Intel", "Enabled": True},
                    {"Name": "Wi-Fi", "Description": "Intel", "Enabled": False},
                ]),
                dns_list=[],
            )
            self.assertEqual(path.read_bytes(), before)
        self.assertTrue(result["ok"])
        self.assertEqual(result["config"]["mixed_port"], 7890)
        self.assertEqual(result["config"]["proxies"], 1)
        self.assertEqual(result["config"]["groups"], 1)
        self.assertEqual(result["config"]["rules"], 1)
        self.assertEqual(result["ipv6"], {"以太网": True, "Wi-Fi": False})
        self.assertFalse(result["dns_guard_ok"])

    def test_status_survives_dns_guard_permission_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = Path(tmp) / "app"
            appdir.mkdir()
            (appdir / "clash-verge.yaml").write_text(
                yaml.safe_dump(runtime_config(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            with mock.patch.object(
                    platform_windows.dns_guard, "list_rules",
                    side_effect=platform_windows.dns_guard.DnsGuardError("Access is denied")):
                result = platform_windows.status_windows(
                    appdir,
                    runner=lambda script: bindings_json([]),
                )
        self.assertTrue(result["ok"])
        self.assertFalse(result["dns_guard_ok"])
        self.assertIn("Access is denied", result["dns_guard_error"])


class ApplyTest(unittest.TestCase):
    def test_post_apply_ipv6_failure_restores_verge_files(self):
        reloads = []
        restored = []
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(verge_apply, "apply_migration",
                                  return_value={"profile_name": "FIB",
                                                "expected_proxies": 1,
                                                "expected_rules": 33}), \
                mock.patch.object(platform_windows, "disable_ipv6",
                                  side_effect=platform_windows.WindowsError("denied")), \
                mock.patch.object(verge_apply, "restore",
                                  side_effect=lambda *a: restored.append(a) or {"files": {}}):
            with self.assertRaises(platform_windows.WindowsError):
                platform_windows.apply_windows(
                    Path(tmp) / "app",
                    {"verge": {"merge": "", "script": ""}},
                    Path(tmp) / "backup",
                    reload=lambda: reloads.append(True),
                    runner=lambda script: "",
                )
        self.assertEqual(len(restored), 1)
        self.assertEqual(reloads, [True])


class RollbackTest(unittest.TestCase):
    def test_rollback_restores_colorings_and_removes_created_rules(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            backup = Path(tmp) / "backup"
            backup.mkdir()
            (backup / "ipv6.json").write_text(
                json.dumps({"previous": {"以太网": True, "Wi-Fi": False},
                            "changed": ["以太网"]}), encoding="utf-8")
            (backup / "dnsguard.json").write_text(
                json.dumps({"created": ["UDP"], "skipped": []}), encoding="utf-8")
            with mock.patch.object(verge_apply, "restore",
                                   return_value={"files": {"profiles.yaml": {}}}):
                result = platform_windows.rollback_windows(
                    Path(tmp) / "app", backup,
                    reload=lambda: calls.append("reload"),
                    runner=lambda script: calls.append(script) or "",
                )
        self.assertTrue(any("Enable-NetAdapterBinding" in str(c) for c in calls))
        self.assertTrue(any("Remove-NetFirewallRule" in str(c) for c in calls))
        self.assertEqual(calls[-1], "reload")
        self.assertIn("profiles.yaml", result["files"])
        self.assertEqual(result["ipv6_restored"], ["以太网"])


class ControllerTest(unittest.TestCase):
    class Response:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(self.data).encode("utf-8")

    def test_selected_name_follows_group_chain(self):
        payloads = {
            "/proxies/PROXY": {"type": "Selector", "now": "自动选择"},
            "/proxies/%E8%87%AA%E5%8A%A8%E9%80%89%E6%8B%A9": {"type": "URLTest", "now": "香港 01"},
            "/proxies/%E9%A6%99%E6%B8%AF%2001": {"type": "Shadowsocks", "now": None},
        }
        requested = []

        def opener(request, timeout):
            requested.append(request.full_url)
            path = request.full_url.split("127.0.0.1:9097", 1)[1]
            return self.Response(payloads[path])

        selected = platform_windows.selected_proxy_name(
            {"external-controller": "127.0.0.1:9097", "secret": "not-a-real-secret"},
            opener=opener,
        )
        self.assertEqual(selected["name"], "香港 01")
        self.assertEqual(selected["path"], ["PROXY", "自动选择", "香港 01"])
        self.assertEqual(len(requested), 3)


class IntegrityTest(unittest.TestCase):
    def test_parses_high_and_low_integrity_sids(self):
        self.assertEqual(
            platform_windows.parse_integrity("Mandatory Label\\High Mandatory Level S-1-16-12288"),
            "high",
        )
        self.assertEqual(
            platform_windows.parse_integrity("Mandatory Label\\Low Mandatory Level S-1-16-4096"),
            "low",
        )
        self.assertEqual(platform_windows.parse_integrity("S-1-16-8192"), "medium")
        self.assertEqual(platform_windows.parse_integrity("no label"), "unknown")

    def test_integrity_level_uses_whoami_output(self):
        class Completed:
            returncode = 0
            stdout = "Mandatory Label\\High Mandatory Level S-1-16-12288\n"

        calls = []

        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return Completed()

        self.assertEqual(platform_windows.integrity_level(runner), "high")
        self.assertEqual(calls[0][0][:2], ["whoami", "/groups"])


if __name__ == "__main__":
    unittest.main()
