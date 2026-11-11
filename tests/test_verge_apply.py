"""Verge 全局迁移的应用与回滚测试（接缝 A1/A2）。

A1：apply_migration 在任何写入前完成备份，失败时恢复原文件。
A2：verify_config 只接受符合仓库 MVP 契约的生成结果。
"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verge_apply  # noqa: E402


REGIONS = ["香港节点", "台湾节点", "日本节点", "韩国节点", "狮城节点", "美国节点", "其他节点"]
GROUPS = ["PROXY", "Google", "OpenAI", "Claude", "Cursor", "自动选择"] + REGIONS


def make_config(proxies=46):
    names = ["node-%d" % i for i in range(proxies)]
    groups = [
        {"name": "PROXY", "type": "select", "proxies": ["自动选择"] + REGIONS + ["DIRECT"]},
        {"name": "Google", "type": "fallback", "proxies": ["美国节点", "狮城节点", "日本节点", "香港节点"]},
        {"name": "OpenAI", "type": "select", "proxies": ["自动选择"] + REGIONS},
        {"name": "Claude", "type": "select", "proxies": ["自动选择"] + REGIONS},
        {"name": "Cursor", "type": "select", "proxies": ["自动选择"] + REGIONS},
        {
            "name": "自动选择",
            "type": "url-test",
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
            "tolerance": 50,
            "proxies": names,
        },
    ]
    for name in REGIONS:
        groups.append({"name": name, "type": "select", "proxies": ["node-0"]})
    return {
        "mixed-port": 7897,
        "mode": "rule",
        "ipv6": False,
        "allow-lan": False,
        "tun": {"enable": True, "stack": "gvisor", "auto-route": True},
        "dns": {"listen": "0.0.0.0:1053", "enable": True},
        "proxies": [{"name": name, "type": "ss"} for name in names],
        "proxy-groups": groups,
        "rule-providers": {
            "geosite-cn": {"type": "inline"},
            "geosite-private": {"type": "inline"},
        },
        "rules": ["DOMAIN-SUFFIX,local,DIRECT"] * 25 + ["MATCH,PROXY"],
    }


def write_appdir(root):
    appdir = Path(root) / "app"
    (appdir / "profiles").mkdir(parents=True)
    (appdir / "profiles" / "Merge.yaml").write_text("old-merge: true\n", encoding="utf-8")
    (appdir / "profiles" / "Script.js").write_text("// old script\n", encoding="utf-8")
    profiles = {
        "current": "oldLocal",
        "items": [
            {"uid": "oldLocal", "type": "local", "file": "oldLocal.yaml", "option": {}},
            {"uid": "FIB", "type": "remote", "file": "FIB.yaml", "option": {}},
        ],
    }
    (appdir / "profiles.yaml").write_text(
        yaml.safe_dump(profiles, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (appdir / "profiles" / "oldLocal.yaml").write_text(
        yaml.safe_dump({"proxies": [{"name": "old"}]}), encoding="utf-8"
    )
    (appdir / "profiles" / "FIB.yaml").write_text(
        yaml.safe_dump({"proxies": [{"name": "node-0"}]}), encoding="utf-8"
    )
    (appdir / "verge.yaml").write_text(
        "enable_tun_mode: true\nenable_system_proxy: false\nverge_mixed_port: 7897\n",
        encoding="utf-8",
    )
    (appdir / "config.yaml").write_text(
        yaml.safe_dump({"mixed-port": 7897, "mode": "rule"}, sort_keys=False), encoding="utf-8"
    )
    (appdir / "clash-verge.yaml").write_text(
        yaml.safe_dump(make_config(1), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return appdir


def plan():
    return {
        "merge": "profile:\n  store-selected: true\n",
        "script": "// generated\n",
        "profile_uid": "FIB",
        "profile_name": "FIB",
        "settings": {
            "enable_tun_mode": True,
            "enable_system_proxy": False,
            "verge_mixed_port": 7897,
        },
        "expected_proxies": 46,
    }


class BackupTest(unittest.TestCase):
    def test_backup_and_restore_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = write_appdir(tmp)
            backup = Path(tmp) / "backup"
            manifest = verge_apply.backup(appdir, backup)
            self.assertIn("profiles/Merge.yaml", manifest["files"])
            self.assertEqual(
                (backup / "profiles" / "Merge.yaml").read_bytes(),
                (appdir / "profiles" / "Merge.yaml").read_bytes(),
            )
            (appdir / "profiles" / "Merge.yaml").write_text("changed\n", encoding="utf-8")
            verge_apply.restore(appdir, backup)
            self.assertEqual(
                (appdir / "profiles" / "Merge.yaml").read_text(encoding="utf-8"),
                "old-merge: true\n",
            )


class AtomicWriteTest(unittest.TestCase):
    def test_write_atomic_replaces_content_and_uses_lf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.txt"
            verge_apply.write_atomic(path, "a\r\nb\r\n")
            self.assertEqual(path.read_bytes(), b"a\nb\n")


class VerifyConfigTest(unittest.TestCase):
    def test_accepts_contract(self):
        verge_apply.verify_config(make_config(), expected_proxies=46)

    def test_rejects_wrong_rule_count(self):
        bad = make_config()
        bad["rules"].append("GEOIP,CN,DIRECT")
        with self.assertRaises(verge_apply.ApplyError):
            verge_apply.verify_config(bad, expected_proxies=46)

    def test_rejects_wrong_port(self):
        bad = make_config()
        bad["mixed-port"] = 7890
        with self.assertRaises(verge_apply.ApplyError):
            verge_apply.verify_config(bad, expected_proxies=46)

    def test_rejects_wrong_proxy_order(self):
        bad = make_config()
        bad["proxy-groups"][0]["proxies"] = ["DIRECT"]
        with self.assertRaises(verge_apply.ApplyError):
            verge_apply.verify_config(bad, expected_proxies=46)


class ApplyMigrationTest(unittest.TestCase):
    def test_writes_backs_up_switches_and_reloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = write_appdir(tmp)
            backup = Path(tmp) / "backup"
            calls = []

            def reload():
                calls.append(1)
                (appdir / "clash-verge.yaml").write_text(
                    yaml.safe_dump(make_config(46), allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )

            result = verge_apply.apply_migration(
                appdir, plan(), backup, reload=reload, verify_timeout=2, sleep=lambda _: None
            )
            self.assertTrue(result["ok"])
            self.assertEqual(calls, [1])
            self.assertEqual(
                (appdir / "profiles" / "Script.js").read_text(encoding="utf-8"),
                "// generated\n",
            )
            profiles = yaml.safe_load((appdir / "profiles.yaml").read_text(encoding="utf-8"))
            self.assertEqual(profiles["current"], "FIB")
            manifest = yaml.safe_load((backup / "manifest.yaml").read_text(encoding="utf-8"))
            self.assertIn("profiles/Script.js", manifest["files"])
            self.assertTrue((backup / "profiles" / "Script.js").is_file())

    def test_failed_verification_restores_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = write_appdir(tmp)
            backup = Path(tmp) / "backup"

            def reload():
                (appdir / "clash-verge.yaml").write_text(
                    yaml.safe_dump(make_config(1), allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )

            with self.assertRaises(verge_apply.ApplyError) as ctx:
                verge_apply.apply_migration(
                    appdir, plan(), backup, reload=reload, verify_timeout=0.1, sleep=lambda _: None
                )
            self.assertIn("回滚", str(ctx.exception))
            self.assertEqual(
                (appdir / "profiles" / "Script.js").read_text(encoding="utf-8"),
                "// old script\n",
            )
            profiles = yaml.safe_load((appdir / "profiles.yaml").read_text(encoding="utf-8"))
            self.assertEqual(profiles["current"], "oldLocal")

    def test_stale_runtime_without_regeneration_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = write_appdir(tmp)
            backup = Path(tmp) / "backup"
            before_mtime = (appdir / "clash-verge.yaml").stat().st_mtime_ns

            def reload():
                return None

            with self.assertRaises(verge_apply.ApplyError) as ctx:
                verge_apply.apply_migration(
                    appdir, plan(), backup, reload=reload, verify_timeout=0.1, sleep=lambda _: None
                )
            self.assertIn("尚未重新生成", str(ctx.exception))
            self.assertEqual((appdir / "clash-verge.yaml").stat().st_mtime_ns, before_mtime)
            self.assertEqual(
                (appdir / "profiles" / "Script.js").read_text(encoding="utf-8"),
                "// old script\n",
            )

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = write_appdir(tmp)
            before = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in appdir.rglob("*") if path.is_file()
            }
            result = verge_apply.apply_migration(appdir, plan(), None, dry_run=True)
            after = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in appdir.rglob("*") if path.is_file()
            }
            self.assertTrue(result["dry_run"])
            self.assertEqual(before, after)

    def test_missing_current_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = write_appdir(tmp)
            (appdir / "profiles.yaml").write_text("current: nope\nitems: []\n", encoding="utf-8")
            with self.assertRaises(verge_apply.ApplyError):
                verge_apply.prepare_plan(
                    appdir, ROOT, "mihomo.exe", Path(tmp), target_uid="FIB"
                )


class RestartTest(unittest.TestCase):
    def test_kills_ui_and_core_then_runs_task(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return mock.Mock(returncode=0, stdout=b"")

        with mock.patch.object(verge_apply.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(verge_apply.time, "sleep", return_value=None):
            verge_apply.restart_verge(wait=0)
        self.assertEqual(
            calls,
            [
                ["taskkill", "/IM", "clash-verge.exe", "/F"],
                ["taskkill", "/IM", "verge-mihomo.exe", "/F"],
                ["schtasks", "/Run", "/TN", "Clash Verge (Admin)"],
            ],
        )

    def test_start_failure_is_reported(self):
        def fake_run(args, **kwargs):
            if args[0] == "schtasks":
                return mock.Mock(returncode=1, stdout=b"ERROR")
            return mock.Mock(returncode=0, stdout=b"")

        with mock.patch.object(verge_apply.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(verge_apply.time, "sleep", return_value=None):
            with self.assertRaises(verge_apply.ApplyError):
                verge_apply.restart_verge(wait=0)


class SettingsTest(unittest.TestCase):
    def test_setting_restore_preserves_other_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdir = write_appdir(tmp)
            path = appdir / "verge.yaml"
            verge_apply.set_setting(path, "enable_tun_mode", False)
            text = path.read_text(encoding="utf-8")
            self.assertIn("enable_tun_mode: false", text)
            self.assertIn("verge_mixed_port: 7897", text)
            data = yaml.safe_load(text)
            self.assertFalse(data["enable_tun_mode"])


if __name__ == "__main__":
    unittest.main()
