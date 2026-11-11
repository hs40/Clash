"""ENG-06 发布包构建与校验测试（接缝 S3：build_release / verify_release）。"""

import hashlib
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import release  # noqa: E402


class ReleaseBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "release"
        cls.result = release.build_release("v0.1.0", ROOT, cls.out)
        cls.directory = Path(cls.result["directory"])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_release_directory_and_checksums(self):
        self.assertEqual(self.result["version"], "0.1.0")
        self.assertTrue((self.directory / "SHA256SUMS").is_file())
        self.assertTrue((self.directory / "RELEASE-NOTES.md").is_file())
        self.assertTrue((self.directory / "THIRD_PARTY_NOTICES.md").is_file())
        self.assertTrue((self.directory / "LICENSE-metacubex.txt").is_file())
        self.assertTrue((self.directory / "CONFIG-DIFF.md").is_file())
        for platform in ("windows", "openclash"):
            self.assertTrue((self.directory / platform / "config.yaml").is_file())
            self.assertTrue((self.directory / (platform + "-0.1.0.zip")).is_file())

    def test_verify_release_passes(self):
        result = release.verify_release(self.directory)
        self.assertEqual(result["version"], "0.1.0")
        self.assertIn("windows-0.1.0.zip", result["files"])

    def test_archive_contains_config_and_notices(self):
        for platform in ("windows", "openclash"):
            path = self.directory / (platform + "-0.1.0.zip")
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    [
                        "CONFIG-DIFF.md",
                        "LICENSE-metacubex.txt",
                        "THIRD_PARTY_NOTICES.md",
                        "config.yaml",
                    ],
                )
                self.assertEqual(
                    archive.read("config.yaml"),
                    (self.directory / platform / "config.yaml").read_bytes(),
                )

    def test_rebuild_is_byte_deterministic(self):
        before = (self.directory / "SHA256SUMS").read_bytes()
        release.build_release("0.1.0", ROOT, self.out)
        after = (self.directory / "SHA256SUMS").read_bytes()
        self.assertEqual(before, after)

    def test_config_diff_report_is_chinese_and_complete(self):
        text = (self.directory / "CONFIG-DIFF.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# 配置差异报告 0.1.0"))
        self.assertIn("未找到上一版本", text)
        for platform in ("windows", "openclash"):
            self.assertIn("## " + platform, text)
            self.assertIn("- Provider：geosite-cn, geosite-private", text)

    def test_invalid_versions_are_rejected(self):
        for value in ("0.1", "1.2.3.4", "v01.2.3", "", "release"):
            with self.subTest(value=value):
                with self.assertRaises(release.ReleaseError):
                    release.normalize_version(value)

    def test_version_file_must_match(self):
        with self.assertRaises(release.ReleaseError) as ctx:
            release.build_release("0.2.0", ROOT, Path(self._tmp.name) / "other")
        self.assertIn("VERSION", str(ctx.exception))


class ReleaseVerifyFailureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._base_tmp.name) / "release"
        release.build_release("0.1.0", ROOT, cls.base)

    @classmethod
    def tearDownClass(cls):
        cls._base_tmp.cleanup()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(self.base / "0.1.0", self.root / "release" / "0.1.0")
        self.directory = self.root / "release" / "0.1.0"

    def tearDown(self):
        self._tmp.cleanup()

    def test_tampered_config_fails_verify(self):
        path = self.directory / "windows" / "config.yaml"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(release.ReleaseError) as ctx:
            release.verify_release(self.directory)
        self.assertIn("SHA-256", str(ctx.exception))

    def test_missing_archive_fails_verify(self):
        (self.directory / "openclash-0.1.0.zip").unlink()
        with self.assertRaises(release.ReleaseError) as ctx:
            release.verify_release(self.directory)
        self.assertIn("SHA256SUMS", str(ctx.exception))

    def test_archive_config_mismatch_fails_verify(self):
        archive_path = self.directory / "windows-0.1.0.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("config.yaml", "mixed-port: 1\n")
            archive.writestr("THIRD_PARTY_NOTICES.md", "x\n")
            archive.writestr("LICENSE-metacubex.txt", "x\n")
            archive.writestr("CONFIG-DIFF.md", "x\n")
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        sums = self.directory / "SHA256SUMS"
        lines = []
        for line in sums.read_text(encoding="utf-8").splitlines():
            if line.endswith("windows-0.1.0.zip"):
                line = digest + "  windows-0.1.0.zip"
            lines.append(line)
        sums.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        with self.assertRaises(release.ReleaseError) as ctx:
            release.verify_release(self.directory)
        self.assertIn("不一致", str(ctx.exception))


class ConfigDiffPreviousVersionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configs = {
            platform: release.build.build_platform(platform, ROOT)
            for platform in ("windows", "openclash")
        }

    def test_no_change_is_reported(self):
        previous = {"version": "0.1.0", "configs": self.configs}
        text = release.render_config_diff("0.2.0", self.configs, previous)
        self.assertIn("上一版本：0.1.0", text)
        self.assertIn("配置内容无变化。", text)

    def test_added_and_removed_rules_are_reported(self):
        old_configs = {}
        for platform, cfg in self.configs.items():
            copy = dict(cfg)
            copy["rules"] = list(cfg["rules"])[:-1] + ["DOMAIN,old.example,DIRECT"]
            old_configs[platform] = copy
        previous = {"version": "0.1.0", "configs": old_configs}
        text = release.render_config_diff("0.2.0", self.configs, previous)
        self.assertIn("新增 1，删除 1", text)
        self.assertIn("MATCH,PROXY", text)
        self.assertIn("DOMAIN,old.example,DIRECT", text)


if __name__ == "__main__":
    unittest.main()
