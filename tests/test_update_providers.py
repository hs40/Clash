"""ENG-06 Provider 上游检查测试（接缝 S4：update_providers --check）。"""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_providers  # noqa: E402

COMMIT = "458e716abd80ff8c6aee2b7d15c4f94b20e9d279"
PAYLOAD = b"+.example\nlocal\n"


def write_fixture(root):
    root = Path(root)
    snapshot = root / "providers" / "snapshots" / "geosite-private.list"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(PAYLOAD)
    entry = {
        "source": "metacubex",
        "commit": COMMIT,
        "upstream_path": "geo/geosite/private.list",
        "behavior": "domain",
        "snapshot": "providers/snapshots/geosite-private.list",
        "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "bytes": len(PAYLOAD),
    }
    lock = {
        "version": 1,
        "sources": {
            "metacubex": {
                "owner": "MetaCubeX",
                "repository": "meta-rules-dat",
                "license": "GPL-3.0",
                "approval": "负责人 @hs40 2026-11-11 批准",
                "ref": "meta",
            }
        },
        "providers": {"geosite-private": entry},
    }
    (root / "providers" / "lock.yaml").write_text(
        yaml.safe_dump(lock, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    return lock


class UpstreamCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lock = write_fixture(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_unchanged_payload_is_reported_unchanged(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return PAYLOAD

        result = update_providers.check_upstream(self.lock, fetch)
        self.assertFalse(result[0]["changed"])
        self.assertEqual(result[0]["upstream_sha256"], self.lock["providers"]["geosite-private"]["sha256"])
        self.assertEqual(
            calls,
            ["https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/private.list"],
        )

    def test_changed_payload_is_reported_changed(self):
        result = update_providers.check_upstream(self.lock, lambda _url: PAYLOAD + b"+.new\n")
        self.assertTrue(result[0]["changed"])
        self.assertEqual(result[0]["upstream_bytes"], len(PAYLOAD) + 6)

    def test_fetch_failure_is_wrapped(self):
        def fetch(_url):
            raise OSError("network down")

        with self.assertRaises(update_providers.UpdateError) as ctx:
            update_providers.check_upstream(self.lock, fetch)
        self.assertIn("geosite-private", str(ctx.exception))

    def test_non_bytes_fetch_is_rejected(self):
        with self.assertRaises(update_providers.UpdateError) as ctx:
            update_providers.check_upstream(self.lock, lambda _url: "text")
        self.assertIn("非字节", str(ctx.exception))


class ApplyUpdateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lock = write_fixture(self.root)
        self.new_payload = PAYLOAD + b"+.new\n"

    def tearDown(self):
        self._tmp.cleanup()

    def test_apply_writes_snapshot_and_lock(self):
        results = update_providers.check_upstream(
            self.lock, lambda _url: self.new_payload
        )
        new_commit = "a" * 40
        updated = update_providers.apply_updates(
            self.lock, results, new_commit, self.root
        )
        self.assertEqual(updated, ["geosite-private"])
        snapshot = self.root / "providers" / "snapshots" / "geosite-private.list"
        self.assertEqual(snapshot.read_bytes(), self.new_payload)
        reloaded = update_providers.load_provider_lock(self.root)
        entry = reloaded["providers"]["geosite-private"]
        self.assertEqual(entry["commit"], new_commit)
        self.assertEqual(entry["bytes"], len(self.new_payload))
        self.assertEqual(
            entry["sha256"], hashlib.sha256(self.new_payload).hexdigest()
        )

    def test_apply_without_changes_writes_nothing(self):
        results = update_providers.check_upstream(self.lock, lambda _url: PAYLOAD)
        before = (self.root / "providers" / "lock.yaml").read_bytes()
        updated = update_providers.apply_updates(
            self.lock, results, "a" * 40, self.root
        )
        self.assertEqual(updated, [])
        self.assertEqual((self.root / "providers" / "lock.yaml").read_bytes(), before)

    def test_apply_rejects_invalid_commit(self):
        results = update_providers.check_upstream(
            self.lock, lambda _url: self.new_payload
        )
        with self.assertRaises(update_providers.UpdateError):
            update_providers.apply_updates(self.lock, results, "abc", self.root)

    def test_apply_rejects_invalid_payload_without_touching_files(self):
        results = update_providers.check_upstream(
            self.lock, lambda _url: PAYLOAD + b"bad,domain\n"
        )
        snapshot = self.root / "providers" / "snapshots" / "geosite-private.list"
        before_snapshot = snapshot.read_bytes()
        before_lock = (self.root / "providers" / "lock.yaml").read_bytes()
        with self.assertRaises(update_providers.ProviderError):
            update_providers.apply_updates(self.lock, results, "a" * 40, self.root)
        self.assertEqual(snapshot.read_bytes(), before_snapshot)
        self.assertEqual(
            (self.root / "providers" / "lock.yaml").read_bytes(), before_lock
        )


class ResolveCommitTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lock = write_fixture(self.root)
        self.new_payload = PAYLOAD + b"+.new\n"

    def tearDown(self):
        self._tmp.cleanup()

    def changed_results(self, payload=None):
        return update_providers.check_upstream(
            self.lock, lambda _url: payload or self.new_payload
        )

    def test_resolves_tracked_ref_to_commit_sha(self):
        urls = []
        sha = "b" * 40

        def fetch(url):
            urls.append(url)
            return json.dumps({"sha": sha}).encode("utf-8")

        commit = update_providers.resolve_commit(self.lock, self.changed_results(), fetch)
        self.assertEqual(commit, sha)
        self.assertEqual(
            urls,
            ["https://api.github.com/repos/MetaCubeX/meta-rules-dat/commits/meta"],
        )

    def test_rejects_non_commit_sha(self):
        def fetch(_url):
            return json.dumps({"sha": "abc"}).encode("utf-8")

        with self.assertRaises(update_providers.UpdateError) as ctx:
            update_providers.resolve_commit(self.lock, self.changed_results(), fetch)
        self.assertIn("40 位", str(ctx.exception))

    def test_rejects_unparseable_response(self):
        with self.assertRaises(update_providers.UpdateError):
            update_providers.resolve_commit(
                self.lock, self.changed_results(), lambda _url: b"not json"
            )

    def test_rejects_when_nothing_changed(self):
        results = update_providers.check_upstream(self.lock, lambda _url: PAYLOAD)
        with self.assertRaises(update_providers.UpdateError):
            update_providers.resolve_commit(self.lock, results, lambda _url: b"{}")

    def test_rejects_multiple_changed_sources(self):
        second = dict(self.lock["providers"]["geosite-private"])
        second["source"] = "other"
        self.lock["sources"]["other"] = dict(self.lock["sources"]["metacubex"])
        self.lock["providers"]["geosite-cn"] = second
        results = update_providers.check_upstream(
            self.lock, lambda _url: self.new_payload
        )
        with self.assertRaises(update_providers.UpdateError) as ctx:
            update_providers.resolve_commit(self.lock, results, lambda _url: b"{}")
        self.assertIn("多个来源", str(ctx.exception))


class ApplyCommandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lock = write_fixture(self.root)
        self.new_payload = PAYLOAD + b"+.new\n"
        self.sha = "c" * 40

    def tearDown(self):
        self._tmp.cleanup()

    def run_apply(self, argv, payload=None):
        payload = payload or self.new_payload
        stdout = io.StringIO()

        def fetch(url):
            if "api.github.com" in url:
                return json.dumps({"sha": self.sha}).encode("utf-8")
            return payload

        with mock.patch.object(update_providers, "fetch_url", side_effect=fetch):
            with contextlib.redirect_stdout(stdout):
                code = update_providers.main(
                    ["--apply", "--root", str(self.root)] + argv
                )
        return code, stdout.getvalue()

    def test_apply_resolves_commit_and_writes_branch_report(self):
        output = self.root / "report.json"
        code, text = self.run_apply(["--json", str(output)])
        self.assertEqual(code, 0)
        reloaded = update_providers.load_provider_lock(self.root)
        entry = reloaded["providers"]["geosite-private"]
        self.assertEqual(entry["commit"], self.sha)
        self.assertEqual(entry["bytes"], len(self.new_payload))
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["commit"], self.sha)
        self.assertEqual(report["branch"], "provider/update-" + self.sha[:12])
        self.assertTrue(report["changed"])
        self.assertIn("provider/update-" + self.sha[:12], text)

    def test_apply_keeps_explicit_commit(self):
        explicit = "d" * 40
        code, _text = self.run_apply(["--commit", explicit])
        self.assertEqual(code, 0)
        reloaded = update_providers.load_provider_lock(self.root)
        self.assertEqual(reloaded["providers"]["geosite-private"]["commit"], explicit)

    def test_apply_reports_error_when_commit_unresolvable(self):
        stderr = io.StringIO()

        def fetch(url):
            if "api.github.com" in url:
                return json.dumps({"sha": "bad"}).encode("utf-8")
            return self.new_payload

        with mock.patch.object(update_providers, "fetch_url", side_effect=fetch):
            with contextlib.redirect_stderr(stderr):
                code = update_providers.main(["--apply", "--root", str(self.root)])
        self.assertEqual(code, 2)
        self.assertIn("Provider 检查失败", stderr.getvalue())
        reloaded = update_providers.load_provider_lock(self.root)
        self.assertEqual(reloaded["providers"]["geosite-private"]["commit"], COMMIT)


class CheckCommandTest(unittest.TestCase):
    def test_check_with_fixture_writes_json_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = write_fixture(root)
            output = root / "provider-check.json"
            stdout = io.StringIO()
            with mock.patch.object(update_providers, "fetch_url", return_value=PAYLOAD):
                with contextlib.redirect_stdout(stdout):
                    code = update_providers.main(
                        ["--check", "--root", str(root), "--json", str(output)]
                    )
            self.assertEqual(code, 0)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(data["changed"])
            self.assertEqual(data["providers"][0]["provider"], "geosite-private")
            self.assertIn("已是最新", stdout.getvalue())
            self.assertNotIn("candidate", data["providers"][0])

    def test_check_failure_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = update_providers.main(["--check", "--root", tmp])
            self.assertEqual(code, 2)
            self.assertIn("Provider 检查失败", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
