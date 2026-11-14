"""ENG-06 Provider 上游检查与本地更新。"""

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import yaml

from providers import (
    COMMIT_RE,
    ProviderError,
    load_provider_lock,
    parse_provider_payload,
)

ROOT = Path(__file__).resolve().parents[1]
RAW_URL = "https://raw.githubusercontent.com/{owner}/{repository}/{ref}/{path}"
COMMIT_API = "https://api.github.com/repos/{owner}/{repository}/commits/{ref}"
BRANCH_PREFIX = "provider/update-"
LOCK_HEADER = """# ENG-06 Provider 锁（构建期校验，不参与运行时下载）
#
# 来源白名单硬编码在 scripts/providers.py；本文件只记录已批准来源的固定版本。
# 升级必须同时更新 commit、upstream_path、snapshot、sha256、bytes，并通过全部测试。
"""


class UpdateError(Exception):
    """Provider 检查失败。"""


def fetch_url(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": "hs40-clash-provider-check"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def upstream_url(source, entry):
    return RAW_URL.format(
        owner=source["owner"],
        repository=source["repository"],
        ref=source["ref"],
        path=entry["upstream_path"],
    )


def commit_url(source, ref):
    return COMMIT_API.format(
        owner=source["owner"], repository=source["repository"], ref=ref
    )


def resolve_commit(lock, results, fetch=None):
    """把发生变化来源的跟踪 ref 解析为 40 位 commit；多来源同时变化需人工处理。"""
    if fetch is None:
        fetch = fetch_url
    names = sorted({item["provider"] for item in results if item["changed"]})
    if not names:
        raise UpdateError("没有需要更新的 Provider")
    sources = sorted({lock["providers"][name]["source"] for name in names})
    if len(sources) > 1:
        raise UpdateError(
            "多个来源同时变化（%s），请分别提供 --commit 人工处理" % "、".join(sources)
        )
    source = lock["sources"][sources[0]]
    url = commit_url(source, source["ref"])
    try:
        payload = fetch(url)
    except Exception as exc:
        raise UpdateError("无法解析上游 commit：%s" % exc)
    try:
        data = json.loads(bytes(payload).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise UpdateError("上游 commit 接口返回无法解析：%s" % exc)
    sha = data.get("sha") if isinstance(data, dict) else None
    if not isinstance(sha, str) or not COMMIT_RE.match(sha):
        raise UpdateError("上游 commit 接口未返回 40 位小写 commit")
    return sha


def check_upstream(lock, fetch=None):
    """按锁中的固定来源和跟踪 ref 拉取上游内容并比较哈希。"""
    if fetch is None:
        fetch = fetch_url
    results = []
    sources = lock["sources"]
    for name in sorted(lock["providers"]):
        entry = lock["providers"][name]
        source = sources[entry["source"]]
        url = upstream_url(source, entry)
        try:
            payload = fetch(url)
        except Exception as exc:
            raise UpdateError("Provider %s 无法读取上游：%s" % (name, exc))
        if not isinstance(payload, (bytes, bytearray)):
            raise UpdateError("Provider %s 的上游返回非字节内容" % name)
        digest = hashlib.sha256(payload).hexdigest()
        changed = digest != entry["sha256"] or len(payload) != entry["bytes"]
        results.append(
            {
                "provider": name,
                "url": url,
                "changed": changed,
                "current_sha256": entry["sha256"],
                "upstream_sha256": digest,
                "upstream_bytes": len(payload),
                "candidate": bytes(payload),
            }
        )
    return results


def public_results(results):
    return [
        {key: value for key, value in item.items() if key != "candidate"}
        for item in results
    ]


def _atomic_write(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _write_lock(lock, root):
    path = Path(root) / "providers" / "lock.yaml"
    text = LOCK_HEADER + yaml.safe_dump(
        lock, allow_unicode=True, sort_keys=False, width=4096
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def apply_updates(lock, results, commit, root=ROOT):
    """把所有已变更 Provider 写入快照并更新锁；任一校验失败则不写任何文件。"""
    changed = [item for item in results if item["changed"]]
    if not changed:
        return []
    if not isinstance(commit, str) or not COMMIT_RE.match(commit):
        raise UpdateError("更新必须提供 40 位小写 commit")
    prepared = []
    for item in changed:
        name = item["provider"]
        entry = dict(lock["providers"][name])
        data = bytes(item["candidate"])
        entry["commit"] = commit
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        entry["bytes"] = len(data)
        parse_provider_payload(entry, data)
        prepared.append((name, entry, data))
    root = Path(root)
    for name, entry, data in prepared:
        snapshot = root / entry["snapshot"]
        _atomic_write(snapshot, data)
        lock["providers"][name] = entry
    _write_lock(lock, root)
    return [name for name, _entry, _data in prepared]


def _write_json(path, data):
    path = Path(path)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="检查或应用 ENG-06 Provider 上游更新")
    parser.add_argument("--check", action="store_true", help="检查上游是否存在更新")
    parser.add_argument("--apply", action="store_true", help="把上游更新写入快照与锁文件")
    parser.add_argument(
        "--commit",
        help="上游 40 位 commit；省略时由 --apply 通过 GitHub API 解析跟踪 ref",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根目录")
    parser.add_argument("--json", type=Path, help="把检查结果写入 JSON 文件")
    args = parser.parse_args(argv)
    if args.check == args.apply:
        parser.error("必须且只能指定 --check 或 --apply")
    try:
        lock = load_provider_lock(args.root)
        results = check_upstream(lock)
        changed = any(item["changed"] for item in results)
        branch = None
        commit = None
        if args.apply and changed:
            commit = args.commit or resolve_commit(lock, results)
            updated = apply_updates(lock, results, commit, args.root)
            branch = BRANCH_PREFIX + commit[:12]
            print("已更新 Provider：%s" % "、".join(updated))
            print("上游 commit：%s" % commit)
            print("下一步（请人工审查后执行）：")
            print("  git switch -c %s" % branch)
            print("  git add providers/lock.yaml providers/snapshots")
            print("  git commit -m \"chore(provider): 更新至 %s\"" % commit)
            print("  git push -u origin HEAD")
            print("  gh pr create --fill")
        elif args.apply:
            print("Provider 均已是最新，未写入任何文件")
    except (ProviderError, UpdateError) as exc:
        print("Provider 检查失败：%s" % exc, file=sys.stderr)
        return 2
    for item in results:
        status = "需要更新" if item["changed"] else "已是最新"
        print("%s：%s（上游 %d 字节）" % (item["provider"], status, item["upstream_bytes"]))
    if args.json:
        report = {"changed": changed, "providers": public_results(results)}
        if commit:
            report["commit"] = commit
            report["branch"] = branch
        _write_json(args.json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
