"""ENG-05 敏感信息扫描：发现疑似凭据时只报告位置与类型，不回显内容。"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PLACEHOLDER_MARKERS = (
    "PLACEHOLDER",
    "NOT-REAL",
    "NOT_REAL",
    "EXAMPLE",
    "CHANGEME",
    "CHANGE_ME",
    "YOUR_",
    "REDACTED",
    "DUMMY",
    "FAKE",
    "<",
    ">",
)

# (报告类型, 正则，首个捕获组为待判定的值；无捕获组时整段命中即报告)
PATTERNS = (
    ("私钥", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "疑似密钥赋值",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b"
            r"\s*[:=]\s*['\"]?([^\s'\"]{8,})"
        ),
    ),
    (
        "订阅链接凭据",
        re.compile(
            r"https?://[^\s]*[?&](?:token|key|secret|sub|subscription)=([^&\s]{8,})"
        ),
    ),
    (
        "Bearer Token",
        re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/-]{20,}=*)"),
    ),
)

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
}
TEXT_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".sh",
    ".ps1",
}
TEXT_NAMES = {
    ".gitignore",
    ".gitattributes",
    "CODEOWNERS",
    "Dockerfile",
    "Makefile",
}


def _is_placeholder(value):
    upper = value.upper()
    return any(marker in upper for marker in PLACEHOLDER_MARKERS)


def scan_text(text, name="<text>"):
    """返回 ["路径:行号: 类型", ...]；不包含命中的具体内容。"""
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for label, pattern in PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(1) if pattern.groups else match.group(0)
                if pattern.groups and _is_placeholder(value):
                    continue
                findings.append("%s:%d: %s" % (name, number, label))
    return findings


def _is_scannable(path):
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES


def scan_repository(root=ROOT):
    """遍历仓库内文本文件，返回排序后的发现列表。"""
    root = Path(root)
    findings = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(
            part in SKIP_DIRS or part.startswith(".tmp_") for part in relative.parts
        ):
            continue
        if not _is_scannable(path):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_text(text, relative.as_posix()))
    return sorted(findings)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else ROOT
    findings = scan_repository(root)
    if findings:
        print("发现疑似敏感信息：", file=sys.stderr)
        for finding in findings:
            print("  " + finding, file=sys.stderr)
        return 1
    print("敏感信息扫描通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
