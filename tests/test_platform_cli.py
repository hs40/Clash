"""S1：平台 CLI 的子进程契约。"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "platform.py"


class CliTest(unittest.TestCase):
    def run_cli(self, *args, stdin=subprocess.DEVNULL):
        state = Path(tempfile.mkdtemp(prefix="clash-platform-state-")) / "state"
        env = os.environ.copy()
        env.update({
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "CLASH_PLATFORM_STATE": str(state),
        })
        env.pop("CLASH_NODE_SOURCE", None)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            stdin=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(ROOT),
            timeout=30,
        )
        return completed, state

    def test_help_exits_zero(self):
        completed, _ = self.run_cli("--help")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("usage", completed.stdout.lower())

    def test_unknown_platform_is_argument_error(self):
        completed, _ = self.run_cli("plan", "--platform", "router")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("invalid choice", completed.stderr.lower())

    def test_unknown_command_is_argument_error(self):
        completed, _ = self.run_cli("destroy", "--platform", "windows")
        self.assertEqual(completed.returncode, 2)

    def test_default_command_is_plan_and_writes_nothing(self):
        completed, state = self.run_cli("--platform", "openclash")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--node-source", completed.stderr)
        self.assertFalse(state.exists())

    def test_deploy_without_apply_exits_4(self):
        completed, state = self.run_cli("deploy", "--platform", "windows")
        self.assertEqual(completed.returncode, 4)
        self.assertIn("--apply", completed.stderr)
        self.assertFalse(state.exists())

    def test_deploy_without_confirmation_exits_4_before_side_effects(self):
        completed, state = self.run_cli("deploy", "--platform", "windows", "--apply")
        self.assertEqual(completed.returncode, 4)
        self.assertIn("--yes", completed.stderr)
        self.assertFalse(state.exists())

    def test_yes_skips_prompt_and_reaches_plan(self):
        completed, state = self.run_cli(
            "deploy", "--platform", "openclash", "--apply", "--yes",
            "--node-source", str(ROOT / "missing-node-source.yaml"),
        )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertNotEqual(completed.returncode, 4)
        self.assertIn("节点来源", completed.stderr)
        self.assertFalse(state.exists())

    def test_rollback_requires_backup_dir(self):
        completed, state = self.run_cli("rollback", "--platform", "windows", "--yes")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--backup-dir", completed.stderr)
        self.assertFalse(state.exists())

    def test_openclash_plan_requires_node_source(self):
        completed, state = self.run_cli("plan", "--platform", "openclash")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("CLASH_NODE_SOURCE", completed.stderr)
        self.assertFalse(state.exists())


import argparse
import importlib.util
import io
from unittest import mock

from scripts import platform_diff


def load_platform_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("platform_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeployFlowTest(unittest.TestCase):
    def test_no_change_deploy_stops_without_confirmation_or_state(self):
        cli = load_platform_module()
        summary = platform_diff.summarize_config({}, {})
        plan = {"summary": summary, "diff": "配置内容无变化\n"}
        args = argparse.Namespace(
            platform="windows",
            apply=True,
            yes=True,
            state=str(Path(tempfile.mkdtemp(prefix="clash-platform-state-")) / "state"),
            json=False,
            diff=False,
            appdir=None,
            mihomo=None,
            workdir=None,
            profile=None,
            node_source=None,
            backup_dir=None,
            root=str(ROOT),
        )
        parser = argparse.ArgumentParser()
        with mock.patch.object(cli, "_make_plan", return_value=plan), \
                mock.patch.object(cli.platform_state, "create_run") as create_run, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            code = cli.cmd_deploy(args, parser)
        self.assertEqual(code, 0)
        create_run.assert_not_called()
        self.assertIn("没有需要变更", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
