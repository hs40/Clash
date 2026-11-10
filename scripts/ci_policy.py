"""ENG-05 CI 工作流与 CODEOWNERS 静态策略检查（接缝：S7）。"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
SECRETS_RE = re.compile(r"\$\{\{\s*secrets\.", re.IGNORECASE)
REQUIRED_CODEOWNER_PATTERNS = (
    "*",
    "/.github/",
    "/scripts/",
    "/configs/common/",
    "/security/",
    "/docs/REQUIREMENTS.md",
)
OWNER = "@hs40"


def _load_yaml(text):
    try:
        data = yaml.load(text, Loader=yaml.BaseLoader)
    except yaml.YAMLError as exc:
        return None, ["CI 工作流 YAML 解析失败：%s" % exc]
    if not isinstance(data, dict):
        return None, ["CI 工作流根节点必须是映射"]
    return data, []


def _walk_uses(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "uses":
                yield item
            else:
                yield from _walk_uses(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_uses(item)


def check_workflow(text):
    data, errors = _load_yaml(text)
    if data is None:
        return errors

    if "pull_request_target" in text:
        errors.append("不允许使用 pull_request_target")
    if SECRETS_RE.search(text):
        errors.append("工作流不得引用 Secrets 上下文")

    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        errors.append("缺少只读 permissions 配置")
    elif any(value != "read" for value in permissions.values()):
        errors.append("permissions 必须全部为只读（read）")
    elif permissions.get("contents") != "read":
        errors.append("permissions 缺少 contents: read")

    event = data.get("on")
    if isinstance(event, str):
        event = {event: None}
    if not isinstance(event, dict) or "pull_request" not in event:
        errors.append("工作流必须响应 pull_request")
    push = event.get("push") if isinstance(event, dict) else None
    branches = push.get("branches") if isinstance(push, dict) else None
    if not isinstance(branches, list) or "main" not in branches:
        errors.append("工作流必须在 push main 时运行")

    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        errors.append("工作流缺少 jobs")
    else:
        for name, job in jobs.items():
            if not isinstance(job, dict):
                errors.append("job %s 必须是映射" % name)
                continue
            if job.get("runs-on") != "windows-latest":
                errors.append("job %s 必须使用 windows-latest" % name)

    for uses in _walk_uses(data.get("jobs")):
        if not isinstance(uses, str) or not FULL_SHA_RE.match(uses):
            errors.append("Action 必须固定完整 SHA：%r" % (uses,))

    for name, job in (jobs or {}).items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses", "")
            if isinstance(uses, str) and uses.startswith("actions/checkout@"):
                with_block = step.get("with") or {}
                if with_block.get("persist-credentials") != "false":
                    errors.append(
                        "checkout 必须设置 persist-credentials: false（job %s）" % name
                    )

    return errors


def check_codeowners(text):
    entries = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            entries.setdefault(parts[0], [])
            continue
        entries[parts[0]] = parts[1:]

    errors = []
    for pattern in REQUIRED_CODEOWNER_PATTERNS:
        owners = entries.get(pattern)
        if owners is None:
            errors.append("CODEOWNERS 缺少核心路径：%s" % pattern)
        elif OWNER not in owners:
            errors.append("CODEOWNERS 核心路径必须由 %s 审查：%s" % (OWNER, pattern))
    return errors


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    workflow = Path(argv[0]) if argv else ROOT / ".github" / "workflows" / "ci.yml"
    codeowners = (
        Path(argv[1]) if len(argv) > 1 else ROOT / ".github" / "CODEOWNERS"
    )
    errors = []
    for path, checker in ((workflow, check_workflow), (codeowners, check_codeowners)):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append("无法读取 %s：%s" % (path, exc))
            continue
        errors.extend("%s：%s" % (path.name, error) for error in checker(text))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("CI 策略检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
