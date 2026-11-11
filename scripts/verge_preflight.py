"""Verge 全局迁移的节点预检（VERGE-GLOBAL）。

预检分两步：
1. 静态过滤 reality-opts.short-id 不是 8/16 位十六进制的节点；
2. 对剩余节点逐个调用 mihomo -t，发现静态规则覆盖不到的问题。

任一节点无法加载都从可用节点中剔除并记录；全部不可用时中止迁移。
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml

SHORT_ID_RE = re.compile(r"^(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{16})$")


class PreflightError(Exception):
    """预检输入或 mihomo 执行失败，不能继续迁移。"""


def valid_short_id(value):
    """REALITY short-id 缺省或空串视为未设置；否则必须是 8/16 位十六进制。"""
    if value is None or value == "":
        return True
    if not isinstance(value, str):
        return False
    return SHORT_ID_RE.match(value) is not None


def filter_bad_short_ids(proxies):
    """返回 (可用节点, 静态坏节点)，保持原始顺序。"""
    good = []
    bad = []
    for proxy in proxies:
        if not isinstance(proxy, dict):
            raise PreflightError("proxies 中存在非映射条目")
        reality = proxy.get("reality-opts")
        short_id = reality.get("short-id") if isinstance(reality, dict) else None
        if valid_short_id(short_id):
            good.append(proxy)
        else:
            bad.append(proxy)
    return good, bad


def build_probe_config(proxies):
    """构造只包含指定节点、不触发 GeoIP 下载的最小配置。"""
    if not proxies:
        raise PreflightError("探测配置不能为空")
    name = proxies[0]["name"]
    return {
        "mixed-port": 7897,
        "proxies": list(proxies),
        "proxy-groups": [{"name": "PROBE", "type": "select", "proxies": [name]}],
        "rules": ["MATCH,PROBE"],
    }


def run_mihomo(mihomo, config, workdir, timeout=20):
    """执行 mihomo -t，返回 (是否成功, 合并后的输出)。"""
    mihomo = Path(mihomo)
    if not mihomo.is_file():
        raise PreflightError("找不到 Mihomo 内核：%s" % mihomo)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    probe = workdir / "mvp-probe.yaml"
    probe.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    command = [str(mihomo), "-t", "-f", str(probe), "-d", str(workdir)]
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise PreflightError("mihomo -t 超时（%s）" % mihomo)
    try:
        output = proc.stdout.decode("utf-8", errors="replace")
    except Exception:
        output = str(proc.stdout)
    return proc.returncode == 0, output


def preflight(profile_path, mihomo, workdir, runner=None, timeout=20):
    """读取单个 profile，返回预检结果；全部节点不可用时抛错。"""
    path = Path(profile_path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PreflightError("无法读取 profile：%s" % exc) from exc
    except yaml.YAMLError as exc:
        raise PreflightError("profile YAML 解析失败：%s" % exc) from exc
    if not isinstance(data, dict):
        raise PreflightError("profile 顶层必须是映射")
    providers = data.get("proxy-providers")
    if providers:
        raise PreflightError("当前 profile 含 proxy-providers；全局脚本只支持 inline proxies")
    proxies = data.get("proxies")
    if not isinstance(proxies, list) or not proxies:
        raise PreflightError("profile 缺少非空 proxies 列表")

    good, static_bad = filter_bad_short_ids(proxies)
    if runner is None:
        def runner(binary, cfg, directory):
            return run_mihomo(binary, cfg, directory, timeout=timeout)

    runtime_bad = []
    usable = []
    first_output = ""
    for proxy in good:
        try:
            ok, output = runner(mihomo, build_probe_config([proxy]), Path(workdir))
        except PreflightError:
            raise
        except Exception as exc:
            raise PreflightError("调用 mihomo 失败：%s" % exc) from exc
        if not first_output:
            first_output = output
        if ok:
            usable.append(proxy)
        else:
            runtime_bad.append(proxy["name"])

    if not usable:
        detail = first_output.strip().splitlines()[-1] if first_output.strip() else "无输出"
        raise PreflightError("预检后没有可用节点（mihomo 输出：%s）" % detail)

    return {
        "total": len(proxies),
        "static_bad": static_bad,
        "runtime_bad": runtime_bad,
        "usable": usable,
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Verge profile 节点预检")
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--mihomo", required=True, type=Path)
    parser.add_argument("--workdir", type=Path, default=Path(".tmp_verge_preflight"))
    args = parser.parse_args(argv)
    try:
        result = preflight(args.profile, args.mihomo, args.workdir)
    except PreflightError as exc:
        print("预检失败：%s" % exc, file=sys.stderr)
        return 2
    print(
        "预检通过：总节点 %d，静态剔除 %d，运行时剔除 %d，可用 %d"
        % (
            result["total"],
            len(result["static_bad"]),
            len(result["runtime_bad"]),
            len(result["usable"]),
        )
    )
    for item in result["static_bad"]:
        print("  静态剔除：%s（short-id=%r）" % (
            item["name"], (item.get("reality-opts") or {}).get("short-id")
        ))
    for name in result["runtime_bad"]:
        print("  运行时剔除：%s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
