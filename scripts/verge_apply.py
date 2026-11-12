"""把仓库 MVP 设置应用到 Clash Verge 的全局扩展（Merge/Script）。

流程：预检当前订阅 -> 生成全局文件 -> 备份 -> 原子写入 -> 切换目标 profile
-> 重启 Verge -> 校验生成配置 -> 失败自动回滚。

本模块只改 Verge AppData 下的：
  profiles/Merge.yaml、profiles/Script.js、profiles.yaml、verge.yaml
以及由 Verge 生成的 clash-verge.yaml（只读校验，不直接写）。

注意：config.yaml 只是 Verge 的应用设置底板；运行时完整配置是
clash-verge.yaml。校验和备份都以 clash-verge.yaml 为准。
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

from verge_global import GROUP_ORDER, build_merge, build_script
from verge_preflight import PreflightError, preflight

APP_DIR_NAME = "io.github.clash-verge-rev.clash-verge-rev"
BACKUP_FILES = (
    "profiles/Merge.yaml",
    "profiles/Script.js",
    "profiles.yaml",
    "verge.yaml",
    "config.yaml",
    "clash-verge.yaml",
)
REQUIRED_SETTINGS = ("enable_tun_mode", "enable_system_proxy", "verge_mixed_port")
REGION_GROUPS = ("香港节点", "台湾节点", "日本节点", "韩国节点", "狮城节点", "美国节点", "其他节点")
AI_GROUPS = ("OpenAI", "Claude", "Cursor")
PROVIDERS = ("geosite-cn", "geosite-private")
URL_TEST = "https://www.gstatic.com/generate_204"


class ApplyError(Exception):
    """迁移前置条件、写入或校验失败。"""


def appdata_root():
    value = os.environ.get("APPDATA")
    if not value:
        raise ApplyError("APPDATA 未设置，无法定位 Clash Verge 配置目录")
    return Path(value) / APP_DIR_NAME


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_yaml(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ApplyError("无法读取 %s：%s" % (path, exc)) from exc
    except yaml.YAMLError as exc:
        raise ApplyError("YAML 解析失败 %s：%s" % (path, exc)) from exc


def backup(appdir, backup_dir):
    """把迁移会改动的文件复制到备份目录，并写 manifest.yaml。"""
    appdir = Path(appdir)
    backup_dir = Path(backup_dir)
    if backup_dir.exists() and any(backup_dir.iterdir()):
        raise ApplyError("备份目录非空：%s" % backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for relative in BACKUP_FILES:
        source = appdir / relative
        if not source.is_file():
            raise ApplyError("备份源文件不存在：%s" % source)
        target = backup_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files[relative] = {"sha256": _sha256(source), "size": source.stat().st_size}
    manifest = {
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": str(appdir),
        "files": files,
    }
    (backup_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def restore(appdir, backup_dir):
    """按备份目录恢复被改动的文件；manifest 不存在时拒绝执行。"""
    appdir = Path(appdir)
    backup_dir = Path(backup_dir)
    manifest_path = backup_dir / "manifest.yaml"
    if not manifest_path.is_file():
        raise ApplyError("备份目录缺少 manifest.yaml：%s" % backup_dir)
    manifest = _read_yaml(manifest_path)
    for relative in manifest.get("files", {}):
        source = backup_dir / relative
        if not source.is_file():
            raise ApplyError("备份文件缺失：%s" % source)
        target = appdir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return manifest


def write_atomic(path, text):
    """同目录临时文件 + os.replace，统一 LF，避免半写文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def set_setting(path, key, value):
    """只替换一个顶层标量，保留 Verge 配置的注释和其他键。"""
    path = Path(path)
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    literal = json.dumps(value, ensure_ascii=False)
    pattern = re.compile(r"^%s[ \t]*:.*$" % re.escape(key), re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub("%s: %s" % (key, literal), text, count=1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "%s: %s\n" % (key, literal)
    write_atomic(path, text)


def snapshot_settings(appdir):
    data = _read_yaml(Path(appdir) / "verge.yaml")
    if not isinstance(data, dict):
        raise ApplyError("verge.yaml 顶层不是映射")
    return {key: data.get(key) for key in REQUIRED_SETTINGS}


def _find_item(profiles, uid):
    for item in profiles.get("items") or []:
        if item.get("uid") == uid:
            return item
    return None


def prepare_plan(appdir, root, mihomo, workdir, target_uid=None):
    """读取目标 profile、预检节点并生成待写入内容；不修改任何文件。"""
    appdir = Path(appdir)
    profiles_path = appdir / "profiles.yaml"
    profiles = _read_yaml(profiles_path)
    if not isinstance(profiles, dict):
        raise ApplyError("profiles.yaml 顶层不是映射")
    uid = target_uid or profiles.get("current")
    if not uid:
        raise ApplyError("profiles.yaml 没有 current")
    item = _find_item(profiles, uid)
    if item is None:
        raise ApplyError("找不到 profile：%s" % uid)
    relative = item.get("file")
    if not relative:
        raise ApplyError("profile %s 缺少 file" % uid)
    profile_path = appdir / "profiles" / relative
    if not profile_path.is_file():
        raise ApplyError("profile 文件不存在：%s" % profile_path)
    try:
        result = preflight(profile_path, mihomo, workdir)
    except PreflightError as exc:
        raise ApplyError("节点预检失败：%s" % exc) from exc
    name = item.get("name") or uid
    bad = [node["name"] for node in result["static_bad"]] + list(result["runtime_bad"])
    try:
        merge = build_merge(root)
        script = build_script(root, exclusions={name: bad})
    except Exception as exc:
        raise ApplyError("生成全局扩展失败：%s" % exc) from exc
    return {
        "merge": merge,
        "script": script,
        "profile_uid": uid,
        "profile_name": name,
        "settings": snapshot_settings(appdir),
        "expected_proxies": len(result["usable"]),
        "preflight": {
            "total": result["total"],
            "static_bad": [node["name"] for node in result["static_bad"]],
            "runtime_bad": list(result["runtime_bad"]),
            "usable": len(result["usable"]),
        },
    }


def _group(groups, name):
    for item in groups:
        if item.get("name") == name:
            return item
    raise ApplyError("缺少策略组：%s" % name)


def verify_config(config, expected_proxies):
    """校验 Verge 生成的 config.yaml 是否符合 MVP 固定契约。"""
    if not isinstance(config, dict):
        raise ApplyError("config.yaml 顶层不是映射")
    if config.get("mixed-port") != 7897:
        raise ApplyError("mixed-port 不是 7897：%r" % config.get("mixed-port"))
    if config.get("mode") != "rule":
        raise ApplyError("mode 不是 rule：%r" % config.get("mode"))
    if config.get("ipv6") is not False:
        raise ApplyError("ipv6 不是 false")
    if config.get("allow-lan") is not False:
        raise ApplyError("allow-lan 不是 false")
    tun = config.get("tun")
    if not isinstance(tun, dict) or tun.get("enable") is not True or tun.get("stack") != "gvisor":
        raise ApplyError("tun.enable 不是 true 或 stack 不是 gvisor")
    dns = config.get("dns")
    if not isinstance(dns, dict) or dns.get("listen") != "0.0.0.0:1053":
        raise ApplyError("dns.listen 不是 0.0.0.0:1053")
    proxies = config.get("proxies")
    if not isinstance(proxies, list) or len(proxies) != expected_proxies:
        raise ApplyError("节点数不是 %d：%r" % (
            expected_proxies, len(proxies) if isinstance(proxies, list) else proxies
        ))
    groups = config.get("proxy-groups")
    if not isinstance(groups, list) or [g.get("name") for g in groups] != list(GROUP_ORDER):
        raise ApplyError("策略组名称或顺序不符合固定契约")
    proxy_group = _group(groups, "PROXY")
    if proxy_group.get("type") != "select" or proxy_group.get("proxies") != (
        ["自动选择"] + list(REGION_GROUPS) + ["DIRECT"]
    ):
        raise ApplyError("PROXY 组成员或类型不符合契约")
    google = _group(groups, "Google")
    if google.get("type") != "fallback" or google.get("proxies") != [
        "美国节点", "狮城节点", "日本节点", "香港节点"
    ]:
        raise ApplyError("Google 回退顺序不符合契约")
    auto = _group(groups, "自动选择")
    if (
        auto.get("type") != "url-test"
        or auto.get("url") != URL_TEST
        or auto.get("interval") != 300
        or auto.get("tolerance") != 50
        or len(auto.get("proxies") or []) != expected_proxies
    ):
        raise ApplyError("自动选择组不符合契约")
    for name in AI_GROUPS:
        group = _group(groups, name)
        if group.get("type") != "select" or group.get("proxies") != [
            "自动选择"
        ] + list(REGION_GROUPS):
            raise ApplyError("%s 组成员或类型不符合契约" % name)
    for name in REGION_GROUPS:
        group = _group(groups, name)
        if group.get("type") != "select" or not group.get("proxies"):
            raise ApplyError("%s 组为空或类型错误" % name)
    providers = config.get("rule-providers")
    if not isinstance(providers, dict) or set(providers) != set(PROVIDERS):
        raise ApplyError("rule-providers 不是且仅是两个内嵌 Provider")
    rules = config.get("rules")
    if not isinstance(rules, list) or len(rules) != 27:
        raise ApplyError("规则数不是 27")
    if rules[-1] != "MATCH,PROXY" or any(rule == "MATCH,PROXY" for rule in rules[:-1]):
        raise ApplyError("MATCH,PROXY 必须是唯一且最后一条")
    return True


def _switch_current(profiles_path, uid):
    text = profiles_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    pattern = re.compile(r"^current[ \t]*:.*$", re.MULTILINE)
    if not pattern.search(text):
        raise ApplyError("profiles.yaml 缺少 current")
    text = pattern.sub("current: %s" % uid, text, count=1)
    write_atomic(profiles_path, text)


def _wait_for_config(appdir, expected_proxies, timeout, sleep, min_mtime_ns=None):
    deadline = time.monotonic() + timeout
    last_error = None
    runtime = Path(appdir) / "clash-verge.yaml"
    while True:
        try:
            if min_mtime_ns is not None:
                if runtime.stat().st_mtime_ns <= min_mtime_ns:
                    raise ApplyError("clash-verge.yaml 尚未重新生成")
            data = _read_yaml(runtime)
            verify_config(data, expected_proxies)
            return True
        except ApplyError as exc:
            last_error = exc
        except OSError as exc:
            last_error = ApplyError("无法读取 clash-verge.yaml：%s" % exc)
        if time.monotonic() >= deadline:
            raise ApplyError("等待新配置超时：%s" % last_error)
        sleep(0.5)


def apply_migration(appdir, plan, backup_dir, reload=None, dry_run=False,
                    verify_timeout=45, sleep=time.sleep):
    """执行迁移；任何异常都恢复备份（dry_run 不写文件）。"""
    appdir = Path(appdir)
    if dry_run:
        return {
            "dry_run": True,
            "profile_uid": plan["profile_uid"],
            "expected_proxies": plan["expected_proxies"],
            "merge_bytes": len(plan["merge"].encode("utf-8")),
            "script_bytes": len(plan["script"].encode("utf-8")),
        }
    if backup_dir is None:
        raise ApplyError("apply 模式必须提供备份目录")
    print("[1/6] 备份到 %s" % backup_dir, flush=True)
    manifest = backup(appdir, backup_dir)
    original_current = _read_yaml(appdir / "profiles.yaml").get("current")
    try:
        print("[2/6] 写入全局 Merge/Script", flush=True)
        write_atomic(appdir / "profiles" / "Merge.yaml", plan["merge"])
        write_atomic(appdir / "profiles" / "Script.js", plan["script"])
        print("[3/6] 切换 current -> %s" % plan["profile_uid"], flush=True)
        _switch_current(appdir / "profiles.yaml", plan["profile_uid"])
        print("[4/6] 保留 TUN/系统代理/混合端口设置", flush=True)
        for key, value in (plan.get("settings") or {}).items():
            set_setting(appdir / "verge.yaml", key, value)
        if reload is not None:
            print("[5/6] 重启 Verge，等待生成新配置", flush=True)
            runtime = appdir / "clash-verge.yaml"
            before_mtime = runtime.stat().st_mtime_ns if runtime.is_file() else None
            reload()
            if verify_timeout is not None:
                _wait_for_config(
                    appdir, plan["expected_proxies"], verify_timeout, sleep,
                    min_mtime_ns=before_mtime,
                )
            print("[6/6] 校验通过", flush=True)
    except Exception as exc:
        restore(appdir, backup_dir)
        if reload is not None:
            try:
                reload()
            except Exception:
                pass
        raise ApplyError("%s；已回滚到迁移前文件" % exc) from exc
    return {
        "ok": True,
        "backup": str(backup_dir),
        "profile_uid": plan["profile_uid"],
        "profile_name": plan["profile_name"],
        "previous_current": original_current,
        "expected_proxies": plan["expected_proxies"],
        "preflight": plan.get("preflight"),
        "files": manifest["files"],
    }


RESTART_IMAGES = ("clash-verge.exe", "verge-mihomo.exe")


def restart_verge(task_name="Clash Verge (Admin)", wait=3.0):
    """强制结束 Verge UI/核心，再用计划任务以管理员身份启动。

    schtasks /End 只结束计划任务的直接进程，实测不会结束 sidecar 核心，
    也不会让 Verge 重新生成 clash-verge.yaml；因此这里按镜像名结束两者。
    """
    for image in RESTART_IMAGES:
        subprocess.run(
            ["taskkill", "/IM", image, "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    time.sleep(wait)
    proc = subprocess.run(
        ["schtasks", "/Run", "/TN", task_name],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = proc.stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise ApplyError("启动 Verge 计划任务失败：%s" % output)


def main(argv=None):
    parser = argparse.ArgumentParser(description="把仓库 MVP 设置应用到 Verge 全局扩展")
    parser.add_argument("--appdir", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mihomo", type=Path, default=Path(r"C:\Program Files\Clash Verge\verge-mihomo.exe"))
    parser.add_argument("--workdir", type=Path, default=Path(".tmp_verge_preflight"))
    parser.add_argument("--profile", default=None, help="目标 profile UID；默认当前 profile")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--rollback", type=Path, default=None)
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args(argv)
    appdir = args.appdir or appdata_root()

    try:
        if args.rollback:
            restore(appdir, args.rollback)
            if args.restart:
                restart_verge()
            print("已从 %s 恢复" % args.rollback, flush=True)
            return 0
        plan = prepare_plan(appdir, args.root, args.mihomo, args.workdir, args.profile)
        print(
            "预检：总节点 %(total)d，静态剔除 %(static_bad)d，运行时剔除 %(runtime_bad)d，可用 %(usable)d"
            % {
                "total": plan["preflight"]["total"],
                "static_bad": len(plan["preflight"]["static_bad"]),
                "runtime_bad": len(plan["preflight"]["runtime_bad"]),
                "usable": plan["preflight"]["usable"],
            }
        )
        if args.dry_run or not args.apply:
            result = apply_migration(appdir, plan, None, dry_run=True)
            print("dry-run：Merge %d 字节，Script %d 字节；未写入" % (
                result["merge_bytes"], result["script_bytes"]
            ))
            return 0
        backup_dir = args.backup_dir or (
            appdir.parent / ("clash-verge-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        )
        result = apply_migration(
            appdir, plan, backup_dir,
            reload=restart_verge if args.restart else None,
            verify_timeout=45 if args.restart else None,
        )
        print("迁移完成：profile=%s，节点=%d，备份=%s" % (
            result["profile_name"], result["expected_proxies"], result["backup"]
        ))
        return 0
    except ApplyError as exc:
        print("迁移失败：%s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
