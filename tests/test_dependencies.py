"""ENG-05 依赖锁定测试（接缝：validate_requirements）。"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_dependencies  # noqa: E402

HASH_A = "a" * 64
HASH_B = "b" * 64


class ValidateRequirementsTest(unittest.TestCase):
    def validate(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requirements.txt"
            path.write_text(text, encoding="utf-8")
            return check_dependencies.validate_requirements(path)

    def assert_error(self, text, fragment):
        with self.assertRaises(check_dependencies.RequirementError) as ctx:
            self.validate(text)
        self.assertIn(fragment, str(ctx.exception))

    def test_actual_requirements_are_pinned_and_hashed(self):
        packages = check_dependencies.validate_requirements(ROOT / "requirements.txt")
        self.assertIn("PyYAML==6.0.3", packages)
        self.assertEqual(len(packages), 1)

    def test_unpinned_requirement_is_rejected(self):
        self.assert_error("PyYAML\n", "精确版本")

    def test_missing_hash_is_rejected(self):
        self.assert_error("PyYAML==6.0.3\n", "哈希")

    def test_malformed_hash_is_rejected(self):
        self.assert_error(
            "PyYAML==6.0.3 --hash=sha256:abc\n", "哈希"
        )

    def test_duplicate_requirement_is_rejected(self):
        self.assert_error(
            "PyYAML==6.0.3 --hash=sha256:%s\nPyYAML==6.0.3 --hash=sha256:%s\n"
            % (HASH_A, HASH_B),
            "重复",
        )

    def test_continuation_and_multiple_hashes_are_accepted(self):
        packages = self.validate(
            "# 注释\n"
            "PyYAML==6.0.3 \\\n"
            "    --hash=sha256:%s \\\n"
            "    --hash=sha256:%s\n" % (HASH_A, HASH_B)
        )
        self.assertEqual(packages, ["PyYAML==6.0.3"])


if __name__ == "__main__":
    unittest.main()
