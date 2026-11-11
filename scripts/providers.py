"""ENG-06 Provider 锁与内嵌渲染。

Provider 数据在构建时内嵌为 Mihomo 的 inline rule-provider，最终配置自包含，
不依赖运行时下载。锁文件记录固定来源、固定 commit、上游路径、字节数与 SHA-256；
构建前必须逐项校验，任何不一致都让构建失败。
"""

import hashlib
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

LOCK_RELATIVE = Path("providers") / "lock.yaml"
SNAPSHOT_ROOT = Path("providers") / "snapshots"

# 固定来源白名单。新增来源必须修改代码并由负责人审查，不能只改锁文件。
APPROVED_SOURCES = {
    "metacubex": {
        "owner": "MetaCubeX",
        "repository": "meta-rules-dat",
        "license": "GPL-3.0",
        "ref": "meta",
    },
}

SOURCE_KEYS = ("owner", "repository", "license", "approval", "ref")
PROVIDER_KEYS = (
    "source",
    "commit",
    "upstream_path",
    "behavior",
    "snapshot",
    "sha256",
    "bytes",
)
PROVIDER_BEHAVIORS = ("domain", "ipcidr", "classical")
PROVIDER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProviderError(Exception):
    """Provider 锁、快照或来源不满足契约。"""


def _error(detail):
    raise ProviderError("providers：" + detail)


def _read_mapping(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _error("无法读取 %s：%s" % (path, exc))
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        _error("%s：YAML 解析失败：%s" % (path, exc))
    if not isinstance(data, dict):
        _error("%s：顶层必须是映射" % path)
    return data


def _safe_relative(value, field):
    if not isinstance(value, str) or not value or value != value.strip():
        _error("%s 必须是非空相对路径" % field)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        _error("%s 必须是仓库内的相对路径：%r" % (field, value))
    return path


def _snapshot_path(entry, root):
    relative = _safe_relative(entry.get("snapshot"), "snapshot")
    expected_parent = SNAPSHOT_ROOT
    if relative.parts[: len(expected_parent.parts)] != expected_parent.parts:
        _error("snapshot 必须位于 %s 下：%r" % (expected_parent.as_posix(), relative.as_posix()))
    if relative.suffix != ".list":
        _error("snapshot 必须是 .list 文件：%r" % relative.as_posix())
    path = (Path(root) / relative).resolve()
    try:
        path.relative_to((Path(root) / expected_parent).resolve())
    except ValueError:
        _error("snapshot 越出快照目录：%r" % relative.as_posix())
    return path


def _validate_source(name, source):
    approved = APPROVED_SOURCES.get(name)
    if approved is None:
        _error("未知来源 %r（白名单：%s）" % (name, ", ".join(sorted(APPROVED_SOURCES))))
    if not isinstance(source, dict):
        _error("来源 %r 必须是映射" % name)
    unknown = sorted(set(source) - set(SOURCE_KEYS))
    if unknown:
        _error("来源 %r 含未登记的键：%s" % (name, ", ".join(unknown)))
    for key, expected in approved.items():
        if source.get(key) != expected:
            _error("来源 %r 的 %s 必须为 %r" % (name, key, expected))
    approval = source.get("approval")
    if not isinstance(approval, str) or not approval.strip():
        _error("来源 %r 缺少 approval（负责人批准记录）" % name)


def verify_provider_snapshot(entry, root):
    """校验一个 Provider 快照的路径、字节数和 SHA-256，返回快照路径。"""
    if not isinstance(entry, dict):
        _error("Provider 条目必须是映射")
    path = _snapshot_path(entry, root)
    if not path.is_file():
        _error("快照不存在：%s" % entry.get("snapshot"))
    try:
        payload = path.read_bytes()
    except OSError as exc:
        _error("无法读取快照 %s：%s" % (entry.get("snapshot"), exc))
    expected_bytes = entry.get("bytes")
    if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes <= 0:
        _error("bytes 必须是正整数")
    if len(payload) != expected_bytes:
        _error(
            "快照字节数不匹配：期望 %d，实际 %d（%s）"
            % (expected_bytes, len(payload), entry.get("snapshot"))
        )
    expected_sha = entry.get("sha256")
    if not isinstance(expected_sha, str) or not SHA256_RE.match(expected_sha):
        _error("sha256 必须是 64 位小写十六进制")
    actual_sha = hashlib.sha256(payload).hexdigest()
    if actual_sha != expected_sha:
        _error(
            "快照 SHA-256 不匹配：期望 %s，实际 %s（%s）"
            % (expected_sha, actual_sha, entry.get("snapshot"))
        )
    return path


def load_provider_lock(root=ROOT):
    """读取并校验 providers/lock.yaml，同时校验所有快照。"""
    root = Path(root)
    path = root / LOCK_RELATIVE
    if not path.is_file():
        _error("锁文件不存在：%s" % LOCK_RELATIVE.as_posix())
    data = _read_mapping(path)
    if data.get("version") != 1:
        _error("version 必须为 1")
    sources = data.get("sources")
    providers = data.get("providers")
    if not isinstance(sources, dict) or not sources:
        _error("sources 必须是非空映射")
    if not isinstance(providers, dict) or not providers:
        _error("providers 必须是非空映射")
    for name, source in sources.items():
        _validate_source(name, source)
    for name, entry in providers.items():
        if not isinstance(name, str) or not PROVIDER_NAME_RE.match(name):
            _error("Provider 名称必须是小写字母、数字或连字符：%r" % (name,))
        if not isinstance(entry, dict):
            _error("Provider %r 必须是映射" % name)
        unknown = sorted(set(entry) - set(PROVIDER_KEYS))
        if unknown:
            _error("Provider %r 含未登记的键：%s" % (name, ", ".join(unknown)))
        missing = [key for key in PROVIDER_KEYS if key not in entry]
        if missing:
            _error("Provider %r 缺少键：%s" % (name, ", ".join(missing)))
        if entry["source"] not in sources:
            _error("Provider %r 引用了未知来源 %r" % (name, entry["source"]))
        commit = entry.get("commit")
        if not isinstance(commit, str) or not COMMIT_RE.match(commit):
            _error("Provider %r 的 commit 必须是 40 位小写十六进制" % name)
        upstream = _safe_relative(entry.get("upstream_path"), "upstream_path")
        if upstream.suffix != ".list":
            _error("Provider %r 的 upstream_path 必须是 .list 文件" % name)
        if entry.get("behavior") not in PROVIDER_BEHAVIORS:
            _error(
                "Provider %r 的 behavior 必须是 %s"
                % (name, "、".join(PROVIDER_BEHAVIORS))
            )
        verify_provider_snapshot(entry, root)
    return data


def parse_provider_payload(entry, data):
    """校验并解析 Provider 原始字节，返回可放入 inline payload 的条目列表。"""
    if not isinstance(data, (bytes, bytearray)):
        _error("快照内容必须是字节")
    try:
        text = bytes(data).decode("utf-8")
    except UnicodeDecodeError:
        _error("快照不是 UTF-8 文本：%s" % entry.get("snapshot"))
    payload = []
    for number, raw in enumerate(text.splitlines(), 1):
        item = raw.strip()
        if not item or item.startswith("#"):
            continue
        if any(char.isspace() for char in item):
            _error(
                "快照 %s 第 %d 行含空白：%r"
                % (entry.get("snapshot"), number, item)
            )
        if entry.get("behavior") == "domain" and "," in item:
            _error(
                "快照 %s 第 %d 行不是 domain 条目：%r"
                % (entry.get("snapshot"), number, item)
            )
        payload.append(item)
    if not payload:
        _error("快照 %s 为空" % entry.get("snapshot"))
    return payload


def read_provider_payload(entry, root=ROOT):
    """读取快照并返回可放入 inline payload 的条目列表。"""
    path = verify_provider_snapshot(entry, root)
    try:
        data = path.read_bytes()
    except OSError as exc:
        _error("无法读取快照 %s：%s" % (entry.get("snapshot"), exc))
    return parse_provider_payload(entry, data)


def render_rule_providers(lock, root=ROOT):
    """把锁中的 Provider 渲染成 Mihomo rule-providers（inline）。"""
    providers = lock.get("providers")
    if not isinstance(providers, dict) or not providers:
        _error("providers 必须是非空映射")
    rendered = {}
    for name in sorted(providers):
        entry = providers[name]
        rendered[name] = {
            "type": "inline",
            "behavior": entry["behavior"],
            "payload": read_provider_payload(entry, root),
        }
    return rendered
