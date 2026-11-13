"""Windows/Clash Verge 平台适配器（S3）。

只改 Verge AppData 下的四个文件、物理网卡 IPv6 绑定和两条 DNS 护栏规则；
不修改系统 DNS、hosts、路由，不覆盖 FIB profile。所有副作用都通过可注入
runner 完成，便于 unittest 断言实际发出的命令。
"""

import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

import build
import dns_guard
import platform_diff
import platform_probe
import platform_verify
import verge_apply

FILES = (
    "profiles/Merge.yaml",
    "profiles/Script.js",
    "profiles.yaml",
    "verge.yaml",
)
PROXY = "http://127.0.0.1:7897"


INTEGRITY_SIDS = {
    "S-1-16-16384": "system",
    "S-1-16-12288": "high",
    "S-1-16-8192": "medium",
    "S-1-16-4096": "low",
}


def parse_integrity(text):
    """从 whoami /groups 输出识别完整性级别；SID 不随系统语言变化。"""
    for sid, level in INTEGRITY_SIDS.items():
        if sid in (text or ""):
            return level
    return "unknown"


def integrity_level(runner=None):
    """返回当前 Python 进程的 Windows 完整性级别。"""
    runner = runner or subprocess.run
    try:
        completed = runner(
            ["whoami", "/groups"], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        raise WindowsError("无法读取进程完整性级别：%s" % exc) from exc
    if completed.returncode != 0:
        raise WindowsError("无法读取进程完整性级别：whoami 退出码 %s" % completed.returncode)
    return parse_integrity(completed.stdout)


class WindowsError(Exception):
    """Windows 适配器命令失败或返回不可解析的结果。"""


def _ps_quote(value):
    return "'%s'" % str(value).replace("'", "''")


def _default_powershell(script):
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise WindowsError(detail or "powershell 退出码 %d" % completed.returncode)
    return (completed.stdout or "").strip()


def run_powershell(script, runner=None):
    try:
        return (runner or _default_powershell)(script)
    except WindowsError:
        raise
    except Exception as exc:
        raise WindowsError("powershell 执行失败：%s" % exc) from exc


def _json_list(output):
    if not output:
        return []
    try:
        data = json.loads(output.lstrip("\ufeff"))
    except ValueError as exc:
        raise WindowsError("命令输出不是 JSON：%s" % str(output)[:200]) from exc
    if isinstance(data, dict):
        return [data]
    if not isinstance(data, list):
        raise WindowsError("命令输出格式错误：%s" % str(output)[:200])
    return data


BINDING_SCRIPT = """
$ErrorActionPreference = 'Stop'
$items = @(Get-NetAdapter -Physical | ForEach-Object {
    $binding = Get-NetAdapterBinding -Name $_.Name -ComponentID 'ms_tcpip6' -ErrorAction SilentlyContinue
    if ($null -ne $binding) {
        [pscustomobject]@{
            Name = $_.Name
            Description = $_.InterfaceDescription
            Enabled = [bool]$binding.Enabled
        }
    }
})
$items | ConvertTo-Json -Compress
"""


def physical_ipv6_bindings(runner=None):
    """返回物理网卡的 IPv6 绑定状态；虚拟网卡（Mihomo/Tailscale）不在此列。"""
    rows = _json_list(run_powershell(BINDING_SCRIPT, runner))
    result = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("Name"):
            continue
        result.append({
            "name": str(row["Name"]),
            "description": str(row.get("Description") or ""),
            "enabled": bool(row.get("Enabled")),
        })
    return result


def ipv6_states(bindings):
    return {item["name"]: item["enabled"] for item in bindings if item.get("name")}


def _binding(name, action, runner):
    script = "%s-NetAdapterBinding -Name %s -ComponentID 'ms_tcpip6' -Confirm:$false" % (
        action, _ps_quote(name)
    )
    run_powershell(script, runner)


def disable_ipv6(runner=None):
    """关闭所有物理网卡的 IPv6 绑定，返回改动前的状态供回滚。"""
    bindings = physical_ipv6_bindings(runner)
    previous = ipv6_states(bindings)
    changed = [item["name"] for item in bindings if item["enabled"]]
    done = []
    try:
        for name in changed:
            _binding(name, "Disable", runner)
            done.append(name)
    except Exception:
        for name in done:
            try:
                _binding(name, "Enable", runner)
            except Exception:
                pass
        raise
    return {"previous": previous, "changed": changed}


def restore_ipv6(previous, runner=None):
    """只恢复部署前确实启用的物理网卡绑定。"""
    restored = []
    for name, enabled in (previous or {}).items():
        if enabled:
            _binding(name, "Enable", runner)
            restored.append(name)
    return restored


def _read_yaml(path):
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WindowsError("无法读取 %s：%s" % (path, exc)) from exc
    return data if isinstance(data, dict) else {}


def _order_groups(config):
    """按 Verge Script 的固定顺序排列策略组，未知组保留在末尾。"""
    groups = config.get("proxy-groups")
    if not isinstance(groups, list):
        return config
    by_name = {
        group.get("name"): group for group in groups
        if isinstance(group, dict) and group.get("name")
    }
    ordered = [by_name[name] for name in verge_apply.GROUP_ORDER if name in by_name]
    ordered += [group for group in groups if group not in ordered]
    normalized = []
    for group in ordered:
        if group.get("name") == "Google" and group.get("type") == "fallback":
            group = dict(group)
            group.setdefault("url", verge_apply.URL_TEST)
            group.setdefault("interval", 300)
        normalized.append(group)
    result = dict(config)
    result["proxy-groups"] = normalized
    return result


def projected_config(root, proxies, builder=None):
    """用运行时节点定义生成预期配置；只用于差异摘要，不写入 Verge。"""
    normalized = []
    for item in proxies or []:
        if isinstance(item, dict):
            normalized.append(item)
        elif isinstance(item, str) and item:
            normalized.append({"name": item, "type": "ss"})
    return _order_groups(
        (builder or build.build_platform)("windows", root, proxies=normalized)
    )


def plan_windows(appdir, root, mihomo, workdir, target_uid=None,
                 prepare=None, builder=None, runner=None, dns_list=None):
    """只读规划：预检节点、生成预期配置、返回摘要与实际改动项。"""
    prepare = prepare or verge_apply.prepare_plan
    try:
        plan = prepare(appdir, root, mihomo, workdir, target_uid)
    except verge_apply.ApplyError as exc:
        raise WindowsError(str(exc)) from exc
    before = _read_yaml(Path(appdir) / "clash-verge.yaml")
    after = projected_config(
        root, plan.get("proxies") or plan.get("proxy_names") or [], builder
    )
    safe_after = platform_diff.redact_config(after)
    safe_before = platform_diff.align_owned(
        platform_diff.redact_config(before), safe_after
    )
    summary = platform_diff.summarize_config(safe_before, safe_after, files=list(FILES))
    bindings = physical_ipv6_bindings(runner)
    states = ipv6_states(bindings)
    dns_error = None
    try:
        rules = dns_guard.list_rules() if dns_list is None else dns_list
    except dns_guard.DnsGuardError as exc:
        rules = []
        dns_error = str(exc)
    dns_ok = all(
        dns_guard.is_expected(
            {rule.get("DisplayName", ""): rule for rule in rules}.get(
                dns_guard.rule_name(protocol), {}
            ), protocol
        )
        for protocol in dns_guard.PROTOCOLS
    )
    ipv6_enabled = sorted(name for name, enabled in states.items() if enabled)
    summary["has_changes"] = bool(summary["has_changes"] or ipv6_enabled or not dns_ok)
    return {
        "verge": plan,
        "before": safe_before,
        "after": safe_after,
        "summary": summary,
        "diff": platform_diff.render_diff(safe_before, safe_after),
        "ipv6_bindings": bindings,
        "ipv6_states": states,
        "ipv6_enabled": ipv6_enabled,
        "dns_guard_ok": dns_ok,
        "dns_guard_error": dns_error,
    }


def _write_json(path, data):
    path = Path(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def _read_json(path):
    path = Path(path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def apply_windows(appdir, plan, backup_dir, reload=None, runner=None,
                  dns_apply=None, verify_timeout=45, sleep=None):
    """应用 Verge 迁移、关闭物理网卡 IPv6、补齐 DNS 护栏。

    配置已加载后的业务验证不在这里做；技术步骤失败会恢复全部已改状态。
    """
    backup_dir = Path(backup_dir)
    apply_kwargs = {"reload": reload, "stop": verge_apply.stop_verge}
    if verify_timeout is not None:
        apply_kwargs["verify_timeout"] = verify_timeout
    if sleep is not None:
        apply_kwargs["sleep"] = sleep
    try:
        result = verge_apply.apply_migration(
            appdir, plan["verge"], backup_dir, **apply_kwargs
        )
    except verge_apply.ApplyError as exc:
        raise WindowsError(str(exc)) from exc

    ipv6 = None
    dns_result = None
    try:
        ipv6 = disable_ipv6(runner)
        _write_json(backup_dir / "ipv6.json", ipv6)
        dns_result = (dns_apply or dns_guard.apply)(
            **(dict(runner=runner) if runner is not None else {})
        )
        _write_json(backup_dir / "dnsguard.json",
                    {"created": dns_result.get("created", []), "skipped": dns_result.get("skipped", [])})
    except Exception as exc:
        if ipv6:
            try:
                restore_ipv6(ipv6.get("previous"), runner)
            except Exception:
                pass
        if dns_result:
            try:
                for protocol in dns_result.get("created", []):
                    run_powershell(dns_guard.build_remove_script(
                        dns_guard.rule_name(protocol)), runner)
            except Exception:
                pass
        try:
            verge_apply.restore(Path(appdir), backup_dir)
            if reload is not None:
                reload()
        except Exception:
            pass
        raise WindowsError("%s；已回滚 Verge 文件与 IPv6/DNS 改动" % exc) from exc

    return {
        "ok": True,
        "backup": str(backup_dir),
        "profile": result.get("profile_name"),
        "proxies": result.get("expected_proxies"),
        "rules": result.get("expected_rules"),
        "ipv6_changed": ipv6.get("changed", []),
        "dns_guard": dns_result,
    }


def rollback_windows(appdir, backup_dir, reload=None, runner=None):
    """按备份清单恢复 Verge 文件、IPv6 绑定和本次新建的防火墙规则。"""
    backup_dir = Path(backup_dir)
    ipv6 = _read_json(backup_dir / "ipv6.json")
    dns_state = _read_json(backup_dir / "dnsguard.json")
    ipv6_restored = []
    if ipv6:
        ipv6_restored = restore_ipv6(ipv6.get("previous"), runner)
    for protocol in dns_state.get("created", []):
        run_powershell(
            dns_guard.build_remove_script(dns_guard.rule_name(protocol)), runner
        )
    try:
        manifest = verge_apply.restore(Path(appdir), backup_dir)
    except verge_apply.ApplyError as exc:
        raise WindowsError(str(exc)) from exc
    if reload is not None:
        reload()
    return {"ok": True, "files": list(manifest.get("files", {})),
            "ipv6_restored": ipv6_restored, "backup": str(backup_dir)}


def controller_base(config):
    value = (config or {}).get("external-controller")
    if not value:
        return None
    value = str(value).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    return "http://" + value


def _controller_get(config, path, opener=None, timeout=3.0):
    base = controller_base(config)
    if not base:
        raise WindowsError("配置没有 external-controller")
    headers = {}
    if config.get("secret"):
        headers["Authorization"] = "Bearer %s" % config["secret"]
    request = urllib.request.Request(base + path, headers=headers)
    with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def selected_proxy_name(config, opener=None, timeout=3.0):
    """沿 PROXY -> 自动选择 -> 节点 读取当前选中项；不输出控制接口密钥。"""
    name = "PROXY"
    path = []
    for _ in range(4):
        encoded = urllib.parse.quote(name, safe="")
        data = _controller_get(config, "/proxies/" + encoded, opener, timeout)
        path.append(name)
        now = data.get("now")
        if not now or now == name:
            return {"name": name, "type": data.get("type"), "path": path}
        name = now
    return {"name": name, "type": None, "path": path}


def status_windows(appdir, runner=None, dns_list=None):
    """只读状态：当前运行时配置计数、物理网卡 IPv6、DNS 护栏。"""
    path = Path(appdir) / "clash-verge.yaml"
    try:
        config = _read_yaml(path)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "config": {}}
    bindings = physical_ipv6_bindings(runner)
    states = ipv6_states(bindings)
    dns_error = None
    if dns_list is None:
        try:
            rules = dns_guard.list_rules()
        except dns_guard.DnsGuardError as exc:
            rules = []
            dns_error = str(exc)
    else:
        rules = dns_list
    by_name = {rule.get("DisplayName", ""): rule for rule in rules}
    dns_ok = all(
        dns_guard.is_expected(by_name.get(dns_guard.rule_name(protocol), {}), protocol)
        for protocol in dns_guard.PROTOCOLS
    )
    return {
        "ok": True,
        "config": {
            "mixed_port": config.get("mixed-port"),
            "port": config.get("port"),
            "socks_port": config.get("socks-port"),
            "mode": config.get("mode"),
            "ipv6": config.get("ipv6"),
            "proxies": len(config.get("proxies") or []),
            "groups": len(config.get("proxy-groups") or []),
            "rules": len(config.get("rules") or []),
            "tun": (config.get("tun") or {}).get("enable"),
        },
        "ipv6": states,
        "dns_guard_ok": dns_ok,
        "dns_guard_error": dns_error,
    }


def verify_windows(appdir, expected_proxies, expected_rules, runner=None,
                   dns_query=None, http_check=None, ip_info=None,
                   selected=None):
    """真实环境验收：配置契约、IPv6、DNS 不泄漏、代理 204、出口地区。"""
    runtime = _read_yaml(Path(appdir) / "clash-verge.yaml")
    try:
        verge_apply.verify_config(runtime, expected_proxies, expected_rules)
    except verge_apply.ApplyError as exc:
        raise WindowsError(str(exc)) from exc
    bindings = physical_ipv6_bindings(runner)
    ipv6 = platform_verify.ipv6_disabled(ipv6_states(bindings))
    dns = platform_verify.dns_no_leak(dns_query or platform_probe.dns_query)
    if http_check is None:
        try:
            status = platform_probe.http_status(
                "https://www.gstatic.com/generate_204", proxy=PROXY
            )
        except Exception as exc:
            http = {"status": None, "expected": 204, "passed": False,
                    "detail": str(exc)}
        else:
            http = platform_verify.http_ok(status)
    else:
        http = http_check
    try:
        info = ip_info() if ip_info is not None else platform_probe.public_ip_info(proxy=PROXY)
    except Exception as exc:
        info = {"error": str(exc)}
    try:
        current = selected() if selected is not None else selected_proxy_name(runtime)
        group = current.get("name") if isinstance(current, dict) else None
    except Exception:
        group = None
    country = platform_verify.exit_country(info, group)
    passed = bool(ipv6["passed"] and dns["passed"] and http["passed"]
                  and country["passed"] is True)
    return {
        "passed": passed,
        "config": {"proxies": expected_proxies, "rules": expected_rules},
        "ipv6": ipv6,
        "dns": dns,
        "http": http,
        "exit": country,
        "selected": group,
        "ip": {key: info.get(key) for key in ("ip", "country", "org", "error") if key in info},
    }
