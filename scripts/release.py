"""ENG-06 发布包构建与校验（接缝 S3：build_release / verify_release）。

发布包只包含最终配置、第三方声明和校验和；不包含订阅、凭据或本机路径。
"""

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path

import yaml

import build

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PLATFORMS = ("windows", "openclash")
ARCHIVE_MEMBERS = (
    "config.yaml",
    "THIRD_PARTY_NOTICES.md",
    "LICENSE-metacubex.txt",
    "CONFIG-DIFF.md",
)
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class ReleaseError(Exception):
    """发布包不满足契约。"""


def normalize_version(value):
    if not isinstance(value, str):
        raise ReleaseError("版本号必须是字符串")
    normalized = value[1:] if value.startswith("v") else value
    if not VERSION_RE.match(normalized):
        raise ReleaseError("版本号必须是 SemVer 形式 X.Y.Z：%r" % value)
    return normalized


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _asset_names(version):
    return sorted("%s-%s.zip" % (platform, version) for platform in PLATFORMS)


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, members[name])


def render_release_notes(version, configs):
    lines = [
        "# Clash 配置发布 %s" % version,
        "",
        "本发布包含 Windows 与 OpenClash 两个独立配置包，均为 Mihomo/Meta 配置。",
        "",
        "## 配置摘要",
        "",
        "| 平台 | 策略组 | 规则 | Provider |",
        "| --- | ---: | ---: | ---: |",
    ]
    for platform in PLATFORMS:
        cfg = configs[platform]
        lines.append(
            "| %s | %d | %d | %d |"
            % (
                platform,
                len(cfg.get("proxy-groups", [])),
                len(cfg.get("rules", [])),
                len(cfg.get("rule-providers", {})),
            )
        )
    lines.extend(
        [
            "",
            "## 部署",
            "",
            "1. 下载对应平台的 zip 包并解压得到 `config.yaml`。",
            "2. Windows：在 Clash Verge 中导入/替换配置；TUN、IPv4-only 等运行时项由负责人按部署环境设置。",
            "3. OpenClash：在 OpenClash 中替换配置；LAN 访问与防火墙规则由运行时负责。",
            "4. `SHA256SUMS` 只覆盖两个平台 zip；下载 Release 资产后可直接在下载目录执行 `sha256sum -c SHA256SUMS`。",
            "5. 部署前查看 `CONFIG-DIFF.md`，部署后按 `docs/ROLLBACK.md` 做连通性验证。",
            "",
            "## 安全与第三方数据",
            "",
            "- 发布包不含订阅、账号、密码或任何真实凭据。",
            "- 配置内嵌锁定版本的 Provider 数据，来源和 SHA-256 见 `providers/lock.yaml`。",
            "- MetaCubeX/meta-rules-dat 数据按 GPL-3.0 分发，详见 `THIRD_PARTY_NOTICES.md` 和 `LICENSE-metacubex.txt`。",
            "",
            "## 回滚",
            "",
            "保留上一版本发布包；按 `docs/ROLLBACK.md` 独立回滚 Windows 或 OpenClash，不要跨平台覆盖。",
        ]
    )
    return "\n".join(lines) + "\n"


def _config_summary(cfg):
    groups = cfg.get("proxy-groups") or []
    return {
        "keys": sorted(cfg),
        "groups": [group.get("name") for group in groups if isinstance(group, dict)],
        "rules": list(cfg.get("rules") or []),
        "providers": sorted(cfg.get("rule-providers") or {}),
        "proxies": len(cfg.get("proxies") or []),
        "sha256": hashlib.sha256(build.dump_yaml(cfg).encode("utf-8")).hexdigest(),
    }


def _list_delta(previous, current):
    previous_set = set(previous)
    current_set = set(current)
    return [item for item in current if item not in previous_set], [
        item for item in previous if item not in current_set
    ]


def _delta_lines(label, previous, current):
    added, removed = _list_delta(previous, current)
    return [
        "- %s：%d → %d（新增 %d，删除 %d）"
        % (label, len(previous), len(current), len(added), len(removed)),
        "  - 新增：%s" % (", ".join(added[:20]) if added else "无"),
        "  - 删除：%s" % (", ".join(removed[:20]) if removed else "无"),
    ]


def render_config_diff(version, configs, previous=None):
    """生成中文配置差异报告；previous 为上一版本的配置映射。"""
    lines = ["# 配置差异报告 %s" % version, ""]
    if previous is None:
        lines.append("未找到上一版本；本报告只记录当前版本摘要。")
    else:
        lines.append("上一版本：%s" % previous["version"])
    lines.append("")
    for platform in PLATFORMS:
        current = _config_summary(configs[platform])
        lines.append("## %s" % platform)
        lines.append("")
        lines.append("- SHA-256：%s" % current["sha256"])
        lines.append("- 顶层键：%s" % ", ".join(current["keys"]))
        lines.append("- 策略组：%d 个" % len(current["groups"]))
        lines.append("- 规则：%d 条" % len(current["rules"]))
        lines.append("- Provider：%s" % ", ".join(current["providers"]))
        lines.append("- 节点数：%d" % current["proxies"])
        if previous is not None:
            old = previous["configs"].get(platform)
            if old is None:
                lines.append("- 上一版本缺少该平台配置，无法比较。")
            else:
                old_summary = _config_summary(old)
                lines.extend(_delta_lines("策略组", old_summary["groups"], current["groups"]))
                lines.extend(_delta_lines("规则", old_summary["rules"], current["rules"]))
                lines.extend(_delta_lines("Provider", old_summary["providers"], current["providers"]))
                added_keys = sorted(set(current["keys"]) - set(old_summary["keys"]))
                removed_keys = sorted(set(old_summary["keys"]) - set(current["keys"]))
                lines.append("- 顶层键新增：%s" % (", ".join(added_keys) if added_keys else "无"))
                lines.append("- 顶层键删除：%s" % (", ".join(removed_keys) if removed_keys else "无"))
                if old_summary["sha256"] == current["sha256"]:
                    lines.append("- 配置内容无变化。")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_previous(out, version):
    out = Path(out)
    if not out.is_dir():
        return None
    current = tuple(int(part) for part in version.split("."))
    candidates = []
    for path in out.iterdir():
        if not path.is_dir() or not VERSION_RE.match(path.name):
            continue
        numbers = tuple(int(part) for part in path.name.split("."))
        if numbers < current:
            candidates.append((numbers, path))
    if not candidates:
        return None
    _numbers, directory = max(candidates)
    configs = {}
    for platform in PLATFORMS:
        path = directory / platform / "config.yaml"
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict):
            configs[platform] = data
    return {"version": directory.name, "configs": configs}


def build_release(version, root=ROOT, out=None):
    """构建发布目录，返回版本、目录和文件哈希列表。"""
    version = normalize_version(version)
    root = Path(root)
    version_file = root / "VERSION"
    try:
        declared = version_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ReleaseError("无法读取 VERSION：%s" % exc)
    if declared != version:
        raise ReleaseError("VERSION 必须与发布版本一致：%r != %r" % (declared, version))
    out = Path(out) if out is not None else root / "dist" / "release"
    target = out / version
    previous = _load_previous(out, version)
    target.mkdir(parents=True, exist_ok=True)

    try:
        configs = {
            platform: build.build_platform(platform, root) for platform in PLATFORMS
        }
    except build.ConfigError as exc:
        raise ReleaseError("构建配置失败：%s" % exc)

    notice = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    license_text = (root / "providers" / "LICENSE-metacubex.txt").read_text(
        encoding="utf-8"
    )
    (target / "THIRD_PARTY_NOTICES.md").write_text(
        notice, encoding="utf-8", newline="\n"
    )
    (target / "LICENSE-metacubex.txt").write_text(
        license_text, encoding="utf-8", newline="\n"
    )
    diff_text = render_config_diff(version, configs, previous)
    (target / "CONFIG-DIFF.md").write_text(diff_text, encoding="utf-8", newline="\n")

    files = []
    for platform in PLATFORMS:
        text = build.dump_yaml(configs[platform])
        config_path = target / platform / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(text, encoding="utf-8", newline="\n")
        archive_path = target / ("%s-%s.zip" % (platform, version))
        _write_zip(
            archive_path,
            {
                "config.yaml": text,
                "THIRD_PARTY_NOTICES.md": notice,
                "LICENSE-metacubex.txt": license_text,
                "CONFIG-DIFF.md": diff_text,
            },
        )
        files.extend([config_path, archive_path])

    notes_path = target / "RELEASE-NOTES.md"
    notes_path.write_text(
        render_release_notes(version, configs), encoding="utf-8", newline="\n"
    )
    files.append(notes_path)

    relative_files = sorted(
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    # SHA256SUMS 只覆盖实际上传到 GitHub Release 的资产（两个平台 zip）。
    # 发布目录中的其他文件由 verify_release 做结构校验，并作为 zip 内嵌副本核对。
    summaries = []
    for name in _asset_names(version):
        path = target / name
        summaries.append("%s  %s" % (_sha256(path), name))
    sums_path = target / "SHA256SUMS"
    sums_path.write_text("\n".join(summaries) + "\n", encoding="utf-8", newline="\n")

    return {
        "version": version,
        "directory": str(target),
        "files": [{"path": relative, "sha256": _sha256(target / relative)}
                  for relative in relative_files],
    }


def _parse_sums(path):
    entries = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseError("无法读取 SHA256SUMS：%s" % exc)
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split("  ")
        if len(parts) != 2:
            raise ReleaseError("SHA256SUMS 第 %d 行格式错误" % number)
        digest, relative = parts
        if not SHA256_RE.match(digest):
            raise ReleaseError("SHA256SUMS 第 %d 行哈希格式错误" % number)
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ReleaseError("SHA256SUMS 第 %d 行路径不合法" % number)
        if relative in entries:
            raise ReleaseError("SHA256SUMS 第 %d 行重复：%s" % (number, relative))
        entries[relative] = digest
    if not entries:
        raise ReleaseError("SHA256SUMS 为空")
    return entries


def verify_release(directory):
    """校验发布目录的校验和、包内容与配置结构。"""
    directory = Path(directory)
    if not directory.is_dir():
        raise ReleaseError("发布目录不存在：%s" % directory)
    sums_path = directory / "SHA256SUMS"
    entries = _parse_sums(sums_path)
    assets = set(_asset_names(directory.name))
    if set(entries) != assets:
        missing_assets = sorted(assets - set(entries))
        extra_assets = sorted(set(entries) - assets)
        details = []
        if missing_assets:
            details.append("缺少 " + ", ".join(missing_assets))
        if extra_assets:
            details.append("包含非发布资产 " + ", ".join(extra_assets))
        raise ReleaseError("SHA256SUMS 资产覆盖不正确：%s" % "；".join(details))
    for name in sorted(assets):
        path = directory / name
        if not path.is_file():
            raise ReleaseError("SHA256SUMS 指向不存在的文件：%s" % name)
        if _sha256(path) != entries[name]:
            raise ReleaseError("SHA-256 不匹配：%s" % name)

    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    }
    expected = {
        "SHA256SUMS",
        "RELEASE-NOTES.md",
        "THIRD_PARTY_NOTICES.md",
        "LICENSE-metacubex.txt",
        "CONFIG-DIFF.md",
    }
    for platform in PLATFORMS:
        expected.add("%s/config.yaml" % platform)
        expected.add("%s-%s.zip" % (platform, directory.name))
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise ReleaseError("发布包缺少文件：%s" % ", ".join(missing))
    if extra:
        raise ReleaseError("发布包包含未预期文件：%s" % ", ".join(extra))

    for name in (
        "RELEASE-NOTES.md",
        "THIRD_PARTY_NOTICES.md",
        "LICENSE-metacubex.txt",
        "CONFIG-DIFF.md",
    ):
        if name not in actual:
            raise ReleaseError("发布包缺少 %s" % name)
    for platform in PLATFORMS:
        config_path = directory / platform / "config.yaml"
        archive_path = directory / ("%s-%s.zip" % (platform, directory.name))
        if config_path.relative_to(directory).as_posix() not in actual:
            raise ReleaseError("发布包缺少 %s/config.yaml" % platform)
        if archive_path.relative_to(directory).as_posix() not in actual:
            raise ReleaseError("发布包缺少 %s" % archive_path.name)
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ReleaseError("%s/config.yaml YAML 解析失败：%s" % (platform, exc))
        if not isinstance(cfg, dict):
            raise ReleaseError("%s/config.yaml 必须是映射" % platform)
        expected_key = "mixed-port" if platform == "windows" else "port"
        if expected_key not in cfg:
            raise ReleaseError("%s/config.yaml 缺少 %s" % (platform, expected_key))
        rules = cfg.get("rules")
        if not isinstance(rules, list) or not rules or not str(rules[-1]).startswith("MATCH,"):
            raise ReleaseError("%s/config.yaml 的最后一条规则必须是 MATCH" % platform)
        if not isinstance(cfg.get("rule-providers"), dict) or not cfg["rule-providers"]:
            raise ReleaseError("%s/config.yaml 缺少 Provider" % platform)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                names = sorted(archive.namelist())
                if names != sorted(ARCHIVE_MEMBERS):
                    raise ReleaseError("%s 包含未预期文件：%s" % (archive_path.name, names))
                zipped = archive.read("config.yaml")
                zipped_diff = archive.read("CONFIG-DIFF.md")
        except zipfile.BadZipFile as exc:
            raise ReleaseError("%s 不是有效 zip：%s" % (archive_path.name, exc))
        if zipped != config_path.read_bytes():
            raise ReleaseError("%s 内 config.yaml 与发布配置不一致" % archive_path.name)
        if zipped_diff != (directory / "CONFIG-DIFF.md").read_bytes():
            raise ReleaseError("%s 内 CONFIG-DIFF.md 与发布报告不一致" % archive_path.name)
    return {"version": directory.name, "files": sorted(actual)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="构建或校验 Clash 配置发布包")
    parser.add_argument("--version", help="SemVer 版本，例如 0.1.0 或 v0.1.0")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "release")
    parser.add_argument("--verify", type=Path, help="只校验已有发布目录")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            result = verify_release(args.verify)
            print("发布包校验通过：%s" % result["version"])
            return 0
        if not args.version:
            parser.error("构建发布包时必须提供 --version")
        result = build_release(args.version, args.root, args.out)
    except (ReleaseError, build.ConfigError, OSError) as exc:
        print("发布失败：%s" % exc, file=sys.stderr)
        return 2
    print("已生成发布包：%s" % result["directory"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
