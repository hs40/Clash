"""Windows 防火墙 DNS 泄漏护栏。

负责人 2026-11-12 选择 C：阻断本机到 192.168.2.0/24 的 53 端口出站，
保留 TUN DNS 198.18.0.2，防止应用显式查询路由器 DNS 绕过 Mihomo。
负责人 2026-11-12 选择 A：放行受控解析器 192.168.2.10:53，其余 LAN
地址仍阻断；地址集合由该网段去掉 192.168.2.10/32 后汇总而成。

只增删两条 Windows 防火墙规则（UDP/TCP），不改系统 DNS、hosts、
路由或代理设置。需要管理员权限；--check 只读。
"""

import argparse
import ctypes
import ipaddress
import json
import os
import subprocess
import sys

RULE_GROUP = "Clash DNS Guard"
RULE_PREFIX = "Clash DNS Guard - Block LAN DNS"
PROTOCOLS = ("UDP", "TCP")
# 192.168.2.0/24 去掉 192.168.2.10/32 后的精确汇总。
REMOTE_ADDRESSES = (
    "192.168.2.0/29",
    "192.168.2.8/31",
    "192.168.2.11/32",
    "192.168.2.12/30",
    "192.168.2.16/28",
    "192.168.2.32/27",
    "192.168.2.64/26",
    "192.168.2.128/25",
)
REMOTE_ADDRESS = ",".join(REMOTE_ADDRESSES)
REMOTE_PORT = 53


class DnsGuardError(Exception):
    """防火墙命令失败或返回不可解析的结果。"""


def _protocol(value):
    protocol = str(value).upper()
    if protocol not in PROTOCOLS:
        raise ValueError("unsupported protocol: %s" % value)
    return protocol


def rule_name(protocol):
    return "%s (%s)" % (RULE_PREFIX, _protocol(protocol))


def rule_spec(protocol):
    protocol = _protocol(protocol)
    return {
        "DisplayName": rule_name(protocol),
        "Group": RULE_GROUP,
        "Direction": "Outbound",
        "Action": "Block",
        "Protocol": protocol,
        "RemoteAddress": REMOTE_ADDRESS,
        "RemotePort": str(REMOTE_PORT),
        "Profile": "Any",
        "Enabled": True,
    }


def _ps_quote(value):
    return "'%s'" % str(value).replace("'", "''")


STATUS_SCRIPT = """
$ErrorActionPreference = 'Stop'
Get-NetFirewallProfile | Out-Null
$names = @('Clash DNS Guard - Block LAN DNS (UDP)', 'Clash DNS Guard - Block LAN DNS (TCP)')
$rules = @(Get-NetFirewallRule -DisplayName 'Clash DNS Guard*' -ErrorAction SilentlyContinue | ForEach-Object {
    $port = $_ | Get-NetFirewallPortFilter
    $addr = $_ | Get-NetFirewallAddressFilter
    [pscustomobject]@{
        DisplayName = $_.DisplayName
        Enabled = $_.Enabled.ToString()
        Direction = $_.Direction.ToString()
        Action = $_.Action.ToString()
        Protocol = $port.Protocol
        RemoteAddress = ($addr.RemoteAddress -join ',')
        RemotePort = ($port.RemotePort -join ',')
        Profile = $_.Profile.ToString()
    }
})
$rules | ConvertTo-Json -Compress
"""


def _run_powershell(script):
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise DnsGuardError("无法启动 powershell.exe：%s" % exc) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise DnsGuardError(detail or "powershell 退出码 %d" % completed.returncode)
    return (completed.stdout or "").strip()


def list_rules(runner=_run_powershell):
    output = runner(STATUS_SCRIPT)
    if not output:
        return []
    try:
        data = json.loads(output)
    except ValueError as exc:
        raise DnsGuardError("防火墙状态不是 JSON：%s" % output[:200]) from exc
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise DnsGuardError("防火墙状态格式错误：%s" % output[:200])
    return [item for item in data if isinstance(item, dict) and item.get("DisplayName")]


def _text(value):
    return str(value).strip()


def _normalize_address(value):
    try:
        return str(ipaddress.ip_network(value.strip(), strict=False))
    except ValueError:
        return value.strip()


def _address_set(value):
    return {_normalize_address(part) for part in _text(value).split(",") if part.strip()}


def is_expected(rule, protocol):
    spec = rule_spec(protocol)
    return (
        _text(rule.get("DisplayName")) == spec["DisplayName"]
        and _text(rule.get("Enabled")).lower() == "true"
        and _text(rule.get("Direction")).lower() == "outbound"
        and _text(rule.get("Action")).lower() == "block"
        and _text(rule.get("Protocol")).upper() == spec["Protocol"]
        and _address_set(rule.get("RemoteAddress")) == set(REMOTE_ADDRESSES)
        and spec["RemotePort"] in _text(rule.get("RemotePort"))
        and _text(rule.get("Profile")).lower() == "any"
    )


def build_new_rule_script(protocol):
    spec = rule_spec(protocol)
    return (
        "New-NetFirewallRule -DisplayName %s -Group %s -Direction Outbound "
        "-Action Block -Protocol %s -RemoteAddress %s -RemotePort %s "
        "-Profile Any -Enabled True -Description %s"
        % (
            _ps_quote(spec["DisplayName"]),
            _ps_quote(spec["Group"]),
            spec["Protocol"],
            spec["RemoteAddress"],
            spec["RemotePort"],
            _ps_quote("Clash DNS Guard: block direct LAN DNS to prevent TUN bypass"),
        )
    )


def build_remove_script(name):
    return "Remove-NetFirewallRule -DisplayName %s -ErrorAction SilentlyContinue" % _ps_quote(name)


def apply(runner=_run_powershell):
    existing = {rule.get("DisplayName"): rule for rule in list_rules(runner=runner)}
    created = []
    skipped = []
    try:
        for protocol in PROTOCOLS:
            name = rule_name(protocol)
            current = existing.get(name)
            if current is not None and is_expected(current, protocol):
                skipped.append(protocol)
                continue
            if current is not None:
                runner(build_remove_script(name))
            runner(build_new_rule_script(protocol))
            created.append(protocol)
    except Exception:
        for protocol in created:
            try:
                runner(build_remove_script(rule_name(protocol)))
            except Exception:
                pass
        raise
    return {"created": created, "skipped": skipped}


def remove(runner=_run_powershell):
    removed = []
    for protocol in PROTOCOLS:
        runner(build_remove_script(rule_name(protocol)))
        removed.append(protocol)
    return removed


def is_admin():
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Windows DNS 泄漏护栏（阻断 LAN 53，保留 TUN DNS）")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="只读检查（默认）")
    action.add_argument("--apply", action="store_true", help="创建/修复两条出站阻断规则")
    action.add_argument("--remove", action="store_true", help="删除两条规则，恢复原状")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args(argv)

    try:
        if args.apply:
            if not is_admin():
                raise DnsGuardError("需要管理员权限；请用管理员 PowerShell 或双击管理员脚本")
            result = apply()
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print("已创建/修复：%s；已存在：%s" % (result["created"], result["skipped"]))
            return 0
        if args.remove:
            if not is_admin():
                raise DnsGuardError("需要管理员权限；请用管理员 PowerShell 或双击管理员脚本")
            result = remove()
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print("已删除：%s" % result)
            return 0

        rules = list_rules()
        by_name = {rule.get("DisplayName"): rule for rule in rules}
        status = {protocol: is_expected(by_name.get(rule_name(protocol), {}), protocol) for protocol in PROTOCOLS}
        result = {"rules": rules, "ok": all(status.values()), "status": status}
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            for protocol in PROTOCOLS:
                print("%s: %s" % (protocol, "OK" if status[protocol] else "MISSING/INVALID"))
            print("overall: %s" % ("OK" if result["ok"] else "NOT READY"))
        return 0 if result["ok"] else 1
    except (DnsGuardError, ValueError) as exc:
        print("DNS guard failed: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
