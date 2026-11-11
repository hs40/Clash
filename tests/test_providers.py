"""ENG-06 Provider 锁与内嵌渲染测试（接缝：providers.load_provider_lock / verify_provider_snapshot）。"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import providers  # noqa: E402

COMMIT = "458e716abd80ff8c6aee2b7d15c4f94b20e9d279"
PAYLOAD = "+.example\n# comment\n\nlocal\n"


def write_lock(root, payload=PAYLOAD, **overrides):
    root = Path(root)
    snapshot = root / "providers" / "snapshots" / "geosite-private.list"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(payload, encoding="utf-8", newline="\n")
    entry = {
        "source": "metacubex",
        "commit": COMMIT,
        "upstream_path": "geo/geosite/private.list",
        "behavior": "domain",
        "snapshot": "providers/snapshots/geosite-private.list",
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "bytes": len(payload.encode("utf-8")),
    }
    entry.update(overrides)
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
    lock_path = root / "providers" / "lock.yaml"
    lock_path.write_text(
        yaml.safe_dump(lock, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    return lock, entry, snapshot


class ProviderLockTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_lock_is_loaded_and_snapshot_verified(self):
        lock, entry, snapshot = write_lock(self.root)
        loaded = providers.load_provider_lock(self.root)
        self.assertEqual(loaded["providers"]["geosite-private"]["sha256"], entry["sha256"])
        self.assertEqual(
            providers.verify_provider_snapshot(loaded["providers"]["geosite-private"], self.root),
            snapshot.resolve(),
        )

    def test_missing_lock_is_rejected(self):
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("lock.yaml", str(ctx.exception))

    def test_unknown_source_is_rejected(self):
        write_lock(self.root, source="unknown")
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("未知来源", str(ctx.exception))

    def test_source_identity_must_match_whitelist(self):
        lock, _entry, _snapshot = write_lock(self.root)
        lock["sources"]["metacubex"]["owner"] = "Other"
        (self.root / "providers" / "lock.yaml").write_text(
            yaml.safe_dump(lock, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("来源", str(ctx.exception))

    def test_source_ref_must_match_whitelist(self):
        lock, _entry, _snapshot = write_lock(self.root)
        lock["sources"]["metacubex"]["ref"] = "main"
        (self.root / "providers" / "lock.yaml").write_text(
            yaml.safe_dump(lock, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("来源", str(ctx.exception))

    def test_tampered_snapshot_is_rejected(self):
        _lock, _entry, snapshot = write_lock(self.root)
        snapshot.write_text(PAYLOAD.replace("+.example", "+.tamperr"), encoding="utf-8", newline="\n")
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("SHA-256", str(ctx.exception))

    def test_snapshot_size_mismatch_is_rejected(self):
        write_lock(self.root, bytes=1)
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("字节", str(ctx.exception))

    def test_missing_snapshot_is_rejected(self):
        _lock, _entry, snapshot = write_lock(self.root)
        snapshot.unlink()
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("不存在", str(ctx.exception))

    def test_unknown_provider_key_is_rejected(self):
        write_lock(self.root, url="https://example.invalid/list")
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("未登记的键", str(ctx.exception))

    def test_invalid_behavior_is_rejected(self):
        write_lock(self.root, behavior="mystery")
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("behavior", str(ctx.exception))

    def test_snapshot_path_traversal_is_rejected(self):
        write_lock(self.root, snapshot="../outside.list")
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.load_provider_lock(self.root)
        self.assertIn("snapshot", str(ctx.exception))

    def test_inline_render_strips_comments_and_blank_lines(self):
        write_lock(self.root)
        lock = providers.load_provider_lock(self.root)
        rendered = providers.render_rule_providers(lock, self.root)
        self.assertEqual(
            rendered,
            {
                "geosite-private": {
                    "type": "inline",
                    "behavior": "domain",
                    "payload": ["+.example", "local"],
                }
            },
        )


class ProductionProviderTest(unittest.TestCase):
    def test_production_lock_contains_private_and_cn_domain_sets(self):
        lock = providers.load_provider_lock(ROOT)
        self.assertEqual(set(lock["providers"]), {"geosite-cn", "geosite-private"})
        for name, entry in lock["providers"].items():
            with self.subTest(provider=name):
                self.assertEqual(entry["behavior"], "domain")
                self.assertEqual(entry["source"], "metacubex")
                self.assertGreater(entry["bytes"], 0)
        rendered = providers.render_rule_providers(lock)
        self.assertTrue(rendered["geosite-private"]["payload"])
        self.assertGreater(len(rendered["geosite-cn"]["payload"]), 1000)


if __name__ == "__main__":
    unittest.main()
