"""ENG-05 CI/CODEOWNERS 策略测试（接缝：check_workflow / check_codeowners）。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_policy  # noqa: E402

VALID_WORKFLOW = """name: CI
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with:
          persist-credentials: false
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065
        with:
          python-version: "3.12.3"
"""

VALID_CODEOWNERS = """* @hs40
/.github/ @hs40
/scripts/ @hs40
/configs/common/ @hs40
/security/ @hs40
/docs/REQUIREMENTS.md @hs40
"""


class WorkflowPolicyTest(unittest.TestCase):
    def check(self, text=VALID_WORKFLOW):
        return ci_policy.check_workflow(text)

    def test_valid_workflow_passes(self):
        self.assertEqual(self.check(), [])

    def test_missing_permissions_is_rejected(self):
        text = VALID_WORKFLOW.replace("permissions:\n  contents: read\n", "")
        self.assertTrue(any("permissions" in e for e in self.check(text)))

    def test_write_permission_is_rejected(self):
        text = VALID_WORKFLOW.replace("contents: read", "contents: write")
        self.assertTrue(any("只读" in e for e in self.check(text)))

    def test_pull_request_target_is_rejected(self):
        text = VALID_WORKFLOW.replace("pull_request:", "pull_request_target:")
        self.assertTrue(any("pull_request_target" in e for e in self.check(text)))

    def test_unpinned_action_is_rejected(self):
        text = VALID_WORKFLOW.replace(
            "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
            "actions/checkout@v4",
        )
        self.assertTrue(any("完整 SHA" in e for e in self.check(text)))

    def test_secrets_context_is_rejected(self):
        text = VALID_WORKFLOW + (
            "      - run: echo " + "$" + "{{ secrets.TOKEN }}\n"
        )
        self.assertTrue(any("Secrets" in e for e in self.check(text)))

    def test_checkout_must_disable_persist_credentials(self):
        text = VALID_WORKFLOW.replace(
            "        with:\n          persist-credentials: false\n", ""
        )
        self.assertTrue(any("persist-credentials" in e for e in self.check(text)))

    def test_windows_runner_is_required(self):
        text = VALID_WORKFLOW.replace("windows-latest", "ubuntu-latest")
        self.assertTrue(any("windows-latest" in e for e in self.check(text)))

    def test_main_push_is_required(self):
        text = VALID_WORKFLOW.replace("    branches: [main]\n", "")
        self.assertTrue(any("main" in e for e in self.check(text)))


class CodeownersPolicyTest(unittest.TestCase):
    def test_valid_codeowners_passes(self):
        self.assertEqual(ci_policy.check_codeowners(VALID_CODEOWNERS), [])

    def test_missing_core_path_is_rejected(self):
        errors = ci_policy.check_codeowners(
            VALID_CODEOWNERS.replace("/scripts/ @hs40\n", "")
        )
        self.assertTrue(any("/scripts/" in e for e in errors))

    def test_wrong_owner_is_rejected(self):
        errors = ci_policy.check_codeowners(
            VALID_CODEOWNERS.replace("/security/ @hs40", "/security/ @other")
        )
        self.assertTrue(any("@hs40" in e for e in errors))


class ActualPolicyFilesTest(unittest.TestCase):
    def test_actual_workflow_and_codeowners_pass_policy(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        codeowners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        self.assertEqual(ci_policy.check_workflow(workflow), [])
        self.assertEqual(ci_policy.check_codeowners(codeowners), [])


if __name__ == "__main__":
    unittest.main()
