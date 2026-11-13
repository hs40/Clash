"""平台验证探针：DNS、HTTP、出口 IP、端口。

真实部署只使用这些函数；unittest 用 fake opener/socket，不访问真实网络。
"""

import base64
import ipaddress
import json
import socket
import struct
import urllib.error
import urllib.request

IPINFO_URL = "https://ipinfo.io/json"
GSTATIC_URL = "https://www.gstatic.com/generate_204"
FAKE_IP_RANGE = "198.18.0.0/16"
REGION_COUNTRIES = {
    "香港节点": {"HK"},
    "台湾节点": {"TW"},
    "日本节点": {"JP"},
    "韩国节点": {"KR"},
    "狮城节点": {"SG"},
    "美国节点": {"US"},
}


class ProbeError(Exception):
    """探针超时、协议错误或结果不可解析。"""


def build_dns_query(name, qtype=1, txid=0x1234):
    if not name or ".." in name:
        raise ProbeError("非法 DNS 名称：%r" % name)
    labels = []
    for label in name.rstrip(".").split("."):
        encoded = label.encode("idna")
        if not 1 <= len(encoded) <= 63:
            raise ProbeError("DNS 标签长度非法：%r" % label)
        labels.append(bytes([len(encoded)]) + encoded)
    question = b"".join(labels) + b"\x00"
    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    return header + question + struct.pack("!HH", qtype, 1)


def _skip_name(data, offset):
    while True:
        if offset >= len(data):
            raise ProbeError("DNS 名称越界")
        length = data[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:
            if offset + 2 > len(data):
                raise ProbeError("DNS 压缩指针越界")
            return offset + 2
        offset += 1 + length


def parse_dns_response(data):
    if not isinstance(data, (bytes, bytearray)) or len(data) < 12:
        raise ProbeError("DNS 响应过短")
    txid, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
    offset = 12
    for _ in range(qdcount):
        offset = _skip_name(data, offset)
        if offset + 4 > len(data):
            raise ProbeError("DNS 问题段越界")
        offset += 4
    answers = []
    for _ in range(ancount):
        offset = _skip_name(data, offset)
        if offset + 10 > len(data):
            raise ProbeError("DNS 答案段越界")
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlength]
        if len(rdata) != rdlength:
            raise ProbeError("DNS 记录长度越界")
        offset += rdlength
        if rtype == 1 and rclass == 1 and rdlength == 4:
            answers.append(str(ipaddress.IPv4Address(rdata)))
    return {
        "id": txid,
        "rcode": flags & 0x0F,
        "truncated": bool(flags & 0x0200),
        "answers": answers,
    }


def dns_query(name, server, port=53, timeout=2.0, query=None):
    query = query or build_dns_query(name)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(query, (server, port))
        data, _ = sock.recvfrom(4096)
    except (OSError, socket.timeout) as exc:
        raise ProbeError("DNS 查询 %s@%s:%d 失败：%s" % (name, server, port, exc)) from exc
    finally:
        sock.close()
    result = parse_dns_response(data)
    if result["rcode"] != 0:
        raise ProbeError("DNS 查询 %s@%s 返回 rcode=%d" % (name, server, result["rcode"]))
    return result


def _proxy_headers(proxy_auth):
    if not proxy_auth:
        return {}
    encoded = base64.b64encode(proxy_auth.encode("utf-8")).decode("ascii")
    return {"Proxy-Authorization": "Basic " + encoded}


def _build_opener(proxy, proxy_auth):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    if proxy_auth:
        user, sep, pass_value = proxy_auth.partition(":")
        if sep:
            manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            manager.add_password(None, proxy, user, pass_value)
            handlers.append(urllib.request.ProxyBasicAuthHandler(manager))
    return urllib.request.build_opener(*handlers).open


def http_status(url, proxy=None, timeout=5.0, opener=None, proxy_auth=None):
    request = urllib.request.Request(
        url, headers=_proxy_headers(proxy_auth), method="GET"
    )
    if opener is None:
        opener = _build_opener(proxy, proxy_auth)
    try:
        response = opener(request, timeout=timeout)
        try:
            return response.getcode()
        finally:
            response.close()
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError) as exc:
        raise ProbeError("HTTP 请求失败 %s：%s" % (url, exc)) from exc


def public_ip_info(url=IPINFO_URL, proxy=None, timeout=15.0, opener=None,
                    proxy_auth=None):
    request = urllib.request.Request(
        url, headers=_proxy_headers(proxy_auth), method="GET"
    )
    if opener is None:
        opener = _build_opener(proxy, proxy_auth)
    try:
        response = opener(request, timeout=timeout)
        try:
            payload = response.read()
        finally:
            response.close()
    except urllib.error.HTTPError as exc:
        raise ProbeError("出口 IP 查询返回 HTTP %d" % exc.code) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ProbeError("出口 IP 查询失败：%s" % exc) from exc
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProbeError("出口 IP 查询结果不是 JSON") from exc
    if not isinstance(data, dict) or not data.get("ip"):
        raise ProbeError("出口 IP 查询结果缺少 ip")
    return {
        "ip": str(data["ip"]),
        "country": str(data.get("country") or "").upper(),
        "org": str(data.get("org") or ""),
    }


def port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_fake_ip(value, network=FAKE_IP_RANGE):
    try:
        address = ipaddress.ip_address(value)
        return address.version == 4 and address in ipaddress.ip_network(network, strict=False)
    except ValueError:
        return False


def country_for_region(group):
    return REGION_COUNTRIES.get(group)


def region_matches_country(group, country):
    expected = country_for_region(group)
    if expected is None or not country:
        return None
    return country.upper() in expected
