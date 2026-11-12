"""个人网络部署平台 CLI：status / plan / deploy / rollback / verify。

默认命令是只读的 plan；deploy 必须显式 --apply，并在写任何文件前确认一次。
--yes 仅用于负责人已批准的非交互运行或测试。
"""

import argparse
import ctypes
import json
import os
import sys
from pathlib import Path

import platform_diff
import platform_openclash
import platform_state
import platform_windows
import verge_apply
from platform_ssh import SshError, SshRunner

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIHOMO = Path(r"C:\Program Files\Clash Verge\verge-mihomo.exe")
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_UNCONFIRMED = 4


def _parser():
    parser = argparse.ArgumentParser(
        description="个人网络部署平台：Windows Clash Verge + iStoreOS OpenClash"
    )
    parser.add_argument(
        "command", nargs="?", default="plan",
        choices=("status", "plan", "deploy", "rollback", "verify"),
        help="默认 plan（只读）",
    )
    parser.add_argument("--platform", choices=("windows", "openclash"), required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--state", type=Path, default=None,
                        help="状态目录；默认 LOCALAPPDATA 下的 ClashPlatform")
    parser.add_argument("--appdir", type=Path, default=None,
                        help="Clash Verge AppData 目录")
    parser.add_argument("--mihomo", type=Path, default=DEFAULT_MIHOMO)
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--profile", default=None, help="目标 Verge profile UID")
    parser.add_argument("--node-source", type=Path, default=None,
                        help="OpenClash 节点来源 FIB profile；也可用 CLASH_NODE_SOURCE")
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--diff", action="store_true", help="plan 时输出完整脱敏 diff")
    return parser


def _appdir(args):
    return args.appdir or verge_apply.appdata_root()


def _workdir(args):
    return args.workdir or (args.root / ".tmp_platform_preflight")


def _ssh(args):
    return SshRunner(
        host=os.environ.get("CLASH_SSH_HOST", "192.168.2.10"),
        user=os.environ.get("CLASH_SSH_USER", "root"),
        port=int(os.environ.get("CLASH_SSH_PORT", "22")),
        known_hosts=os.environ.get("CLASH_SSH_KNOWN_HOSTS") or None,
    )


def _node_source(args, parser):
    value = args.node_source or os.environ.get("CLASH_NODE_SOURCE")
    if not value:
        parser.error("OpenClash 需要 --node-source 或 CLASH_NODE_SOURCE")
    return Path(value)


def _public_plan(platform, plan):
    if platform == "windows":
        verge = plan["verge"]
        return {
            "platform": "windows",
            "profile": verge.get("profile_name"),
            "profile_uid": verge.get("profile_uid"),
            "proxies": verge.get("expected_proxies"),
            "rules": verge.get("expected_rules"),
            "summary": plan.get("summary"),
            "ipv6_enabled": plan.get("ipv6_enabled"),
            "dns_guard_ok": plan.get("dns_guard_ok"),
        }
    built = plan["built"]
    return {
        "platform": "openclash",
        "target": platform_openclash.NEW_CONFIG,
        "port": platform_openclash.PORT,
        "current_config": plan["state"].get("config_path"),
        "dns_listen": built.get("dns_listen"),
        "total": built.get("total"),
        "usable": built.get("usable"),
        "static_bad": len(built.get("static_bad") or []),
        "summary": plan.get("summary"),
    }


def _print_plan(platform, plan, show_diff=False):
    print(platform_diff.render_summary(plan["summary"], platform), flush=True)
    if platform == "windows":
        print("目标 profile：%s；可用节点 %d；规则 %d" % (
            plan["verge"].get("profile_name"),
            plan["verge"].get("expected_proxies"),
            plan["verge"].get("expected_rules"),
        ), flush=True)
        if plan.get("ipv6_enabled"):
            print("将关闭物理网卡 IPv6：%s" % "、".join(plan["ipv6_enabled"]), flush=True)
        print("DNS 护栏：%s" % ("已就绪" if plan.get("dns_guard_ok") else "将补齐"), flush=True)
    else:
        built = plan["built"]
        print("目标：%s；端口 %d；DNS %s" % (
            platform_openclash.NEW_CONFIG, platform_openclash.PORT, built.get("dns_listen")
        ), flush=True)
        print("节点：总 %d，静态过滤 %d，可用 %d" % (
            built.get("total"), len(built.get("static_bad") or []), built.get("usable")
        ), flush=True)
    if show_diff:
        print("", flush=True)
        print(plan.get("diff") or "配置内容无变化", flush=True)


def _stdin_is_console():
    if os.name != "nt":
        return sys.stdin.isatty()
    try:
        handle = ctypes.windll.kernel32.GetStdHandle(-10)
        mode = ctypes.c_uint()
        return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
    except Exception:
        return False


def _confirm(args, action):
    if args.yes:
        return True
    if not _stdin_is_console():
        print("未检测到交互终端；非交互%s必须显式 --yes" % action, file=sys.stderr, flush=True)
        return False
    try:
        answer = input("确认%s？输入 y 继续：" % action).strip().lower()
    except EOFError:
        return False
    return answer == "y"


def _make_plan(args, parser):
    if args.platform == "windows":
        return platform_windows.plan_windows(
            _appdir(args), args.root, args.mihomo, _workdir(args), args.profile
        )
    return platform_openclash.plan_openclash(
        args.root, _node_source(args, parser), _ssh(args)
    )


def _summary_line(platform, plan):
    summary = plan.get("summary") or {}
    proxies = summary.get("proxies") or {}
    rules = summary.get("rules") or {}
    return "%s：节点 %s→%s，规则 %s→%s，变更 %s" % (
        platform, proxies.get("before"), proxies.get("after"),
        rules.get("before"), rules.get("after"),
        "是" if summary.get("has_changes") else "否",
    )


def _write_report(path, data):
    platform_state.write_json(path, data)


def cmd_status(args):
    if args.platform == "windows":
        result = platform_windows.status_windows(_appdir(args))
    else:
        result = platform_openclash.status_openclash(_ssh(args))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return EXIT_OK


def cmd_plan(args, parser):
    if args.platform == "openclash":
        _node_source(args, parser)
    plan = _make_plan(args, parser)
    if args.json:
        print(json.dumps(_public_plan(args.platform, plan), ensure_ascii=False, indent=2),
              flush=True)
    else:
        _print_plan(args.platform, plan, args.diff)
    return EXIT_OK


def cmd_deploy(args, parser):
    if not args.apply:
        print("部署必须显式 --apply；当前未做任何修改", file=sys.stderr, flush=True)
        return EXIT_UNCONFIRMED
    if not args.yes and not _stdin_is_console():
        print("未检测到交互终端；非交互部署必须显式 --yes", file=sys.stderr, flush=True)
        return EXIT_UNCONFIRMED
    if args.platform == "openclash":
        _node_source(args, parser)

    plan = _make_plan(args, parser)
    summary = plan.get("summary") or {}
    if not summary.get("has_changes"):
        print(platform_diff.render_summary(summary, args.platform), flush=True)
        print("没有需要变更的配置，已结束。", flush=True)
        return EXIT_OK
    _print_plan(args.platform, plan)
    if not _confirm(args, "部署"):
        print("已取消，未做任何修改", file=sys.stderr, flush=True)
        return EXIT_UNCONFIRMED

    run = platform_state.create_run(args.platform, state=args.state)
    platform_state.write_text(run["diff"], plan.get("diff") or "配置内容无变化\n")
    report = {
        "command": "deploy",
        "platform": args.platform,
        "started": run["run"].name,
        "plan": _public_plan(args.platform, plan),
        "backup": str(run["backup"]),
        "rolled_back": False,
    }
    try:
        if args.platform == "windows":
            applied = platform_windows.apply_windows(
                _appdir(args), plan, run["backup"], reload=verge_apply.restart_verge
            )
            report["applied"] = applied
            verification = platform_windows.verify_windows(
                _appdir(args), applied["proxies"], applied["rules"]
            )
            report["verify"] = verification
            report["ok"] = bool(verification.get("passed"))
            if not report["ok"]:
                report["note"] = "配置已保留；是否回滚等待负责人确认"
        else:
            ssh = _ssh(args)
            applied = platform_openclash.apply_openclash(ssh, plan, run["backup"])
            report["applied"] = applied
            verification = platform_openclash.verify_openclash(ssh)
            report["verify"] = verification
            if verification.get("passed"):
                report["ok"] = True
            else:
                try:
                    platform_openclash.rollback_openclash(ssh, run["backup"])
                    report["rolled_back"] = True
                    report["note"] = "部署后验收失败，已自动恢复旧配置"
                except Exception as exc:
                    report["rollback_error"] = str(exc)
                    report["note"] = "验收失败且自动回滚失败，需要人工处理"
                report["ok"] = False
    except Exception as exc:
        report["ok"] = False
        report["error"] = str(exc)
        print("部署失败：%s" % exc, file=sys.stderr, flush=True)
    _write_report(run["report"], report)
    platform_state.prune_runs(args.platform, state=args.state)
    print("报告：%s" % run["report"], flush=True)
    if report.get("ok"):
        print("部署完成", flush=True)
        return EXIT_OK
    return EXIT_FAIL


def cmd_rollback(args, parser):
    if not args.backup_dir:
        parser.error("rollback 需要 --backup-dir")
    if not Path(args.backup_dir).is_dir():
        parser.error("备份目录不存在：%s" % args.backup_dir)
    if not args.yes and not _stdin_is_console():
        print("未检测到交互终端；非交互回滚必须显式 --yes", file=sys.stderr, flush=True)
        return EXIT_UNCONFIRMED
    print("将回滚到备份：%s" % args.backup_dir, flush=True)
    if not _confirm(args, "回滚"):
        print("已取消，未做任何修改", file=sys.stderr, flush=True)
        return EXIT_UNCONFIRMED
    if args.platform == "windows":
        result = platform_windows.rollback_windows(
            _appdir(args), args.backup_dir, reload=verge_apply.restart_verge
        )
    else:
        result = platform_openclash.rollback_openclash(_ssh(args), args.backup_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return EXIT_OK


def cmd_verify(args):
    if args.platform == "windows":
        try:
            runtime = platform_windows._read_yaml(_appdir(args) / "clash-verge.yaml")
        except Exception as exc:
            print("读取当前配置失败：%s" % exc, file=sys.stderr, flush=True)
            return EXIT_FAIL
        expected_proxies = len(runtime.get("proxies") or [])
        expected_rules = len(runtime.get("rules") or [])
        run = platform_state.latest_run("windows", state=args.state)
        if run and (run / "report.json").is_file():
            previous = platform_state.read_json(run / "report.json")
            applied = previous.get("applied") or {}
            expected_proxies = applied.get("proxies", expected_proxies)
            expected_rules = applied.get("rules", expected_rules)
        result = platform_windows.verify_windows(
            _appdir(args), expected_proxies, expected_rules
        )
    else:
        result = platform_openclash.verify_openclash(_ssh(args))
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return EXIT_OK if result.get("passed") else EXIT_FAIL


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            return cmd_status(args)
        if args.command == "plan":
            return cmd_plan(args, parser)
        if args.command == "deploy":
            return cmd_deploy(args, parser)
        if args.command == "rollback":
            return cmd_rollback(args, parser)
        return cmd_verify(args)
    except (platform_windows.WindowsError, platform_openclash.OpenClashError,
            platform_state.StateError, verge_apply.ApplyError, SshError,
            OSError, ValueError) as exc:
        print("失败：%s" % exc, file=sys.stderr, flush=True)
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
