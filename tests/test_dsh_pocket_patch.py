import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import dsh_pocket_patch as patch  # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "dsh_pocket_patch.py"

FIXTURE = textwrap.dedent(
    """\
    var DRAWER_SELECTOR = '[data-mobile-nav="frame"] > :first-child';
    var TOGGLE_SELECTOR = '[data-mobile-nav="toggle"]';
    /* CSS below is intentionally plain text for the patch fixtures. */
    [data-mobile-nav="frame"] > :nth-child(2) {
      grid-column: 1 !important;
    }

    [data-mobile-nav="frame"] > :first-child {
      position: absolute !important;
      border-right: none !important;
      }

      /* Expanded state (frame without data-sidebar-collapsed) slides the drawer in. */
    [data-mobile-nav="frame"]:not([data-sidebar-collapsed]) > :first-child {
      transform: none !important;
    }
    """
)


class PatchTextTest(unittest.TestCase):
    def test_replaces_selectors_and_inserts_mask_rule(self):
        patched = patch.patch_client(FIXTURE)
        self.assertTrue(patch.is_patched(patched))
        self.assertIn(
            'DRAWER_SELECTOR = \'[data-mobile-nav="frame"] > [class*="_sidebarCol"]\'',
            patched,
        )
        self.assertIn("[data-sidebar-opener]", patched)
        self.assertIn('[data-mobile-nav="frame"] > [class*="_centerCol"] {', patched)
        self.assertIn("[data-sidebar-mask]", patched)
        self.assertNotIn('[data-mobile-nav="frame"] > :first-child {', patched)
        self.assertNotIn(":nth-child(2) {", patched)

    def test_patch_is_idempotent(self):
        patched = patch.patch_client(FIXTURE)
        self.assertEqual(patch.patch_client(patched), patched)

    def test_repairs_known_broken_toggle_selector(self):
        patched = patch.patch_client(FIXTURE)
        broken = patched.replace(
            'var TOGGLE_SELECTOR = \'[data-mobile-nav="toggle"], [data-sidebar-opener]\';',
            'var TOGGLE_SELECTOR = \'[data-mobile-nav="toggle"], [data-sidebar-opener"]\';',
        )
        self.assertFalse(patch.is_patched(broken))
        repaired = patch.patch_client(broken)
        self.assertTrue(patch.is_patched(repaired))
        self.assertNotIn('[data-sidebar-opener"]', repaired)

    def test_partial_layout_is_rejected(self):
        broken = FIXTURE.replace(
            '[data-mobile-nav="frame"] > :nth-child(2) {', "/* missing */"
        )
        with self.assertRaisesRegex(patch.PatchError, "center column CSS"):
            patch.patch_client(broken)


class PatchFileTest(unittest.TestCase):
    def test_apply_creates_backup_and_restore_round_trips(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "client.js"
            target.write_text(FIXTURE, encoding="utf-8", newline="")
            status, backup = patch.apply_patch(target)
            self.assertEqual(status, "patched")
            self.assertEqual(backup, patch.default_backup(target).resolve())
            self.assertTrue(backup.exists())
            self.assertTrue(patch.is_patched(target.read_text(encoding="utf-8")))
            self.assertEqual(backup.read_text(encoding="utf-8"), FIXTURE)

            restored = patch.restore_patch(target)
            self.assertEqual(restored, backup)
            self.assertEqual(target.read_text(encoding="utf-8"), FIXTURE)

    def test_apply_refuses_to_overwrite_existing_backup(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "client.js"
            target.write_text(FIXTURE, encoding="utf-8", newline="")
            patch.default_backup(target).write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(patch.PatchError, "backup already exists"):
                patch.apply_patch(target)
            self.assertEqual(target.read_text(encoding="utf-8"), FIXTURE)


class CommandLineTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_check_apply_restore_cycle(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "client.js"
            target.write_text(FIXTURE, encoding="utf-8", newline="")

            before = self.run_cli("--file", str(target), "--check")
            self.assertEqual(before.returncode, 1, before.stderr)

            applied = self.run_cli("--file", str(target), "--apply")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertTrue(patch.default_backup(target).exists())

            after = self.run_cli("--file", str(target), "--check")
            self.assertEqual(after.returncode, 0, after.stderr)

            restored = self.run_cli("--file", str(target), "--restore")
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), FIXTURE)

            final = self.run_cli("--file", str(target), "--check")
            self.assertEqual(final.returncode, 1, final.stderr)

    def test_unsupported_file_returns_two(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "client.js"
            target.write_text("console.log('other');", encoding="utf-8")
            result = self.run_cli("--file", str(target), "--check")
            self.assertEqual(result.returncode, 2)
            self.assertIn("unsupported layout", result.stderr)


if __name__ == "__main__":
    unittest.main()
