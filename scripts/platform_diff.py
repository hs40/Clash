"""平台配置差异的纯函数（S2）。

只处理内存中的配置字典，不读写文件、不访问网络。
"""

import difflib
import hashlib

import yaml


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SECRET_KEYS = ("password", "uuid", "private-key", "pre-shared-key", "auth", "token",
               "secret", "short-id")


def redact_config(config):
    """返回可写入本机报告的脱敏副本：去掉节点凭据、订阅 URL 和大 Payload。"""
    if not isinstance(config, dict):
        return {}
    result = {}
    for key, value in config.items():
        if key == "proxies":
            result[key] = [
                {field: item.get(field) for field in ("name", "type") if field in item}
                for item in (value or [])
                if isinstance(item, dict)
            ]
        elif key == "proxy-providers":
            result[key] = sorted(value) if isinstance(value, dict) else []
        elif key == "rule-providers" and isinstance(value, dict):
            providers = {}
            for name, provider in value.items():
                if not isinstance(provider, dict):
                    providers[name] = provider
                    continue
                clean = {k: v for k, v in provider.items() if k != "payload"}
                clean["payload_count"] = len(provider.get("payload") or [])
                providers[name] = clean
            result[key] = providers
        elif key in SECRET_KEYS:
            result[key] = "[REDACTED]"
        else:
            result[key] = _redact_value(value)
    return result


def _redact_value(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k in SECRET_KEYS else _redact_value(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def align_owned(before, after):
    """只保留 after 拥有的键，避免把 Verge 运行时注入键当成部署删除项。

    列表整体保留（节点定义、规则、组成员都不做字段级裁剪）；嵌套字典
    递归裁剪，用于 tun、dns、rule-providers 这类平台只拥有部分子键的对象。
    """
    if not isinstance(before, dict) or not isinstance(after, dict):
        return before
    result = {}
    for key, expected in after.items():
        if key not in before:
            continue
        value = before[key]
        if isinstance(value, dict) and isinstance(expected, dict):
            result[key] = align_owned(value, expected)
        else:
            result[key] = value
    return result


def _names(items):
    result = []
    for item in items or []:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = item
        if isinstance(name, str) and name:
            result.append(name)
    return result


def _rules_digest(rules):
    return sha256_text("\n".join(str(rule) for rule in rules or []))


def summarize_config(before, after, files=None):
    """返回可审计的配置摘要；不包含节点凭据。"""
    before = before or {}
    after = after or {}
    old_proxies = _names(before.get("proxies"))
    new_proxies = _names(after.get("proxies"))
    old_groups = _names(before.get("proxy-groups"))
    new_groups = _names(after.get("proxy-groups"))
    old_rules = list(before.get("rules") or [])
    new_rules = list(after.get("rules") or [])
    old_dns = before.get("dns") if isinstance(before.get("dns"), dict) else {}
    new_dns = after.get("dns") if isinstance(after.get("dns"), dict) else {}
    summary = {
        "proxies": {
            "before": len(old_proxies),
            "after": len(new_proxies),
            "added": [name for name in new_proxies if name not in old_proxies],
            "removed": [name for name in old_proxies if name not in new_proxies],
        },
        "groups": {
            "before": old_groups,
            "after": new_groups,
            "added": [name for name in new_groups if name not in old_groups],
            "removed": [name for name in old_groups if name not in new_groups],
        },
        "ports": {
            key: {"before": before.get(key), "after": after.get(key)}
            for key in ("mixed-port", "port", "socks-port", "allow-lan")
        },
        "dns": {
            key: {"before": old_dns.get(key), "after": new_dns.get(key)}
            for key in ("listen", "enhanced-mode", "fake-ip-range", "nameserver", "fallback")
        },
        "rules": {
            "before": len(old_rules),
            "after": len(new_rules),
            "sha256": _rules_digest(new_rules),
        },
        "rule_providers": {
            "before": sorted((before.get("rule-providers") or {}).keys()),
            "after": sorted((after.get("rule-providers") or {}).keys()),
        },
        "files": list(files or []),
    }
    summary["has_changes"] = bool(
        summary["proxies"]["added"]
        or summary["proxies"]["removed"]
        or summary["groups"]["added"]
        or summary["groups"]["removed"]
        or any(v["before"] != v["after"] for v in summary["ports"].values())
        or any(v["before"] != v["after"] for v in summary["dns"].values())
        or old_rules != new_rules
        or summary["rule_providers"]["before"] != summary["rule_providers"]["after"]
    )
    return summary


def _short_list(values, limit=5):
    values = list(values)
    if len(values) <= limit:
        return "、".join(values) if values else "无"
    return "、".join(values[:limit]) + " 等 %d 个" % len(values)


def render_summary(summary, platform=""):
    lines = []
    if platform:
        lines.append("平台：%s" % platform)
    proxies = summary["proxies"]
    lines.append(
        "节点：%d -> %d（新增 %s；删除 %s）" % (
            proxies["before"], proxies["after"],
            _short_list(proxies["added"]), _short_list(proxies["removed"]),
        )
    )
    groups = summary["groups"]
    lines.append(
        "策略组：%d -> %d（新增 %s；删除 %s）" % (
            len(groups["before"]), len(groups["after"]),
            _short_list(groups["added"]), _short_list(groups["removed"]),
        )
    )
    for key, value in summary["ports"].items():
        if value["before"] != value["after"]:
            lines.append("%s：%r -> %r" % (key, value["before"], value["after"]))
    for key, value in summary["dns"].items():
        if value["before"] != value["after"]:
            lines.append("DNS %s：%r -> %r" % (key, value["before"], value["after"]))
    rules = summary["rules"]
    lines.append("规则：%d -> %d 条，SHA-256 %s" % (
        rules["before"], rules["after"], rules["sha256"]
    ))
    if summary["rule_providers"]["before"] != summary["rule_providers"]["after"]:
        lines.append(
            "Provider：%s -> %s" % (
                _short_list(summary["rule_providers"]["before"]),
                _short_list(summary["rule_providers"]["after"]),
            )
        )
    if summary["files"]:
        lines.append("将写文件：%s" % "、".join(summary["files"]))
    lines.append("变更：%s" % ("是" if summary["has_changes"] else "否"))
    return "\n".join(lines)


def _dump(config):
    return yaml.safe_dump(
        config or {},
        allow_unicode=True,
        sort_keys=True,
        default_flow_style=False,
        width=4096,
    )


def render_diff(before, after):
    """生成完整 unified diff；调用方负责把报告留在本机状态目录。"""
    old = _dump(before).splitlines(keepends=True)
    new = _dump(after).splitlines(keepends=True)
    diff = list(difflib.unified_diff(old, new, fromfile="before", tofile="after"))
    if not diff:
        return "配置内容无变化\n"
    return "".join(diff)
