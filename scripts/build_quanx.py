"""iPhone/QuantumultX 配置构建（Q10 / Q19 / Q23）。

QuantumultX 非 Mihomo 内核：配置是 INI 分节格式，没有 mihomo -t 离线校验，
质量模型退化为本模块自建的结构校验 validate_quantx()。

单一数据源：scripts/regions.py 的地区关键词表；模板 configs/quantumultx/platform.conf。
产物入库路径 quantumultx/QuanX.conf 由 --check 保证与重新构建逐字节一致。
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import regions  # noqa: E402

TEMPLATE = "configs/quantumultx/platform.conf"
ARTIFACT = "quantumultx/QuanX.conf"
PLACEHOLDER = "# __QUANX_REGION_POLICIES__"

SECTIONS = (
    "[general]",
    "[task_local]",
    "[rewrite_local]",
    "[rewrite_remote]",
    "[server_local]",
    "[server_remote]",
    "[dns]",
    "[policy]",
    "[filter_remote]",
    "[filter_local]",
    "[http_backend]",
    "[mitm]",
)

POLICY_GROUPS = (
    "节点选择",
    "自动选择",
    *regions.REGION_GROUPS,
    "全球加速",
    "苹果服务",
    "兜底分流",
)
BUILTIN_POLICIES = frozenset(("direct", "proxy", "reject"))
FORBIDDEN = ("pass" + "phrase =", "p12 =", "?clash=", "MIILuQ")

CHECK_INTERVAL = 1200
TOLERANCE = 50

# [policy] 12 组图标（负责人 m18888「按原代码添加图标」+ m18923 选「归位+补齐」）。
# 9 个原有组逐行照抄现用 QuanX.conf；韩国节点归位 Orz-3 KR.png（原配置把它错挂在
# 「其他节点」上）；其他节点改 Qure World_Map.png；新增「节点选择」用 Qure Proxy.png。
# 远程 URL 沿用 Q15「QuanX 原生上游不锁 SHA-256」约定，不新增 assets/ 依赖；
# 图标只影响展示，不参与分流。
_QURE = "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/"
_ORZ = "https://raw.githubusercontent.com/Orz-3/mini/master/Color/"
POLICY_ICONS = {
    "节点选择": _QURE + "Proxy.png",
    "自动选择": _QURE + "Auto.png",
    "香港节点": _ORZ + "HK.png",
    "台湾节点": _ORZ + "TW.png",
    "日本节点": _ORZ + "JP.png",
    "韩国节点": _ORZ + "KR.png",
    "狮城节点": _ORZ + "SG.png",
    "美国节点": _ORZ + "US.png",
    "其他节点": _QURE + "World_Map.png",
    "全球加速": _ORZ + "Global.png",
    "苹果服务": _QURE + "Apple.png",
    "兜底分流": _ORZ + "Final.png",
}


def _token(keyword):
    """把单个关键词转成可拼进 server-tag-regex 的子表达式。

    与 regions._matches 保持一致：中文子串匹配，ASCII 关键词整词匹配。
    re.escape 会把空格转成反斜杠加空格，须还原，否则 ICU 端语义漂移。
    """
    escaped = re.escape(keyword).replace(chr(92) + " ", " ")
    if keyword.isascii():
        return r"(?<![A-Za-z])%s(?![A-Za-z])" % escaped
    return escaped


def _alternation(keywords):
    return "|".join(_token(keyword) for keyword in keywords)


def region_server_tag_regex(group):
    """按 REGION_GROUPS 先命中优先生成 QuantumultX server-tag-regex。

    每个节点名恰好命中一个地区组，与 regions.classify_node() 独立实现交叉验证。
    """
    if group == "自动选择":
        return ".*"
    if group not in regions.REGION_GROUPS:
        raise ValueError("未知地区组: %s" % group)
    if group == regions.OTHER_GROUP:
        named = [
            keyword
            for candidate in regions.REGION_GROUPS
            if candidate != regions.OTHER_GROUP
            for keyword in regions.REGION_KEYWORDS[candidate]
        ]
        return r"(?i)^(?!.*(%s)).*$" % _alternation(named)
    own = _alternation(regions.REGION_KEYWORDS[group])
    earlier = []
    for candidate in regions.REGION_GROUPS:
        if candidate == group:
            break
        if candidate == regions.OTHER_GROUP:
            continue
        earlier.extend(regions.REGION_KEYWORDS[candidate])
    if earlier:
        return r"(?i)^(?=.*(%s))(?!.*(%s)).*$" % (own, _alternation(earlier))
    return r"(?i)^(?=.*(%s)).*$" % own


def _auto_policy_lines():
    lines = []
    for group in ("自动选择", *regions.REGION_GROUPS):
        lines.append(
            "url-latency-benchmark=%s, server-tag-regex=%s, "
            "check-interval=%d, tolerance=%d, img-url=%s"
            % (
                group,
                region_server_tag_regex(group),
                CHECK_INTERVAL,
                TOLERANCE,
                POLICY_ICONS[group],
            )
        )
    return lines


def _headers(text):
    return tuple(
        stripped
        for stripped in (line.strip() for line in text.splitlines())
        if stripped.startswith("[") and stripped.endswith("]") and len(stripped) > 2
    )


def _section_map(text):
    sections = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and len(stripped) > 2:
            current = stripped
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return sections


def _effective(lines):
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";", "//")):
            continue
        result.append(stripped)
    return result


def validate_quantx(text):
    """S3 结构校验：通过返回 None，任何违例抛 ValueError。

    覆盖：12 段齐全且有序、12 策略组、static 成员与 force-policy 引用存在、
    server-tag-regex 语法、final 末位、无凭据、订阅段无 URL、占位行已替换。
    """
    if not isinstance(text, str) or not text:
        raise ValueError("配置文本为空")
    for forbidden in FORBIDDEN:
        if forbidden in text:
            raise ValueError("配置含禁止入库的内容: %s" % forbidden)
    if PLACEHOLDER in text:
        raise ValueError("地区策略占位行未替换")
    if _headers(text) != SECTIONS:
        raise ValueError("12 个段落缺失或顺序不符")

    sections = _section_map(text)
    policy = _effective(sections["[policy]"])
    names = []
    for line in policy:
        match = re.match(r"^(static|url-latency-benchmark)=([^,]+),", line)
        if match:
            names.append(match.group(2))
    expected = set(POLICY_GROUPS)
    if len(names) != len(POLICY_GROUPS) or set(names) != expected:
        raise ValueError("策略组集合与 Q20 基线不符")

    # 每个策略组必须带且仅带一个约定的 img-url（图标只影响展示，不参与分流）。
    for line in policy:
        match = re.match(r"^(static|url-latency-benchmark)=([^,]+),", line)
        if not match:
            continue
        group = match.group(2)
        icons = re.findall(r"(?:^|,)\s*img-url=([^,\s]+)", line)
        if len(icons) != 1 or icons[0] != POLICY_ICONS[group]:
            raise ValueError("策略组 %s 的图标缺失或与基线不符" % group)

    allowed = expected | BUILTIN_POLICIES
    for line in policy:
        if line.startswith("static="):
            members = [
                part.strip() for part in line[len("static="):].split(",")
                if not part.strip().startswith("img-url=")
            ][1:]
            for member in members:
                if member not in allowed:
                    raise ValueError("static 成员引用了不存在的策略: %s" % member)
        match = re.search(r"server-tag-regex=([^,]*)", line)
        if match:
            try:
                re.compile(match.group(1).strip())
            except re.error as exc:
                raise ValueError("server-tag-regex 语法错误") from exc

    for body in sections.values():
        for line in _effective(body):
            match = re.search(r"force-policy=([^,\s]+)", line)
            if match and match.group(1) not in allowed:
                raise ValueError("force-policy 目标不存在: %s" % match.group(1))

    for line in sections["[server_remote]"]:
        if "http://" in line or "https://" in line:
            raise ValueError("server_remote 段不得含订阅 URL")

    local = _effective(sections["[filter_local]"])
    finals = [line for line in local if line.startswith("final,")]
    if len(finals) != 1 or local[-1] != finals[0]:
        raise ValueError("final 必须是 filter_local 的最后一条有效规则")
    return None


def build_quantx(root=REPO_ROOT):
    """S2：读取模板、机械注入地区策略，返回完整 QuanX.conf 文本。"""
    root = Path(root)
    text = (root / TEMPLATE).read_text(encoding="utf-8")
    lines = text.splitlines()
    hits = [i for i, line in enumerate(lines) if line.strip() == PLACEHOLDER]
    if len(hits) != 1:
        raise ValueError("模板必须恰好含一个占位行，实际 %d 个" % len(hits))
    lines[hits[0]:hits[0] + 1] = _auto_policy_lines()
    result = "\n".join(lines) + "\n"
    validate_quantx(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="构建/校验 iPhone QuantumultX 配置")
    parser.add_argument("--out", help="输出目录（写入 QuanX.conf）")
    parser.add_argument("--root", default=str(REPO_ROOT), help="仓库根目录")
    parser.add_argument(
        "--check", action="store_true", help="校验入库产物是否与重新构建一致"
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    text = build_quantx(root)

    if args.check:
        committed = root / ARTIFACT
        if not committed.is_file():
            print("缺少入库产物: %s" % committed, file=sys.stderr)
            return 1
        if committed.read_bytes() != text.encode("utf-8"):
            print(
                "产物与重新构建不一致，请重新生成: %s" % committed, file=sys.stderr
            )
            return 1
        print("产物一致: %s" % committed)
        return 0

    target_dir = Path(args.out) if args.out else (root / ARTIFACT).parent
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "QuanX.conf"
    target.write_text(text, encoding="utf-8", newline="\n")
    print("已生成: %s" % target)
    return 0


if __name__ == "__main__":
    # Windows 默认控制台为 GBK；CI 已设 PYTHONUTF8=1。统一为 UTF-8，
    # 保证本机被工具以 UTF-8 捕获 stdout/stderr 时不会解码失败。
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
