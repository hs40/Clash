"""平台验收编排中的纯检查（S2）。

所有网络动作由调用方注入，便于 unittest 用 fake 替换。
"""

import platform_probe as probe
import regions


def dns_no_leak(dns_query, fake_server="198.18.0.2",
                lan_server="192.168.2.1", public_server="223.5.5.5",
                fake_range=probe.FAKE_IP_RANGE):
    """Q26 自动三项中的 DNS 部分：fake-IP + LAN/公共 DNS 不返回真实 A。"""
    checks = {}

    def _query(server):
        try:
            return dns_query("example.com", server)
        except probe.ProbeError as exc:
            return {"error": str(exc), "answers": []}

    fake = _query(fake_server)
    fake_answers = [ip for ip in fake.get("answers", []) if probe.is_fake_ip(ip, fake_range)]
    checks["fake_ip"] = {
        "server": fake_server,
        "answers": fake.get("answers", []),
        "passed": bool(fake_answers),
        "detail": "返回 fake-IP" if fake_answers else "未返回 fake-IP",
    }

    for label, server in (("lan", lan_server), ("public", public_server)):
        if server is None:
            continue
        result = _query(server)
        real = [ip for ip in result.get("answers", []) if not probe.is_fake_ip(ip, fake_range)]
        if result.get("error"):
            passed = True
            detail = "被阻断或超时（符合预期）"
        elif real:
            passed = False
            detail = "返回真实 A 记录：%s" % ", ".join(real)
        else:
            passed = True
            detail = "被劫持为 fake-IP 或无真实 A"
        checks[label] = {
            "server": server,
            "answers": result.get("answers", []),
            "passed": passed,
            "detail": detail,
        }
    checks["passed"] = all(item["passed"] for item in checks.values() if isinstance(item, dict))
    return checks


def exit_country(ip_info, selected_group):
    """按当前选中节点的地区比对出口国家码；无法映射时明确降级。"""
    country = str((ip_info or {}).get("country") or "").upper()
    expected = probe.country_for_region(selected_group)
    if not country:
        return {"passed": None, "verified": False, "country": "", "group": selected_group,
                "detail": "出口 IP 查询未返回国家码"}
    if expected is None:
        detail = ("未取得选中节点，仅确认出口非 CN" if selected_group is None
                  else "节点地区无国家码映射；仅确认出口非 CN")
        return {"passed": country != "CN", "verified": False, "country": country,
                "group": selected_group, "detail": detail}
    matched = country in expected
    return {
        "passed": matched,
        "verified": True,
        "country": country,
        "group": selected_group,
        "expected": sorted(expected),
        "detail": "出口国家码与节点地区%s" % ("一致" if matched else "不一致"),
    }


def exit_country_for_node(ip_info, selected_node):
    """Q25：用选中叶子节点名识别地区，再与出口国家码比对。

    selected_node 为 Mihomo 控制接口返回的当前选中叶子节点名；为空时按 Q25
    降级为「出口非 CN」。地区沿用 ENG-01 的 regions.classify_node 关键词表，
    不另建映射。返回 exit_country 的结果并附上原始节点名。
    """
    if not selected_node:
        result = exit_country(ip_info, None)
        result["node"] = selected_node
        return result
    group = regions.classify_node(selected_node)
    result = exit_country(ip_info, group)
    result["node"] = selected_node
    return result


def http_ok(status, expected=204):
    return {"status": status, "expected": expected, "passed": status == expected}


def ipv6_disabled(states):
    """states: adapter name -> bool（True 表示 IPv6 绑定启用）。"""
    enabled = sorted(name for name, value in (states or {}).items() if value)
    return {"passed": not enabled, "enabled": enabled,
            "detail": "物理网卡 IPv6 已关闭" if not enabled else "仍有 IPv6 绑定启用"}
