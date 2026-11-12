#!/usr/bin/env python3
"""Apply the local dsh-pocket mobile-layout compatibility patch.

The patch is intentionally local: it edits a dsh-pocket client bundle that
lives outside this repository.  Nothing here touches Clash configuration,
credentials, or the network.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_CLIENT = (
    Path.home()
    / ".dsh"
    / "profiles"
    / "desktop"
    / "node_modules"
    / "dsh-pocket"
    / "client"
    / "client.js"
)

OLD_DRAWER = """var DRAWER_SELECTOR = '[data-mobile-nav="frame"] > :first-child';"""
NEW_DRAWER = """var DRAWER_SELECTOR = '[data-mobile-nav="frame"] > [class*="_sidebarCol"]';"""
OLD_TOGGLE = """var TOGGLE_SELECTOR = '[data-mobile-nav="toggle"]';"""
NEW_TOGGLE = """var TOGGLE_SELECTOR = '[data-mobile-nav="toggle"], [data-sidebar-opener]';"""
BROKEN_TOGGLE = """var TOGGLE_SELECTOR = '[data-mobile-nav="toggle"], [data-sidebar-opener"]';"""

OLD_CENTER = '[data-mobile-nav="frame"] > :nth-child(2) {'
NEW_CENTER = '[data-mobile-nav="frame"] > [class*="_centerCol"] {'
OLD_SIDEBAR = '[data-mobile-nav="frame"] > :first-child {'
NEW_SIDEBAR = '[data-mobile-nav="frame"] > [class*="_sidebarCol"] {'
OLD_EXPANDED = (
    '[data-mobile-nav="frame"]:not([data-sidebar-collapsed]) > :first-child {'
)
NEW_EXPANDED = (
    '[data-mobile-nav="frame"]:not([data-sidebar-collapsed]) > [class*="_sidebarCol"] {'
)
MASK_RULE = '[data-mobile-nav="frame"] > [data-sidebar-mask] {'

REPLACEMENTS = (
    ("DRAWER_SELECTOR", OLD_DRAWER, NEW_DRAWER),
    ("TOGGLE_SELECTOR", OLD_TOGGLE, NEW_TOGGLE),
    ("center column CSS", OLD_CENTER, NEW_CENTER),
    ("drawer CSS", OLD_SIDEBAR, NEW_SIDEBAR),
    ("expanded drawer CSS", OLD_EXPANDED, NEW_EXPANDED),
)

DRAWER_TAIL = (
    '  border-right: none !important;',
    '  }',
    '',
    '  [data-mobile-nav="frame"] > [data-sidebar-mask] {',
    '    display: none !important;',
    '  }',
    '',
    '  /* Expanded state (frame without data-sidebar-collapsed) slides the drawer in.',
)


class PatchError(RuntimeError):
    """The bundle is not the expected dsh-pocket layout."""


def _newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def is_patched(text: str) -> bool:
    """Return True when every selector and the mask rule are present."""
    markers = (NEW_DRAWER, NEW_TOGGLE, NEW_CENTER, NEW_SIDEBAR, NEW_EXPANDED, MASK_RULE)
    return all(marker in text for marker in markers)


def patch_client(text: str) -> str:
    """Return patched bundle text, or the input when already patched."""
    if is_patched(text):
        return text

    # Repair a bundle produced by the first local patch, which wrote an
    # invalid [data-sidebar-opener"] selector.
    if text.count(BROKEN_TOGGLE) == 1:
        repaired = text.replace(BROKEN_TOGGLE, NEW_TOGGLE, 1)
        if is_patched(repaired):
            return repaired
        raise PatchError(
            "partial dsh-pocket patch: broken toggle selector without the other markers"
        )

    for label, old, _new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            raise PatchError(
                "unsupported dsh-pocket layout: expected exactly one %s marker, found %d"
                % (label, count)
            )

    result = text
    for _label, old, new in REPLACEMENTS:
        result = result.replace(old, new, 1)

    newline = _newline_for(result)
    tail = newline.join(DRAWER_TAIL)
    anchor = newline.join(
        [
            '  border-right: none !important;',
            '  }',
            '',
            '  /* Expanded state (frame without data-sidebar-collapsed) slides the drawer in.',
        ]
    )
    count = result.count(anchor)
    if count != 1:
        raise PatchError(
            "unsupported dsh-pocket layout: expected exactly one drawer tail marker, found %d"
            % count
        )
    result = result.replace(anchor, tail, 1)

    if not is_patched(result):
        raise PatchError("patch was applied but verification markers are missing")
    return result


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PatchError("cannot read %s: %s" % (path, exc)) from exc
    except UnicodeDecodeError as exc:
        raise PatchError("%s is not UTF-8: %s" % (path, exc)) from exc


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def default_backup(path: Path) -> Path:
    return path.with_name(path.name + ".pre-dsh-pocket-patch.bak")


def apply_patch(
    path: Path, backup_path: Path | None = None, force: bool = False
) -> tuple[str, Path | None]:
    """Patch *path* and return (status, backup path)."""
    path = path.resolve()
    text = _read(path)
    if is_patched(text):
        return "already-patched", None
    patched = patch_client(text)

    backup = (backup_path or default_backup(path)).resolve()
    if backup.exists() and not force:
        raise PatchError(
            "backup already exists: %s (use --force to overwrite)" % backup
        )
    try:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    except OSError as exc:
        raise PatchError("cannot create backup %s: %s" % (backup, exc)) from exc

    _write_atomic(path, patched)
    return "patched", backup


def restore_patch(path: Path, backup_path: Path | None = None) -> Path:
    """Restore *path* from its backup and return the backup path."""
    path = path.resolve()
    backup = (backup_path or default_backup(path)).resolve()
    if not backup.exists():
        raise PatchError("backup not found: %s" % backup)
    backup_text = _read(backup)
    if is_patched(backup_text):
        raise PatchError("backup is already patched: %s" % backup)
    for label, old, _new in REPLACEMENTS:
        count = backup_text.count(old)
        if count != 1:
            raise PatchError(
                "backup is not the expected layout: %s marker count is %d"
                % (label, count)
            )
    try:
        shutil.copy2(backup, path)
    except OSError as exc:
        raise PatchError("cannot restore %s: %s" % (path, exc)) from exc
    return backup


def node_check(path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        raise PatchError("node is not available; cannot run --node-check")
    completed = subprocess.run(
        [node, "--check", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        raise PatchError(
            "node --check failed (exit %d): %s"
            % (completed.returncode, detail[-1] if detail else "no output")
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_CLIENT)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--node-check", action="store_true")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="report patch status")
    action.add_argument("--apply", action="store_true", help="apply the patch")
    action.add_argument("--restore", action="store_true", help="restore from backup")
    args = parser.parse_args(argv)

    if not (args.check or args.apply or args.restore):
        args.check = True

    try:
        if args.check:
            text = _read(args.file)
            if is_patched(text):
                print("dsh-pocket client: patched")
                return 0
            try:
                repaired = patch_client(text)
            except PatchError as exc:
                print("dsh-pocket client: unsupported layout: %s" % exc, file=sys.stderr)
                return 2
            if BROKEN_TOGGLE in text and repaired != text:
                print("dsh-pocket client: needs repair (known toggle selector typo)")
                return 1
            print("dsh-pocket client: not patched")
            return 1

        if args.apply:
            status, backup = apply_patch(args.file, args.backup, args.force)
            if args.node_check:
                node_check(args.file)
            if status == "already-patched":
                print("dsh-pocket client: already patched")
            else:
                print("dsh-pocket client: patched; backup=%s" % backup)
            return 0

        backup = restore_patch(args.file, args.backup)
        if args.node_check:
            node_check(args.file)
        print("dsh-pocket client: restored; backup=%s" % backup)
        return 0
    except PatchError as exc:
        print("dsh-pocket patch failed: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
