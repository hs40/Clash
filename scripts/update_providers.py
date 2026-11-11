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
    parser.add_argument("--commit", help="上游 meta 分支的 40 位 commit（--apply 必填）")
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根目录")
    parser.add_argument("--json", type=Path, help="把检查结果写入 JSON 文件")
    args = parser.parse_args(argv)
    if args.check == args.apply:
        parser.error("必须且只能指定 --check 或 --apply")
    try:
        lock = load_provider_lock(args.root)
        results = check_upstream(lock)
        changed = any(item["changed"] for item in results)
        if args.apply and changed:
            if not args.commit:
                raise UpdateError("--apply 发现更新时必须提供 --commit")
            updated = apply_updates(lock, results, args.commit, args.root)
            print("已更新 Provider：%s" % "、".join(updated))
            branch = "provider/update-%s" % args.commit[:12]
            print("下一步（请人工审查后执行）：")
            print("  git switch -c %s" % branch)
            print("  git add providers/lock.yaml providers/snapshots")
            print("  git commit -m \"chore(provider): 更新至 %s\"" % args.commit)
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
        _write_json(args.json, {"changed": changed,
                                "providers": public_results(results)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
