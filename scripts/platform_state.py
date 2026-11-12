"""平台运行状态目录与报告保留（S2/S3 公共基础设施）。"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

DEFAULT_KEEP = 5
PLATFORMS = ("windows", "openclash")


class StateError(Exception):
    """状态目录不可用或结构不符合契约。"""


def state_dir(value=None):
    if value:
        return Path(value)
    env = os.environ.get("CLASH_PLATFORM_STATE")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise StateError("LOCALAPPDATA 未设置，无法定位平台状态目录")
    return Path(local) / "ClashPlatform"


def _platform(platform):
    if platform not in PLATFORMS:
        raise StateError("未知平台：%r" % platform)
    return platform


def _stamp(now=None):
    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S-%f")


def create_run(platform, state=None, now=None):
    """创建一次运行目录和独立备份目录；报告与备份分开保留。"""
    platform = _platform(platform)
    root = state_dir(state) / platform
    stamp = _stamp(now)
    run = root / "runs" / stamp
    backup = root / "backups" / stamp
    run.mkdir(parents=True, exist_ok=False)
    backup.mkdir(parents=True, exist_ok=False)
    return {"run": run, "backup": backup, "report": run / "report.json", "diff": run / "config.diff"}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return path


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateError("无法读取状态文件 %s：%s" % (path, exc)) from exc


def prune_runs(platform, keep=DEFAULT_KEEP, state=None):
    """只清理报告目录，保留 backups 目录，避免删除可回滚备份。"""
    platform = _platform(platform)
    if keep < 1:
        raise StateError("keep 必须 >= 1")
    runs = state_dir(state) / platform / "runs"
    if not runs.is_dir():
        return []
    candidates = sorted((p for p in runs.iterdir() if p.is_dir()), key=lambda p: p.name)
    removed = []
    for path in candidates[:-keep]:
        shutil.rmtree(path)
        removed.append(path)
    return removed


def latest_run(platform, state=None):
    platform = _platform(platform)
    runs = state_dir(state) / platform / "runs"
    if not runs.is_dir():
        return None
    candidates = sorted((p for p in runs.iterdir() if p.is_dir()), key=lambda p: p.name)
    return candidates[-1] if candidates else None
