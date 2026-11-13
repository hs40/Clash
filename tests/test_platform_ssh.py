"""SSH 适配器测试（S3）；fake runner，不连接真实设备。"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import platform_ssh  # noqa: E402


class FakeRunner:
    def __init__(self, outputs=None):
        self.calls = []
        self.outputs = list(outputs or [])

    def __call__(self, args, input_text, timeout):
        self.calls.append((args, input_text, timeout))
        stdout = self.outputs.pop(0) if self.outputs else ""
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


class SshRunnerTest(unittest.TestCase):
    def test_args_use_agent_and_strict_host_check(self):
        runner = platform_ssh.SshRunner(known_hosts="C:/known_hosts")
        args = runner.args("true")
        self.assertEqual(args[0], "ssh")
        self.assertIn("BatchMode=yes", args)
        self.assertIn("StrictHostKeyChecking=yes", args)
        self.assertIn("UserKnownHostsFile=C:\\known_hosts", " ".join(args).replace("\\", "\\"))
        self.assertEqual(args[-2], "root@192.168.2.10")
        self.assertNotIn("-i", args)

    def test_run_returns_stdout_and_passes_timeout(self):
        fake = FakeRunner(["ok\n"])
        runner = platform_ssh.SshRunner(runner=fake)
        self.assertEqual(runner.run("true", timeout=7), "ok\n")
        self.assertEqual(fake.calls[0][2], 7)

    def test_nonzero_exit_is_an_error(self):
        def runner(args, input_text, timeout):
            return SimpleNamespace(returncode=2, stdout="", stderr="boom")

        with self.assertRaises(platform_ssh.SshError) as ctx:
            platform_ssh.SshRunner(runner=runner).run("false")
        self.assertIn("boom", str(ctx.exception))

    def test_put_file_uses_stdin_and_quoted_path(self):
        fake = FakeRunner()
        runner = platform_ssh.SshRunner(runner=fake)
        runner.put_file("/tmp/a b.yaml", "x: 1\n")
        args, input_text, _ = fake.calls[0]
        self.assertEqual(input_text, "x: 1\n")
        self.assertIn("cat > '/tmp/a b.yaml'", args[-1])

    def test_relative_or_dotdot_path_is_rejected(self):
        runner = platform_ssh.SshRunner(runner=FakeRunner())
        for path in ("tmp/a", "/tmp/../etc/passwd", "/tmp/a\n"):
            with self.assertRaises(platform_ssh.SshError):
                runner.put_file(path, "x")

    def test_exists_returns_false_without_failing(self):
        fake = FakeRunner(["no\n"])
        runner = platform_ssh.SshRunner(runner=fake)
        self.assertFalse(runner.exists("/tmp/missing"))
        self.assertIn("if [ -f", fake.calls[0][0][-1])
        self.assertTrue(platform_ssh.SshRunner(runner=FakeRunner(["yes\n"])).exists("/tmp/x"))

    def test_sha256_parses_digest(self):
        digest = "a" * 64
        fake = FakeRunner([digest + "  /tmp/x\n"])
        self.assertEqual(platform_ssh.SshRunner(runner=fake).sha256("/tmp/x"), digest)


class SubprocessStdinTest(unittest.TestCase):
    """进程边界回归：Windows 文本模式不得把上传内容改成 CRLF。"""

    def test_subprocess_runner_preserves_lf(self):
        runner = platform_ssh.SshRunner()
        text = "a\nb\n"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        code = (
            "import sys, hashlib; "
            "sys.stdout.write(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
        )
        result = runner._subprocess_runner([sys.executable, "-c", code], text, 10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
