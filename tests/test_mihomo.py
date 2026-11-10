"""ENG-05 Mihomo 清单与二进制校验测试（接缝：S5）。"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_mihomo  # noqa: E402

MANIFEST = {
    "version": "v1.19.33",
    "url": "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.33/mihomo-windows-amd64-v1.19.33.zip",
    "archive_sha256": "6ab2180875f9f6fff8b19386d760daec257f66b45f72b3afc650634272fa837a",
    "executable": "mihomo-windows-amd64.exe",
    "executable_sha256": "1cde41cfffd3de0aedad63c0a8515e1ce5eea507e8133aed0f637d316c93800a",
}
VERSION_TEXT = (
    "Mihomo Meta v1.19.33 windows amd64 with go1.26.10 "
    "Wed Oct 21 16:40:02 UTC 2026; Use tags: with_gvisor"
)


def write_manifest(tmp, overrides=None):
    data = dict(MANIFEST)
    if overrides:
        data.update(overrides)
    path = Path(tmp) / "mihomo.yaml"
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class LoadManifestTest(unittest.TestCase):
    def load(self, overrides=None):
        with tempfile.TemporaryDirectory() as tmp:
            return check_mihomo.load_manifest(write_manifest(tmp, overrides))

    def assert_error(self, overrides, fragment):
        with self.assertRaises(check_mihomo.MihomoError) as ctx:
            self.load(overrides)
        self.assertIn(fragment, str(ctx.exception))

    def test_actual_manifest_is_pinned(self):
        manifest = check_mihomo.load_manifest(ROOT / "security" / "mihomo.yaml")
        self.assertEqual(manifest, MANIFEST)

    def test_missing_key_is_rejected(self):
        self.assert_error({"archive_sha256": None}, "archive_sha256")

    def test_unknown_key_is_rejected(self):
        self.assert_error({"unexpected": "x"}, "未登记")

    def test_version_must_have_v_prefix_and_three_parts(self):
        self.assert_error({"version": "1.19.33"}, "version")
        self.assert_error({"version": "v1.19"}, "version")

    def test_hashes_must_be_64_lowercase_hex(self):
        self.assert_error({"archive_sha256": "ABC"}, "archive_sha256")
        self.assert_error({"executable_sha256": "a" * 63}, "executable_sha256")

    def test_url_must_be_official_release(self):
        self.assert_error({"url": "https://example.com/mihomo.zip"}, "官方")


class FileHashTest(unittest.TestCase):
    def test_sha256_file_matches_known_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bin"
            path.write_bytes(b"hello")
            self.assertEqual(
                check_mihomo.sha256_file(path),
                "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
            )

    def test_verify_archive_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mihomo.zip"
            path.write_bytes(b"not the release")
            with self.assertRaises(check_mihomo.MihomoError) as ctx:
                check_mihomo.verify_archive(path, MANIFEST)
            self.assertIn("SHA-256", str(ctx.exception))

    def test_verify_executable_accepts_matching_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mihomo-windows-amd64.exe"
            data = b"fake binary"
            path.write_bytes(data)
            manifest = dict(MANIFEST, executable_sha256=sha256(data))
            self.assertEqual(check_mihomo.verify_executable(path, manifest), sha256(data))

    def test_verify_executable_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mihomo-windows-amd64.exe"
            path.write_bytes(b"fake binary")
            with self.assertRaises(check_mihomo.MihomoError) as ctx:
                check_mihomo.verify_executable(path, MANIFEST)
            self.assertIn("SHA-256", str(ctx.exception))


class VersionTest(unittest.TestCase):
    def test_parse_release_version(self):
        self.assertEqual(check_mihomo.parse_version(VERSION_TEXT), "v1.19.33")

    def test_parse_alpha_version_returns_none(self):
        self.assertIsNone(
            check_mihomo.parse_version(
                "Mihomo Meta alpha-gbc76c13 linux amd64 with go1.26.9"
            )
        )


class VerifyBinaryTest(unittest.TestCase):
    def make_binary(self, tmp):
        path = Path(tmp) / "mihomo-windows-amd64.exe"
        data = b"fake binary"
        path.write_bytes(data)
        return path, dict(MANIFEST, executable_sha256=sha256(data))

    def runner(self, returncode=0, stdout=VERSION_TEXT):
        def run(args, **kwargs):
            self.assertEqual(args[1], "-v")
            return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")

        return run

    def test_matching_version_and_hash_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, manifest = self.make_binary(tmp)
            self.assertIn(
                "v1.19.33",
                check_mihomo.verify_binary(path, manifest, runner=self.runner()),
            )

    def test_version_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, manifest = self.make_binary(tmp)
            with self.assertRaises(check_mihomo.MihomoError) as ctx:
                check_mihomo.verify_binary(
                    path,
                    manifest,
                    runner=self.runner(stdout="Mihomo Meta v1.19.32 windows amd64"),
                )
            self.assertIn("版本", str(ctx.exception))

    def test_nonzero_exit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, manifest = self.make_binary(tmp)
            with self.assertRaises(check_mihomo.MihomoError) as ctx:
                check_mihomo.verify_binary(
                    path, manifest, runner=self.runner(returncode=1)
                )
            self.assertIn("退出码", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
