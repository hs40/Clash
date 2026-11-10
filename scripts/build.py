"""Clash 配置构建器：把公共配置与平台配置合并成一份 Mihomo 配置。

用法：
    py scripts/build.py --platform all [--out dist]

合并契约见 docs/REQUIREMENTS.md §11：顶层浅合并，每个顶层键只有一个所有者；
白名单之外的键、公共与平台重复定义的键、同一文件内的重复键都会让构建失败。
"""

import ipaddress
import re
import sys
from pathlib import Path

import yaml

from regions import REGION_GROUPS, classify_node

REPO_ROOT = Path(__file__).resolve().parents[1]

# 公共配置的加载顺序即合并顺序，必须稳定。
COMMON_SOURCES = (
    "general.yaml",
    "proxies.yaml",
    "proxy-groups.yaml",
    "dns.yaml",
    "rules.yaml",
)

# 公共独占的顶层键。
COMMON_KEYS = (
    "mode",
    "log-level",
    "ipv6",
    "proxies",
    "proxy-groups",
    "dns",
    "rules",
)

# 每个平台独占的顶层键（docs/REQUIREMENTS.md §11）。
PLATFORM_KEYS = {
    "windows": ("mixed-port", "allow-lan", "tun"),
    "openclash": ("port", "allow-lan", "bind-address"),
}

# 输出键的固定顺序：相同输入必须产生字节一致的输出（§11 约束 5）。
KEY_ORDER = (
    "mode",
    "log-level",
    "ipv6",
    "mixed-port",
    "port",
    "allow-lan",
    "bind-address",
    "tun",
    "dns",
    "proxies",
    "proxy-groups",
    "rules",
)

# 策略组源文件允许的键；include 是构建期指令，不会进入最终产物（ENG-01）。
GROUP_SOURCE_KEYS = (
    "name",
    "type",
    "url",
    "interval",
    "tolerance",
    "proxies",
    "include",
)

# 策略组输出键的固定顺序。
GROUP_OUTPUT_KEYS = ("name", "type", "url", "interval", "tolerance")

# 规则层的固定顺序：层顺序优先于层内优先级（docs/REQUIREMENTS.md §5）。
RULE_LAYERS = ("special", "business", "base", "fallback")

# ENG-02 支持的规则类型。嵌套逻辑规则（AND/OR/NOT）不在本期范围。
RULE_TYPES = (
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "GEOIP",
    "IP-CIDR", "IP-CIDR6", "SRC-IP-CIDR",
    "DST-PORT", "SRC-PORT", "PROCESS-NAME", "PROCESS-PATH",
    "NETWORK", "RULE-SET", "MATCH",
)

# 地区组没有节点时使用的兜底策略组（项目负责人 2026-11-10 确认）。
EMPTY_REGION_FALLBACK = "自动选择"

# Mihomo 内置策略，允许出现在成员列表中。
BUILTIN_POLICIES = ("DIRECT", "REJECT", "REJECT-DROP", "PASS")

# ENG-03 DNS 基线：所有键都必须存在，缺失或类型不符使构建失败。
DNS_REQUIRED_KEYS = (
    "enable",
    "listen",
    "ipv6",
    "enhanced-mode",
    "fake-ip-range",
    "fake-ip-filter",
    "default-nameserver",
    "nameserver",
    "proxy-server-nameserver",
    "fallback",
    "fallback-filter",
)

DNS_SERVER_KEYS = (
    "default-nameserver",
    "nameserver",
    "proxy-server-nameserver",
    "fallback",
)


class ConfigError(Exception):
    """配置不满足合并契约或无法解析。"""


class _UniqueKeyLoader(yaml.SafeLoader):
    """拒绝重复键的 SafeLoader：PyYAML 默认静默保留后一个值。"""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConfigError("重复的键 %r" % (key,))
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def load_yaml_file(path):
    """读取 YAML 文件，任何解析问题都转换为带文件名的 ConfigError。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError("无法读取配置文件 %s：%s" % (path, exc)) from exc
    loader = _UniqueKeyLoader(text)
    try:
        data = loader.get_single_data()
    except ConfigError as exc:
        raise ConfigError("%s：%s" % (path, exc)) from exc
    except yaml.YAMLError as exc:
        raise ConfigError("%s：YAML 解析失败：%s" % (path, exc)) from exc
    finally:
        loader.dispose()
    if data is None:
        raise ConfigError("%s：文件为空" % path)
    if not isinstance(data, dict):
        raise ConfigError("%s：顶层必须是映射" % path)
    return data


def _merge_source(merged, owners, path, allowed_keys):
    data = load_yaml_file(path)
    for key in data:
        if key not in allowed_keys:
            raise ConfigError(
                "%s：未登记的顶层键 %r（允许：%s）"
                % (path, key, ", ".join(allowed_keys))
            )
        if key in merged:
            raise ConfigError(
                "顶层键 %r 重复定义：%s 与 %s" % (key, owners[key], path)
            )
        merged[key] = data[key]
        owners[key] = path


def _proxy_names(proxies, path):
    """校验节点列表并返回名称序列，名称必须非空且唯一。"""
    if not isinstance(proxies, list) or not proxies:
        raise ConfigError("%s：proxies 必须是非空列表" % path)
    names = []
    for index, proxy in enumerate(proxies, start=1):
        if not isinstance(proxy, dict):
            raise ConfigError("%s：第 %d 个节点必须是映射" % (path, index))
        name = proxy.get("name")
        if not isinstance(name, str) or not name:
            raise ConfigError("%s：第 %d 个节点缺少非空 name" % (path, index))
        if name in names:
            raise ConfigError("%s：节点名称重复：%r" % (path, name))
        names.append(name)
    return names


def _validate_groups(groups, proxy_names, path):
    """校验策略组外壳：名称唯一、键已登记、不与节点重名。"""
    if not isinstance(groups, list) or not groups:
        raise ConfigError("%s：proxy-groups 必须是非空列表" % path)
    names = []
    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            raise ConfigError("%s：第 %d 个策略组必须是映射" % (path, index))
        name = group.get("name")
        if not isinstance(name, str) or not name:
            raise ConfigError("%s：第 %d 个策略组缺少非空 name" % (path, index))
        if name in names:
            raise ConfigError("%s：策略组名称重复：%r" % (path, name))
        if name in proxy_names:
            raise ConfigError("%s：策略组与节点重名：%r" % (path, name))
        if not isinstance(group.get("type"), str) or not group["type"]:
            raise ConfigError("%s：策略组 %r 缺少 type" % (path, name))
        unknown = sorted(set(group) - set(GROUP_SOURCE_KEYS))
        if unknown:
            raise ConfigError(
                "%s：策略组 %r 含未登记的键：%s" % (path, name, ", ".join(unknown))
            )
        names.append(name)
    return names


def _expand_include(include, group_name, proxy_names, group_names, path):
    """把 include 指令展开成成员列表。"""
    if include == "all":
        return list(proxy_names)
    if isinstance(include, str) and include.startswith("region:"):
        region = include[len("region:"):]
        if region not in REGION_GROUPS:
            raise ConfigError(
                "%s：策略组 %r 引用了未知地区 %r（可用：%s）"
                % (path, group_name, region, "、".join(REGION_GROUPS))
            )
        members = [name for name in proxy_names if classify_node(name) == region]
        if members:
            return members
        if EMPTY_REGION_FALLBACK not in group_names:
            raise ConfigError(
                "%s：地区 %r 没有节点，且缺少兜底策略组 %r"
                % (path, region, EMPTY_REGION_FALLBACK)
            )
        return [EMPTY_REGION_FALLBACK]
    raise ConfigError(
        "%s：策略组 %r 的 include 指令未知：%r（可用：all、region:<地区名>）"
        % (path, group_name, include)
    )


def _check_cycles(groups, path):
    """拒绝策略组之间的循环引用，避免运行时无法求值。"""
    graph = {group["name"]: list(group["proxies"]) for group in groups}
    state = {}
    stack = []

    def visit(name):
        state[name] = "visiting"
        stack.append(name)
        for member in graph[name]:
            if member not in graph:
                continue
            if state.get(member) == "visiting":
                cycle = stack[stack.index(member):] + [member]
                raise ConfigError(
                    "%s：策略组循环引用：%s" % (path, " → ".join(cycle))
                )
            if state.get(member) is None:
                visit(member)
        stack.pop()
        state[name] = "done"

    for name in graph:
        if state.get(name) is None:
            visit(name)


def _resolve_proxy_groups(groups, proxies, path):
    """解析 include 并校验所有引用，返回可直接输出的策略组列表。"""
    proxy_names = _proxy_names(proxies, path)
    group_names = _validate_groups(groups, proxy_names, path)
    missing_regions = [name for name in REGION_GROUPS if name not in group_names]
    if missing_regions:
        raise ConfigError(
            "%s：缺少地区入口策略组：%s" % (path, "、".join(missing_regions))
        )
    resolved = []
    for group in groups:
        name = group["name"]
        if "include" in group and "proxies" in group:
            raise ConfigError(
                "%s：策略组 %r 不能同时使用 include 与 proxies" % (path, name)
            )
        if "include" in group:
            members = _expand_include(
                group["include"], name, proxy_names, group_names, path
            )
        else:
            members = group.get("proxies")
            if not isinstance(members, list):
                raise ConfigError("%s：策略组 %r 缺少 proxies 列表" % (path, name))
        seen = set()
        for member in members:
            if not isinstance(member, str) or not member:
                raise ConfigError("%s：策略组 %r 含空成员" % (path, name))
            if (member not in proxy_names and member not in group_names
                    and member not in BUILTIN_POLICIES):
                raise ConfigError(
                    "%s：策略组 %r 引用了不存在的节点或策略组：%r"
                    % (path, name, member)
                )
            if member in seen:
                raise ConfigError("%s：策略组 %r 含重复成员：%r" % (path, name, member))
            seen.add(member)
        output = {key: group[key] for key in GROUP_OUTPUT_KEYS if key in group}
        output["proxies"] = list(members)
        resolved.append(output)
    _check_cycles(resolved, path)
    return resolved


def _sorted_entries(entries, layer):
    """校验单层条目并按 priority 升序返回 (priority, rule, where)。"""
    if not isinstance(entries, list):
        raise ConfigError("rules.%s：必须是列表" % layer)
    seen = set()
    items = []
    for index, entry in enumerate(entries, start=1):
        where = "rules.%s：第 %d 条规则" % (layer, index)
        if not isinstance(entry, dict):
            raise ConfigError("%s必须是映射" % where)
        unknown = sorted(set(entry) - {"priority", "rule"})
        if unknown:
            raise ConfigError("%s含未登记的键：%s" % (where, ", ".join(unknown)))
        priority = entry.get("priority")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ConfigError("%s的 priority 必须是整数" % where)
        rule = entry.get("rule")
        if not isinstance(rule, str) or not rule:
            raise ConfigError("%s的 rule 必须是非空字符串" % where)
        if priority in seen:
            raise ConfigError("%s的 priority 重复：%d" % (where, priority))
        seen.add(priority)
        items.append((priority, rule, where))
    return sorted(items, key=lambda item: item[0])


def _rule_target(rule, where, group_names):
    """校验规则语法与目标策略，返回 (类型, 目标)。"""
    parts = rule.split(",")
    if len(parts) < 2 or any(not part or part != part.strip() for part in parts):
        raise ConfigError("%s格式错误：%r" % (where, rule))
    rule_type = parts[0]
    if rule_type not in RULE_TYPES:
        raise ConfigError("%s类型不受支持：%r" % (where, rule_type))
    if rule_type == "MATCH":
        if len(parts) != 2:
            raise ConfigError("%s格式错误：%r" % (where, rule))
        target = parts[1]
    else:
        if len(parts) < 3:
            raise ConfigError("%s格式错误：%r" % (where, rule))
        target = parts[2]
    if target not in group_names and target not in BUILTIN_POLICIES:
        raise ConfigError("%s引用了不存在的策略：%r" % (where, target))
    return rule_type, target


def compile_rules(rules, group_names):
    """把四层规则编译成 Mihomo 的扁平规则列表。

    层顺序固定；层内按 priority 升序；输出不保留 priority 元数据。
    """
    if not isinstance(rules, dict):
        raise ConfigError("rules 必须是按层组织的映射")
    unknown = sorted(set(rules) - set(RULE_LAYERS))
    if unknown:
        raise ConfigError("rules：未知的规则层：%s" % ", ".join(unknown))
    missing = [layer for layer in RULE_LAYERS if layer not in rules]
    if missing:
        raise ConfigError("rules：缺少规则层：%s" % ", ".join(missing))
    group_names = set(group_names)
    compiled = []
    for layer in RULE_LAYERS:
        for _priority, rule, where in _sorted_entries(rules[layer], layer):
            rule_type, _target = _rule_target(rule, where, group_names)
            if rule_type == "MATCH" and layer != "fallback":
                raise ConfigError("%s：MATCH 只能出现在 fallback 层" % where)
            compiled.append(rule)
    if not compiled or compiled[-1].split(",", 1)[0] != "MATCH":
        raise ConfigError("rules：MATCH 必须是最后一条规则")
    if sum(1 for rule in compiled if rule.split(",", 1)[0] == "MATCH") != 1:
        raise ConfigError("rules：MATCH 必须且只能有一条")
    return compiled


def _dns_error(detail):
    raise ConfigError("dns：" + detail)


def _validate_dns_list(dns, key, ip_only=False):
    value = dns.get(key)
    if not isinstance(value, list) or not value:
        _dns_error("%s 必须是非空列表" % key)
    seen = set()
    for item in value:
        if not isinstance(item, str) or not item or item != item.strip():
            _dns_error("%s 的条目必须是非空字符串" % key)
        if item in seen:
            _dns_error("%s 存在重复条目：%r" % (key, item))
        if "::" in item or item.startswith("["):
            _dns_error("%s 不得包含 IPv6 地址：%r" % (key, item))
        if ip_only:
            try:
                address = ipaddress.ip_address(item)
            except ValueError:
                _dns_error("%s 必须是 IPv4 地址：%r" % (key, item))
            if address.version != 4:
                _dns_error("%s 必须是 IPv4 地址：%r" % (key, item))
        seen.add(item)
    return value


def _parse_dns_listen(value):
    if not isinstance(value, str) or value.count(":") != 1:
        _dns_error("listen 必须是 IPv4:端口 形式")
    host, port_text = value.split(":")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        _dns_error("listen 的主机必须是 IPv4 地址：%r" % host)
    if address.version != 4:
        _dns_error("listen 的主机必须是 IPv4 地址：%r" % host)
    if not re.fullmatch(r"[0-9]+", port_text):
        _dns_error("listen 的端口必须是整数")
    port = int(port_text)
    if not 1 <= port <= 65535:
        _dns_error("listen 的端口必须在 1-65535 之间")
    return host, port


def _is_dns_self_reference(server, host, port):
    references = {host + ":" + str(port)}
    if host == "0.0.0.0":
        references |= {"127.0.0.1:" + str(port), "localhost:" + str(port)}
    return any(reference in server for reference in references)


def validate_dns(dns):
    """校验 ENG-03 的 DNS 基线，返回原字典。"""
    if not isinstance(dns, dict):
        _dns_error("必须是映射")
    missing = [key for key in DNS_REQUIRED_KEYS if key not in dns]
    if missing:
        _dns_error("缺少键：%s" % ", ".join(missing))
    if dns["enable"] is not True:
        _dns_error("enable 必须为 true")
    if dns["ipv6"] is not False:
        _dns_error("ipv6 必须为 false（IPv4-only 基线）")
    if dns["enhanced-mode"] != "fake-ip":
        _dns_error("enhanced-mode 必须为 fake-ip")
    host, port = _parse_dns_listen(dns["listen"])

    fake_range = dns["fake-ip-range"]
    if not isinstance(fake_range, str):
        _dns_error("fake-ip-range 必须是字符串")
    try:
        network = ipaddress.ip_network(fake_range, strict=False)
    except ValueError:
        _dns_error("fake-ip-range 不是合法网段：%r" % fake_range)
    if network.version != 4:
        _dns_error("fake-ip-range 必须是 IPv4 网段")
    if not 8 <= network.prefixlen <= 30:
        _dns_error("fake-ip-range 的前缀长度必须在 8-30 之间")

    filters = dns["fake-ip-filter"]
    if not isinstance(filters, list) or not filters:
        _dns_error("fake-ip-filter 必须是非空列表")
    if any(not isinstance(item, str) or not item or item != item.strip() for item in filters):
        _dns_error("fake-ip-filter 的条目必须是非空字符串")
    if len(set(filters)) != len(filters):
        _dns_error("fake-ip-filter 存在重复条目")

    for key in DNS_SERVER_KEYS:
        _validate_dns_list(dns, key, ip_only=(key == "default-nameserver"))

    overlap = set(dns["nameserver"]) & set(dns["fallback"])
    if overlap:
        _dns_error("nameserver 与 fallback 不能重叠：%s" % ", ".join(sorted(overlap)))

    for key in DNS_SERVER_KEYS:
        for server in dns[key]:
            if _is_dns_self_reference(server, host, port):
                _dns_error("%s 指向 DNS 自身监听地址，存在转发循环：%r" % (key, server))

    fallback_filter = dns["fallback-filter"]
    if not isinstance(fallback_filter, dict):
        _dns_error("fallback-filter 必须是映射")
    if fallback_filter.get("geoip") is not True:
        _dns_error("fallback-filter.geoip 必须为 true")
    geoip_code = fallback_filter.get("geoip-code")
    if not isinstance(geoip_code, str) or geoip_code.upper() != "CN":
        _dns_error("fallback-filter.geoip-code 必须为 CN")

    return dns


def build_platform(platform, root=REPO_ROOT):
    """合并公共配置与指定平台配置，返回按键顺序排列的配置字典。"""
    if platform not in PLATFORM_KEYS:
        raise ConfigError(
            "未知平台 %r，可用平台：%s" % (platform, ", ".join(sorted(PLATFORM_KEYS)))
        )
    root = Path(root)
    merged = {}
    owners = {}
    for name in COMMON_SOURCES:
        _merge_source(merged, owners, root / "configs" / "common" / name, COMMON_KEYS)
    _merge_source(
        merged,
        owners,
        root / "configs" / platform / "platform.yaml",
        PLATFORM_KEYS[platform],
    )

    required = set(COMMON_KEYS) | set(PLATFORM_KEYS[platform])
    missing = sorted(required - set(merged))
    if missing:
        raise ConfigError("缺少顶层键：%s" % ", ".join(missing))

    if merged.get("ipv6") is not False:
        raise ConfigError("ipv6：必须为 false（IPv4-only 基线）")
    merged["dns"] = validate_dns(merged["dns"])
    dns_port = int(merged["dns"]["listen"].rsplit(":", 1)[1])
    for key in ("mixed-port", "port"):
        if key in merged and merged[key] == dns_port:
            raise ConfigError("dns.listen 端口与 %s 冲突：%d" % (key, dns_port))
    if platform == "windows":
        tun = merged.get("tun")
        hijack = tun.get("dns-hijack") if isinstance(tun, dict) else None
        if not isinstance(hijack, list) or "any:53" not in hijack:
            raise ConfigError("tun.dns-hijack：Windows 必须包含 any:53")

    merged["proxy-groups"] = _resolve_proxy_groups(
        merged["proxy-groups"], merged["proxies"], owners["proxy-groups"]
    )
    merged["rules"] = compile_rules(
        merged["rules"], {group["name"] for group in merged["proxy-groups"]}
    )

    return {key: merged[key] for key in KEY_ORDER if key in merged}


def dump_yaml(cfg):
    """把配置序列化为 UTF-8 文本；键顺序固定，不含时间戳。"""
    return yaml.safe_dump(
        cfg,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=4096,
    )


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="构建 Clash/Mihomo 配置")
    parser.add_argument(
        "--platform", required=True, choices=["all", "windows", "openclash"]
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "dist")
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT,
        help="源文件根目录（默认为仓库根目录）",
    )
    args = parser.parse_args(argv)

    targets = tuple(PLATFORM_KEYS) if args.platform == "all" else (args.platform,)
    try:
        rendered = {
            platform: dump_yaml(build_platform(platform, args.root))
            for platform in targets
        }
    except ConfigError as exc:
        print("构建失败：%s" % exc, file=sys.stderr)
        return 2

    for platform, text in rendered.items():
        directory = args.out / platform
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "config.yaml"
        path.write_text(text, encoding="utf-8", newline="\n")
        print("已生成 %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
