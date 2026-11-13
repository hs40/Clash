"""iStoreOS/OpenClash 平台适配器（S3）。

只通过 SSH 执行固定命令：独立配置文件、root-only 备份、mihomo -t、UCI
切换与回滚。完整真实配置只留在内存和设备 root-only 备份，不写入本地报告。
"""

import json
import os
import shlex
import time
from datetime import datetime
from pathlib import Path

import yaml

import build
import platform_diff
import platform_probe
import platform_verify
from platform_ssh import SshError
from verge_preflight import PreflightError, filter_bad_short_ids

HOST = "192.168.2.10"
NEW_CONFIG = "/etc/openclash/config/clash-platform.yaml"
BACKUP_ROOT = "/etc/openclash/platform-backups"
CORE = "/etc/openclash/core/clash_meta"
COUNTRY_MMDB = "/etc/openclash/Country.mmdb"
TEST_DIR = "/tmp/clash-platform-test"
TEMP_CONFIG = "/etc/openclash/config/.clash-platform.yaml.tmp"
PORT = 7893
PROXY = "http://192.168.2.10:%d" % PORT
PROXY_AUTH_ENV = "CLASH_PROXY_AUTH"


class OpenClashError(Exception):
    """OpenClash 规划、备份、切换或校验失败。"""

    def __init__(self, message, restored=None):
        super().__init__(message)
        self.restored = restored


def _run(ssh, command, timeout=None, input_text=None):
    try:
        return ssh.run(command, timeout=timeout, input_text=input_text)
    except SshError as exc:
        raise OpenClashError(str(exc)) from exc


def _quote(path):
    return shlex.quote(path)


def read_state(ssh):
    """读取 UCI 路径、开关、目标文件是否存在及哈希；只读。"""
    target = _quote(NEW_CONFIG)
    script = f"""
cfg=$(uci -q get openclash.config.config_path)
printf 'CONFIG_PATH=%s\\n' "$cfg"
printf 'ENABLE=%s\\n' "$(uci -q get openclash.config.enable)"
printf 'DNS_PORT=%s\\n' "$(uci -q get openclash.config.dns_port)"
if [ -f {target} ]; then
    printf 'NEW_EXISTS=yes\\n'
    printf 'NEW_SHA=%s\\n' "$(sha256sum {target} | cut -d' ' -f1)"
else
    printf 'NEW_EXISTS=no\\n'
fi
if [ -n "$cfg" ] && [ -f "$cfg" ]; then
    printf 'CURRENT_SHA=%s\\n' "$(sha256sum "$cfg" | cut -d' ' -f1)"
fi
"""
    output = _run(ssh, script)
    state = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            state[key.strip()] = value.strip()
    state["new_exists"] = state.get("NEW_EXISTS") == "yes"
    state["config_path"] = state.get("CONFIG_PATH") or ""
    if not state["config_path"]:
        raise OpenClashError("OpenClash 未设置 config_path")
    return state


def load_node_source(path):
    """读取负责人指定的 FIB profile；只接受内联 proxies。"""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OpenClashError("无法读取节点来源 %s：%s" % (path, exc)) from exc
    except yaml.YAMLError as exc:
        raise OpenClashError("节点来源 YAML 解析失败：%s" % exc) from exc
    if not isinstance(data, dict):
        raise OpenClashError("节点来源顶层必须是映射")
    if data.get("proxy-providers"):
        raise OpenClashError("节点来源含 proxy-providers；平台只接受内联 proxies")
    proxies = data.get("proxies")
    if not isinstance(proxies, list) or not proxies:
        raise OpenClashError("节点来源缺少非空 proxies 列表")
    return proxies


def build_openclash_config(root, node_source, builder=None,
                           dns_listen="127.0.0.1:7874"):
    """生成 OpenClash 配置；只过滤 REALITY short-id，运行时问题交给 -t。"""
    proxies = load_node_source(node_source)
    try:
        good, bad = filter_bad_short_ids(proxies)
    except PreflightError as exc:
        raise OpenClashError(str(exc)) from exc
    if not good:
        raise OpenClashError("没有可用节点：全部被静态过滤")
    try:
        config = (builder or build.build_platform)(
            "openclash", root, proxies=good, dns_listen=dns_listen
        )
    except build.ConfigError as exc:
        raise OpenClashError("构建 OpenClash 配置失败：%s" % exc) from exc
    return {
        "config": config,
        "text": build.dump_yaml(config),
        "total": len(proxies),
        "static_bad": [item.get("name") for item in bad],
        "usable": len(good),
        "dns_listen": dns_listen,
    }


def plan_openclash(root, node_source, ssh, builder=None):
    """只读规划：设备状态、脱敏差异和当前配置文件哈希。"""
    built = build_openclash_config(root, node_source, builder)
    state = read_state(ssh)
    try:
        before_text = ssh.read_file(state["config_path"])
    except Exception as exc:
        raise OpenClashError("无法读取当前 OpenClash 配置：%s" % exc) from exc
    try:
        before = yaml.safe_load(before_text) or {}
    except yaml.YAMLError as exc:
        raise OpenClashError("当前 OpenClash 配置 YAML 解析失败：%s" % exc) from exc
    safe_before = platform_diff.redact_config(before)
    safe_after = platform_diff.redact_config(built["config"])
    summary = platform_diff.summarize_config(
        safe_before, safe_after, files=[NEW_CONFIG]
    )
    return {
        "built": built,
        "state": state,
        "before": safe_before,
        "summary": summary,
        "diff": platform_diff.render_diff(safe_before, safe_after),
    }


def _remote_backup_path(backup_dir):
    return "%s/%s" % (BACKUP_ROOT, Path(backup_dir).name)


def _write_json(path, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )


def _read_json(path):
    path = Path(path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _backup_remote(ssh, state, backup_dir):
    remote = _remote_backup_path(backup_dir)
    _run(ssh, "mkdir -p %s && chmod 700 %s" % (_quote(remote), _quote(remote)))
    _run(ssh, "cp -p %s %s/current.yaml && chmod 600 %s/current.yaml" % (
        _quote(state["config_path"]), _quote(remote), _quote(remote)
    ))
    if state.get("new_exists"):
        _run(ssh, "cp -p %s %s/previous-platform.yaml && chmod 600 %s/previous-platform.yaml" % (
            _quote(NEW_CONFIG), _quote(remote), _quote(remote)
        ))
    return remote


def _restart(ssh):
    _run(ssh, "/etc/init.d/openclash restart", timeout=120)


def _listening_ports(text):
    """解析 /proc/net/tcp{,6}；0A 为 LISTEN，本地端口为十六进制。"""
    ports = set()
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[3] != "0A":
            continue
        try:
            ports.add(int(fields[1].rsplit(":", 1)[1], 16))
        except (IndexError, ValueError):
            continue
    return ports


def _port_open(ssh, port=PORT):
    # iStoreOS 的 BusyBox 没有 ss；直接读 /proc/net/tcp 更可靠。
    output = _run(ssh, "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null || true")
    return port in _listening_ports(output)


def _wait_port(ssh, port=PORT, timeout=60, sleep=time.sleep):
    deadline = time.monotonic() + timeout
    while True:
        if _port_open(ssh, port):
            return True
        if time.monotonic() >= deadline:
            return False
        sleep(1)


def _config_process(ssh):
    """确认新配置对应的 mihomo 进程已启动，避免旧进程仍占用端口造成假就绪。"""
    name = NEW_CONFIG.rsplit("/", 1)[-1]
    pattern = "[%s]%s" % (name[0], name[1:])
    command = "ps w 2>/dev/null | grep %s || true" % _quote(pattern)
    return bool(_run(ssh, command).strip())


def _wait_config_process(ssh, timeout=60, sleep=time.sleep):
    deadline = time.monotonic() + timeout
    while True:
        if _config_process(ssh):
            return True
        if time.monotonic() >= deadline:
            return False
        sleep(1)


def _proxy_auth(environ=None):
    """只读一次性环境变量；仅在内存中使用，绝不写入磁盘或报告。

    环境变量由负责人在部署终端临时设置，平台不读取设备 UCI 中的认证，
    也不把凭据拼进 SSH 命令、命令行参数或日志。
    """
    source = os.environ if environ is None else environ
    value = source.get(PROXY_AUTH_ENV, "")
    return value or None


def _test_config(ssh):
    command = (
        "mkdir -p %s; cp -f %s %s/Country.mmdb 2>/dev/null || true; "
        "%s -t -f %s -d %s"
        % (_quote(TEST_DIR), _quote(COUNTRY_MMDB), _quote(TEST_DIR),
           _quote(CORE), _quote(TEMP_CONFIG), _quote(TEST_DIR))
    )
    return _run(ssh, command, timeout=120)


def _restore_remote(ssh, manifest):
    remote = manifest["remote_backup"]
    if manifest.get("new_exists"):
        _run(ssh, "cp -p %s/previous-platform.yaml %s && chmod 600 %s" % (
            _quote(remote), _quote(NEW_CONFIG), _quote(NEW_CONFIG)
        ))
    else:
        _run(ssh, "rm -f %s" % _quote(NEW_CONFIG))
    _run(ssh, "uci set openclash.config.config_path=%s" % _quote(manifest["old_config_path"]))
    _run(ssh, "uci commit openclash")
    _restart(ssh)


def apply_openclash(ssh, plan, backup_dir, verify_timeout=60, sleep=time.sleep):
    """上传临时文件 -> mihomo -t -> 原子替换 -> UCI 切换 -> 重启验收。

    任何失败都恢复旧 config_path 和旧文件；旧 FIB 配置从未被写。
    """
    backup_dir = Path(backup_dir)
    built = plan["built"]
    state = plan["state"]
    remote = _backup_remote(ssh, state, backup_dir)
    manifest = {
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "remote_backup": remote,
        "old_config_path": state["config_path"],
        "old_sha": state.get("CURRENT_SHA"),
        "new_exists": bool(state.get("new_exists")),
        "new_sha": build_hash(built["text"]),
        "target": NEW_CONFIG,
    }
    _write_json(backup_dir / "openclash.json", manifest)

    changed = False
    try:
        ssh.put_file(TEMP_CONFIG, built["text"])
        _run(ssh, "chmod 600 %s" % _quote(TEMP_CONFIG))
        output = _test_config(ssh)
        _run(ssh, "mv %s %s && chmod 600 %s" % (
            _quote(TEMP_CONFIG), _quote(NEW_CONFIG), _quote(NEW_CONFIG)
        ))
        changed = True
        _run(ssh, "uci set openclash.config.config_path=%s" % _quote(NEW_CONFIG))
        _run(ssh, "uci commit openclash")
        _restart(ssh)
        if not _wait_config_process(ssh, verify_timeout, sleep):
            raise OpenClashError("OpenClash 重启后未加载目标配置")
        if not _wait_port(ssh, PORT, verify_timeout, sleep):
            raise OpenClashError("OpenClash 重启后 %d 端口未监听" % PORT)
    except Exception as exc:
        restored = False
        restore_error = None
        try:
            _run(ssh, "rm -f %s" % _quote(TEMP_CONFIG))
            _restore_remote(ssh, manifest)
            restored = True
        except Exception as restore_exc:
            restore_error = str(restore_exc)
        if restored:
            message = "%s；已恢复旧 config_path" % exc
        else:
            message = "%s；恢复旧 config_path 失败：%s" % (exc, restore_error)
        raise OpenClashError(message, restored=restored) from exc
    return {
        "ok": True,
        "backup": str(backup_dir),
        "remote_backup": remote,
        "proxies": built["usable"],
        "static_bad": len(built["static_bad"]),
        "port": PORT,
        "new_sha": manifest["new_sha"],
        "test_output": output.strip()[-500:],
    }


def build_hash(text):
    return platform_diff.sha256_text(text)


def rollback_openclash(ssh, backup_dir):
    """按本机清单恢复设备旧 config_path 和旧文件，再重启 OpenClash。"""
    manifest = _read_json(Path(backup_dir) / "openclash.json")
    if not manifest:
        raise OpenClashError("备份目录缺少 openclash.json：%s" % backup_dir)
    _restore_remote(ssh, manifest)
    return {"ok": True, "restored": manifest.get("old_config_path"),
            "backup": str(backup_dir)}


def status_openclash(ssh):
    state = read_state(ssh)
    state["port_open"] = _port_open(ssh, PORT)
    return state


def _local_http_command():
    """设备本机 curl；认证经 stdin 传入，不出现在命令行参数或进程列表里。"""
    return (
        'IFS= read -r auth; '
        'if command -v curl >/dev/null 2>&1; then '
        'if [ -n "$auth" ]; then '
        f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 8 '
        f'-x http://127.0.0.1:{PORT} --proxy-user "$auth" '
        'https://www.gstatic.com/generate_204; '
        'else '
        f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 8 '
        f'-x http://127.0.0.1:{PORT} '
        'https://www.gstatic.com/generate_204; '
        'fi; else echo NO_CURL; fi'
    )


def verify_openclash(ssh, http_check=None, dns_query=None, ip_info=None,
                     dns_attempts=3, dns_sleep=time.sleep):
    """Q24 可自动观测项；真实 LAN 客户端/WebRTC/重启观察仍为人工项。"""
    auth = _proxy_auth()
    port = _port_open(ssh, PORT)
    try:
        local_status = _run(
            ssh, _local_http_command(), timeout=20,
            input_text=(auth or "") + "\n",
        ).strip()
    except OpenClashError:
        local_status = ""
    device_http = platform_verify.http_ok(
        int(local_status) if local_status.isdigit() else None
    )
    if http_check is None:
        try:
            code = platform_probe.http_status(
                "https://www.gstatic.com/generate_204", proxy=PROXY,
                proxy_auth=auth,
            )
        except Exception as exc:
            http = {"status": None, "expected": 204, "passed": False, "detail": str(exc)}
        else:
            http = platform_verify.http_ok(code)
    else:
        http = http_check
    query = dns_query or (lambda name, server: platform_probe.dns_query(
        name, "192.168.2.10", 53
    ))
    dns = None
    for attempt in range(max(1, dns_attempts)):
        dns = platform_verify.dns_no_leak(
            query,
            fake_server="192.168.2.10",
            lan_server=None,
            public_server=None,
        )
        if dns.get("fake_ip", {}).get("passed"):
            break
        if attempt + 1 < dns_attempts:
            dns_sleep(1)
    try:
        info = ip_info() if ip_info is not None else platform_probe.public_ip_info(
            proxy=PROXY, proxy_auth=auth
        )
    except Exception as exc:
        info = {"error": str(exc)}
    country = platform_verify.exit_country(info, None)
    passed = bool(port and device_http["passed"] and http["passed"]
                  and dns["passed"] and country["passed"] is True)
    return {
        "passed": passed,
        "port": port,
        "device_http": device_http,
        "http": http,
        "dns": dns,
        "exit": country,
        "ip": {key: info.get(key) for key in ("ip", "country", "org", "error") if key in info},
    }
