"""ENG-05 中文 CI 测试报告（接缝：build_report）。"""

import argparse
import os
import sys
import time
import unittest
from collections import Counter
from datetime import datetime
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUSES = ("通过", "失败", "错误", "跳过")


def _test_name(test):
    identifier = getattr(test, "id", None)
    return identifier() if callable(identifier) else str(test)


class _RecordingResult(unittest.TestResult):
    def __init__(self, stream=None, descriptions=None, verbosity=None):
        super().__init__(stream, descriptions, verbosity)
        self.records = []
        self._started = 0.0
        self._status = ("未知", "")

    def startTest(self, test):
        super().startTest(test)
        self._started = time.perf_counter()
        self._status = ("通过", "")

    def addSuccess(self, test):
        super().addSuccess(test)
        self._status = ("通过", "")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._status = ("失败", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._status = ("错误", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._status = ("跳过", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._status = ("通过", "预期失败")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._status = ("失败", "预期失败但通过了")

    def stopTest(self, test):
        duration = max(0.0, time.perf_counter() - self._started)
        self.records.append(
            {
                "name": _test_name(test),
                "status": self._status[0],
                "duration": round(duration, 4),
                "detail": self._status[1],
            }
        )
        super().stopTest(test)


def run_tests(start_dir=ROOT / "tests", pattern="test_*.py"):
    """发现并运行测试，返回 build_report 所需的结果列表。"""
    suite = unittest.TestLoader().discover(str(start_dir), pattern=pattern)
    result = unittest.TextTestRunner(
        stream=StringIO(), verbosity=0, resultclass=_RecordingResult
    ).run(suite)
    return result.records


def _escape_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def build_report(results, generated_at=None, python_version=None):
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    python_version = python_version or "%d.%d.%d" % sys.version_info[:3]
    counts = Counter(result["status"] for result in results)
    lines = [
        "# Clash 配置工程测试报告",
        "",
        "- 生成时间：%s" % generated_at,
        "- Python：%s" % python_version,
        "",
        "## 汇总",
        "",
        "| 指标 | 数量 |",
        "| --- | --- |",
        "| 测试总数 | %d |" % len(results),
    ]
    for status in STATUSES:
        lines.append("| %s | %d |" % (status, counts.get(status, 0)))
    lines.extend(
        [
            "",
            "## 测试明细",
            "",
            "| 测试 | 结果 | 耗时（秒） |",
            "| --- | --- | --- |",
        ]
    )
    for result in results:
        lines.append(
            "| %s | %s | %.4f |"
            % (
                _escape_cell(result["name"]),
                _escape_cell(result["status"]),
                result.get("duration", 0.0),
            )
        )

    failures = [
        result for result in results if result["status"] in ("失败", "错误")
    ]
    if failures:
        lines.extend(["", "## 失败详情", ""])
        for result in failures:
            lines.extend(
                [
                    "### %s" % result["name"],
                    "",
                    "~~~text",
                    (result.get("detail") or "").rstrip(),
                    "~~~",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="运行测试并生成中文 Markdown 报告")
    parser.add_argument("--output", default=str(ROOT / "ci-report.md"))
    parser.add_argument("--start-dir", default=str(ROOT / "tests"))
    args = parser.parse_args(argv)

    records = run_tests(args.start_dir)
    report = build_report(records)
    Path(args.output).write_text(report, encoding="utf-8", newline="\n")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(report)

    total = len(records)
    failures = sum(1 for r in records if r["status"] in ("失败", "错误"))
    print("测试报告：%s（%d 项，失败/错误 %d 项）" % (args.output, total, failures))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
