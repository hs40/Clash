"""ENG-05 Mihomo 版本与二进制固定校验（接缝：S5）。"""

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_PREFIX = "https://github.com/MetaCubeX/mihomo/releases/download/"
MANIFEST_KEYS = (
    "version",
    "url",
    "archive_sha256",
    "executable",
    "executable_sha256",
)
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_TEXT_RE = re.compile(r"\bMihomo Meta\s+(v\d+\.\d+\.\d+)\b")


class MihomoError(ValueError):
    """Mihomo 清单或二进制不满足固定版本策略。"""


def load_manifest(path):
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise MihomoError("无法读取 Mihomo 清单 %s：%s" % (path, exc)) from exc
    if not isinstance(data, dict):
        raise MihomoError("Mihomo 清单必须是映射：%s" % path)

    for key in MANIFEST_KEYS:
        if data.get(key) in (None, ""):
            raise MihomoError("Mihomo 清单缺少字段：%s" % key)
    for key in data:
        if key not in MANIFEST_KEYS:
            raise MihomoError("Mihomo 清单存在未登记字段：%s" % key)

    version = data["version"]
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise MihomoError("Mihomo version 必须是 vX.Y.Z：%r" % version)
    for key in ("archive_sha256", "executable_sha256"):
        value = data[key]
        if not isinstance(value, str) or not HASH_RE.match(value):
            raise MihomoError(
                "Mihomo %s 必须是 64 位小写十六进制 SHA-256" % key
            )
    url = data["url"]
    if not isinstance(url, str) or not url.startswith(OFFICIAL_PREFIX):
        raise MihomoError("Mihomo url 必须指向官方 release：%r" % url)
    executable = data["executable"]
    if (
        not isinstance(executable, str)
        or not executable
        or Path(executable).name != executable
    ):
        raise MihomoError("Mihomo executable 必须是无路径的文件名：%r" % executable)
    return data


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(path, manifest):
    actual = sha256_file(path)
    if actual != manifest["archive_sha256"]:
        raise MihomoError(
            "Mihomo 压缩包 SHA-256 不匹配：期望 %s，实际 %s"
            % (manifest["archive_sha256"], actual)
        )
    return actual


def verify_executable(path, manifest):
    actual = sha256_file(path)
    if actual != manifest["executable_sha256"]:
        raise MihomoError(
            "Mihomo 可执行文件 SHA-256 不匹配：期望 %s，实际 %s"
            % (manifest["executable_sha256"], actual)
        )
    return actual


def parse_version(text):
    match = VERSION_TEXT_RE.search(text or "")
    return match.group(1) if match else None


def verify_binary(path, manifest, runner=None):
    verify_executable(path, manifest)
    runner = runner or subprocess.run
    try:
        completed = runner(
            [str(path), "-v"], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MihomoError("无法执行 Mihomo -v：%s" % exc) from exc
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise MihomoError(
            "Mihomo -v 退出码非零：%s" % completed.returncode
        )
    version = parse_version(output)
    if version is None:
        raise MihomoError("无法识别 Mihomo -v 版本：%s" % output.strip())
    if version != manifest["version"]:
        raise MihomoError(
            "Mihomo 版本不匹配：期望 %s，实际 %s"
            % (manifest["version"], version)
        )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="校验 Mihomo 清单、压缩包与二进制")
    parser.add_argument(
        "--manifest", default=str(ROOT / "security" / "mihomo.yaml")
    )
    parser.add_argument("--archive")
    parser.add_argument("--binary")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        if args.archive:
            verify_archive(args.archive, manifest)
        if args.binary:
            verify_binary(args.binary, manifest)
    except MihomoError as exc:
        print("Mihomo 校验失败：%s" % exc, file=sys.stderr)
        return 1
    print("Mihomo 校验通过：%s" % manifest["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
