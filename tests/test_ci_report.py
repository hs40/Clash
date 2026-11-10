"""ENG-05 中文 CI 测试报告测试（接缝：build_report）。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_report  # noqa: E402

RESULTS = [
    {
        "name": "tests.test_a.test_ok",
        "status": "通过",
        "duration": 0.012,
        "detail": "",
    },
    {
        "name": "tests.test_b.test_fail",
        "status": "失败",
        "duration": 0.034,
        "detail": "Traceback (most recent call last):\nAssertionError: boom",
    },
    {
        "name": "tests.test_c.test_skip",
        "status": "跳过",
        "duration": 0.0,
        "detail": "not now",
    },
]


class BuildReportTest(unittest.TestCase):
    def build(self, results=RESULTS):
        return ci_report.build_report(
            results,
            generated_at="2026-11-10 12:00:00",
            python_version="3.12.3",
        )

    def test_summary_counts_and_statuses(self):
        report = self.build()
        self.assertIn("# Clash 配置工程测试报告", report)
        self.assertIn("生成时间：2026-11-10 12:00:00", report)
        self.assertIn("Python：3.12.3", report)
        self.assertIn("| 测试总数 | 3 |", report)
        self.assertIn("| 通过 | 1 |", report)
        self.assertIn("| 失败 | 1 |", report)
        self.assertIn("| 错误 | 0 |", report)
        self.assertIn("| 跳过 | 1 |", report)
        self.assertIn("tests.test_a.test_ok", report)
        self.assertIn("tests.test_c.test_skip", report)

    def test_failure_detail_is_included(self):
        report = self.build()
        self.assertIn("## 失败详情", report)
        self.assertIn("tests.test_b.test_fail", report)
        self.assertIn("AssertionError: boom", report)

    def test_no_failures_has_no_detail_section(self):
        report = self.build([RESULTS[0]])
        self.assertNotIn("## 失败详情", report)

    def test_pipe_in_name_is_escaped(self):
        results = [dict(RESULTS[0], name="a|b")]
        self.assertIn("a\\|b", self.build(results))

    def test_output_is_deterministic(self):
        self.assertEqual(self.build(), self.build())


if __name__ == "__main__":
    unittest.main()
