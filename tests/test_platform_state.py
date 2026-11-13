"""平台状态目录与报告保留测试（S2）。"""

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import platform_state  # noqa: E402


class StateTest(unittest.TestCase):
    def test_create_run_separates_report_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = platform_state.create_run("windows", state=tmp, now=datetime(2026, 1, 2, 3, 4, 5))
            self.assertTrue(run["run"].is_dir())
            self.assertTrue(run["backup"].is_dir())
            self.assertIn("20260102-030405", run["run"].name)
            self.assertNotEqual(run["run"], run["backup"])

    def test_write_and_read_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            platform_state.write_json(path, {"ok": True, "节点": "示例"})
            self.assertEqual(platform_state.read_json(path)["节点"], "示例")
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))

    def test_prune_keeps_latest_five_and_keeps_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(7):
                now = datetime(2026, 1, 1) + timedelta(seconds=index)
                run = platform_state.create_run("windows", state=tmp, now=now)
                platform_state.write_json(run["report"], {"index": index})
            removed = platform_state.prune_runs("windows", keep=5, state=tmp)
            self.assertEqual(len(removed), 2)
            runs = sorted((Path(tmp) / "windows" / "runs").iterdir())
            self.assertEqual(len(runs), 5)
            backups = sorted((Path(tmp) / "windows" / "backups").iterdir())
            self.assertEqual(len(backups), 7)

    def test_unknown_platform_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(platform_state.StateError):
                platform_state.create_run("macos", state=tmp)

    def test_env_state_dir(self):
        import os
        old = os.environ.get("CLASH_PLATFORM_STATE")
        os.environ["CLASH_PLATFORM_STATE"] = "C:/tmp/clash-state"
        try:
            self.assertEqual(str(platform_state.state_dir()), "C:\\tmp\\clash-state")
        finally:
            if old is None:
                os.environ.pop("CLASH_PLATFORM_STATE", None)
            else:
                os.environ["CLASH_PLATFORM_STATE"] = old


if __name__ == "__main__":
    unittest.main()
