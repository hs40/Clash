"""ENG-05 依赖锁定校验：只允许精确版本 + SHA-256 哈希。"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIREMENT_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+!-]*)$"
)
HASH_RE = re.compile(r"^--hash=sha256:([0-9a-f]{64})$")


class RequirementError(ValueError):
    """requirements.txt 不满足锁定策略。"""


def _logical_lines(text):
    """合并反斜杠续行，忽略空行与整行注释，产出 (行号, 内容)。"""
    buffer = ""
    start = 0
    lines = text.splitlines()
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if buffer:
            line = buffer + " " + line
        else:
            start = number
        if line.endswith("\\"):
            buffer = line[:-1].rstrip()
            continue
        yield start, line
        buffer = ""
    if buffer:
        yield start, buffer


def validate_requirements(path):
    """校验文件并返回 ["name==version", ...]。"""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RequirementError("无法读取依赖文件 %s：%s" % (path, exc)) from exc

    seen = set()
    packages = []
    for number, line in _logical_lines(text):
        where = "%s:%d" % (path, number)
        tokens = line.split()
        match = REQUIREMENT_RE.match(tokens[0])
        if not match:
            raise RequirementError(
                "%s：依赖必须使用精确版本（name==version）：%r" % (where, tokens[0])
            )
        name = match.group(1)
        if name.lower() in seen:
            raise RequirementError("%s：依赖重复：%s" % (where, name))
        seen.add(name.lower())

        hashes = tokens[1:]
        if not hashes:
            raise RequirementError(
                "%s：依赖缺少 --hash=sha256 哈希：%s" % (where, tokens[0])
            )
        for token in hashes:
            if not HASH_RE.match(token):
                raise RequirementError(
                    "%s：依赖哈希格式错误（需要 64 位小写十六进制）：%r"
                    % (where, token)
                )
        packages.append("%s==%s" % (name, match.group(2)))
    return packages


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else ROOT / "requirements.txt"
    try:
        packages = validate_requirements(path)
    except RequirementError as exc:
        print("依赖校验失败：%s" % exc, file=sys.stderr)
        return 1
    for package in packages:
        print(package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
