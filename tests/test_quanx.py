"""iPhone/QuantumultX 配置构建测试（接缝 S1/S2/S3，Q19）。

不测：PyYAML 解析、私有函数、第三方 URL 可达性、真机可用性。
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_quanx  # noqa: E402
import regions  # noqa: E402
import security_scan  # noqa: E402

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

# [policy] 12 组图标契约（负责人 m18888「按原代码添加图标」+ m18923 选「归位+补齐」）。
# 9 个原有组逐行照抄现用 QuanX.conf；韩国节点归位 Orz-3 KR.png；
# 其他节点改 Qure World_Map.png；节点选择（新增组）用 Qure Proxy.png。
QURE_ICON = "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/"
ORZ_ICON = "https://raw.githubusercontent.com/Orz-3/mini/master/Color/"
EXPECTED_ICONS = {
    "节点选择": QURE_ICON + "Proxy.png",
    "自动选择": QURE_ICON + "Auto.png",
    "香港节点": ORZ_ICON + "HK.png",
    "台湾节点": ORZ_ICON + "TW.png",
    "日本节点": ORZ_ICON + "JP.png",
    "韩国节点": ORZ_ICON + "KR.png",
    "狮城节点": ORZ_ICON + "SG.png",
    "美国节点": ORZ_ICON + "US.png",
    "其他节点": QURE_ICON + "World_Map.png",
    "全球加速": ORZ_ICON + "Global.png",
    "苹果服务": QURE_ICON + "Apple.png",
    "兜底分流": ORZ_ICON + "Final.png",
}

# 覆盖：中文关键词、ASCII 整词、多地区命中优先级、无匹配兜底、RUSSIA 误命中。
NODE_NAMES = (
    "香港-01", "HK-01", "Hong Kong-01", "美国-香港-01",
    "台湾-01", "TW-01", "台北-01",
    "日本-01", "JP-01", "东京-01", "日本-美国-01",
    "韩国-01", "KR-01", "首尔-01", "新加坡-韩国-01",
    "新加坡-01", "狮城-01", "SG-01",
    "美国-01", "US-01", "USA-01", "洛杉矶-01",
    "RUSSIA-01", "JPEG-01", "德国-01",
)


def _section_lines(text, section):
    """返回某一段的正文行（不含段头）。"""
    lines = text.splitlines()
    start = lines.index(section)
    for end in range(start + 1, len(lines)):
        stripped = lines[end].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            return lines[start + 1:end]
    return lines[start + 1:]


def _body(text, section):
    """段落内的有效配置行（去掉空行与注释）。"""
    return [
        line.strip() for line in _section_lines(text, section)
        if line.strip() and not line.strip().startswith(("#", ";"))
    ]


class ValidateQuantxTest(unittest.TestCase):
    """S3：validate_quantx 的失败路径，用真实产物做变异，不做同义反复断言。"""

    def setUp(self):
        self.text = build_quanx.build_quantx(ROOT)

    def test_valid_output_passes(self):
        build_quanx.validate_quantx(self.text)

    def test_missing_section_is_rejected(self):
        with self.assertRaises(Exception):
            build_quanx.validate_quantx(self.text.replace("[mitm]\n", ""))

    def test_missing_policy_group_is_rejected(self):
        broken = "\n".join(
            line for line in self.text.splitlines()
            if not line.startswith("static=苹果服务,")
        ) + "\n"
        with self.assertRaises(Exception):
            build_quanx.validate_quantx(broken)

    def test_unknown_force_policy_is_rejected(self):
        broken = self.text.replace(
            "force-policy=美国节点", "force-policy=不存在的组", 1
        )
        with self.assertRaises(Exception):
            build_quanx.validate_quantx(broken)

    def test_invalid_regex_is_rejected(self):
        broken = self.text.replace("server-tag-regex=.*", "server-tag-regex=(", 1)
        with self.assertRaises(Exception):
            build_quanx.validate_quantx(broken)

    def test_final_must_be_last(self):
        lines = self.text.splitlines()
        i = next(k for k, line in enumerate(lines) if line.strip() == "final, 兜底分流")
        lines.insert(i + 1, "host-suffix, example.com, direct")
        with self.assertRaises(Exception):
            build_quanx.validate_quantx("\n".join(lines) + "\n")

    def test_placeholder_must_be_substituted(self):
        with self.assertRaises(Exception):
            build_quanx.validate_quantx(
                self.text + "\n# __QUANX_REGION_POLICIES__\n"
            )

    def test_certificate_and_subscription_are_rejected(self):
        for needle in (
            "pass" + "phrase = 4D001452",
            "p12 " + "= MIILuQIBAzCC",
            "https://example.com/sub?clash=REDACTED, tag=订阅占位",
        ):
            with self.subTest(value=needle[:12]):
                with self.assertRaises(Exception):
                    build_quanx.validate_quantx(self.text + "\n" + needle + "\n")

    def test_server_remote_url_is_rejected(self):
        broken = self.text.replace(
            "[server_remote]\n",
            "[server_remote]\nhttps://example.com/sub, tag=占位订阅\n",
        )
        with self.assertRaises(Exception):
            build_quanx.validate_quantx(broken)


class BuildQuantxTest(unittest.TestCase):
    """S2：build_quantx(root) -> str 的输出契约。"""

    @classmethod
    def setUpClass(cls):
        cls.text = build_quanx.build_quantx(ROOT)

    def test_all_sections_present_in_order(self):
        headers = tuple(
            line.strip() for line in self.text.splitlines()
            if line.strip().startswith("[") and line.strip().endswith("]")
        )
        self.assertEqual(headers, SECTIONS)

    def test_twelve_policy_groups(self):
        names = []
        for line in _body(self.text, "[policy]"):
            match = re.match(r"^(static|url-latency-benchmark)=([^,]+),", line)
            if match:
                names.append(match.group(2))
        self.assertEqual(len(names), 12)
        self.assertCountEqual(names, POLICY_GROUPS)

    def test_no_google_or_ai_policy_groups(self):
        names = [
            match.group(2) for line in _body(self.text, "[policy]")
            for match in [re.match(r"^(static|url-latency-benchmark)=([^,]+),", line)]
            if match
        ]
        for name in ("Google", "OpenAI", "Claude", "Cursor"):
            self.assertNotIn(name, names)

    def test_region_regex_matches_independent_classifier(self):
        for name in NODE_NAMES:
            with self.subTest(node=name):
                matched = [
                    group for group in regions.REGION_GROUPS
                    if re.search(build_quanx.region_server_tag_regex(group), name)
                ]
                self.assertEqual(len(matched), 1, (name, matched))
                self.assertEqual(matched[0], regions.classify_node(name))

    def test_auto_policy_timing_parameters(self):
        body = [
            line for line in _body(self.text, "[policy]")
            if line.startswith("url-latency-benchmark=")
        ]
        self.assertEqual(len(body), 8)
        for line in body:
            self.assertIn("check-interval=1200", line)
            self.assertIn("tolerance=50", line)

    def test_no_credentials_or_subscription_urls(self):
        for forbidden in ("pass" + "phrase =", "p12 =", "?clash=", "MIILuQ"):
            self.assertNotIn(forbidden, self.text)
        remote = "\n".join(_section_lines(self.text, "[server_remote]"))
        self.assertNotIn("http://", remote)
        self.assertNotIn("https://", remote)

    def test_conf_is_clean_under_security_scan(self):
        self.assertEqual(
            security_scan.scan_text(self.text, "quantumultx/QuanX.conf"), []
        )

    def test_final_is_last_filter_rule(self):
        body = _body(self.text, "[filter_local]")
        self.assertEqual(body[-1], "final, 兜底分流")
        self.assertEqual(len([line for line in body if line.startswith("final,")]), 1)

    def test_inline_rule_count_and_deleted_business_rules(self):
        body = _body(self.text, "[filter_local]")
        # 负责人 2026-11-17 新增 2 条 aqhouse 直连（21 → 23）。
        self.assertEqual(len(body), 23)
        joined = "\n".join(body)
        for domain in (
            "google.com", "googleapis.com", "gstatic.com", "googleusercontent.com",
            "openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com",
            "anthropic.com", "claude.ai", "cursor.com", "cursor.sh",
        ):
            self.assertNotIn(domain, joined)

    def test_aqhouse_direct_rules_are_in_filter_local(self):
        body = _body(self.text, "[filter_local]")
        self.assertIn("host-suffix, aqhouse.net, direct", body)
        self.assertIn("ip-cidr, 202.104.194.190/32, direct", body)
        # 必须位于 final 兜底之前。
        self.assertLess(
            body.index("host-suffix, aqhouse.net, direct"),
            body.index("final, 兜底分流"),
        )
        self.assertLess(
            body.index("ip-cidr, 202.104.194.190/32, direct"),
            body.index("final, 兜底分流"),
        )

    def test_remote_entry_counts(self):
        remote = [
            line for line in _body(self.text, "[filter_remote]")
            if line.startswith("http")
        ]
        self.assertEqual(len(remote), 9)
        rewrite = [
            line for line in _body(self.text, "[rewrite_remote]")
            if line.startswith("http")
        ]
        self.assertEqual(len(rewrite), 30)

    def test_deleted_dangling_remote_rules_absent(self):
        remote = "\n".join(_section_lines(self.text, "[filter_remote]"))
        for tag in ("Spotify音乐", "国际媒体", "哔哩哔哩"):
            self.assertNotIn("tag=" + tag, remote)

    def test_reproducible_and_committed_file_matches(self):
        first = build_quanx.build_quantx(ROOT)
        second = build_quanx.build_quantx(ROOT)
        self.assertEqual(first, second)
        committed = (ROOT / "quantumultx" / "QuanX.conf").read_bytes()
        self.assertEqual(committed, first.encode("utf-8"))


class CliTest(unittest.TestCase):
    """S1：CLI 退出码、落盘、可重复构建、--check 一致守卫。"""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_quanx.py"), *args],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            errors="replace",
        )

    def test_cli_writes_reproducible_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            first_run = self._run("--out", str(out))
            self.assertEqual(first_run.returncode, 0, first_run.stderr)
            first = (out / "QuanX.conf").read_bytes()
            second_run = self._run("--out", str(out))
            self.assertEqual(second_run.returncode, 0, second_run.stderr)
            self.assertEqual((out / "QuanX.conf").read_bytes(), first)
            self.assertEqual(first, build_quanx.build_quantx(ROOT).encode("utf-8"))

    def test_cli_check_passes(self):
        result = self._run("--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_check_detects_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "configs" / "quantumultx"
            source.mkdir(parents=True)
            template = (
                ROOT / "configs" / "quantumultx" / "platform.conf"
            ).read_text(encoding="utf-8")
            (source / "platform.conf").write_text(
                template.replace(
                    "server_check_timeout = 3000", "server_check_timeout = 9000"
                ),
                encoding="utf-8", newline="\n",
            )
            target = root / "quantumultx"
            target.mkdir()
            (target / "QuanX.conf").write_bytes(
                (ROOT / "quantumultx" / "QuanX.conf").read_bytes()
            )
            result = self._run("--check", "--root", str(root))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


class PolicyIconTest(unittest.TestCase):
    """[policy] 12 组图标（负责人 m18888「按原代码添加图标」+ m18923 映射选择）。"""

    @classmethod
    def setUpClass(cls):
        cls.text = build_quanx.build_quantx(ROOT)

    @staticmethod
    def _policy_entries(text):
        entries = {}
        for line in _body(text, "[policy]"):
            match = re.match(r"^(static|url-latency-benchmark)=([^,]+),", line)
            if not match:
                continue
            icon = re.search(r"(?:^|,)\s*img-url=([^,\s]+)", line)
            entries[match.group(2)] = icon.group(1) if icon else None
        return entries

    def test_all_twelve_groups_have_icon(self):
        entries = self._policy_entries(self.text)
        self.assertEqual(set(entries), set(POLICY_GROUPS))
        self.assertEqual(len(entries), 12)
        self.assertTrue(all(entries.values()), entries)

    def test_icons_match_agreed_mapping(self):
        self.assertEqual(self._policy_entries(self.text), EXPECTED_ICONS)

    def test_icons_are_https_png_urls(self):
        for group, url in self._policy_entries(self.text).items():
            with self.subTest(group=group):
                self.assertTrue(url.startswith("https://"), url)
                self.assertTrue(url.endswith(".png"), url)

    def test_missing_icon_is_rejected(self):
        broken = self.text.replace(
            ", img-url=" + EXPECTED_ICONS["节点选择"], "", 1
        )
        with self.assertRaises(Exception):
            build_quanx.validate_quantx(broken)

    def test_wrong_icon_is_rejected(self):
        broken = self.text.replace(
            EXPECTED_ICONS["韩国节点"], "https://example.com/wrong.png", 1
        )
        with self.assertRaises(Exception):
            build_quanx.validate_quantx(broken)

class CiWorkflowTest(unittest.TestCase):
    def test_ci_workflow_checks_quanx_artifact(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("build_quanx.py --check", workflow)


if __name__ == "__main__":
    unittest.main()
