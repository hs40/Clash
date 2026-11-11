# 安全策略（ENG-05）

- 依据：[REQUIREMENTS.md](REQUIREMENTS.md) §9 与 §9.1。
- 状态：本地 CI 配置、依赖锁定、敏感信息扫描、Mihomo 固定校验与 CODEOWNERS 文件已完成；
  远端 main push CI、PR CI 与 main 分支保护策略 A 已实际运行/启用并通过验证。
  CODEOWNERS 的实际合并门禁未启用，是单人仓库下的已知限制。
- 适用范围：本仓库的构建脚本、公共配置、安全清单、GitHub Actions 与发布流程。

## 1. 阻断规则

1. CI 失败的 PR 不得合并；正式发布必须基于通过 CI 的 main。
2. 高风险问题包括：未授权的新 Provider 来源、凭据或订阅泄露、规则/分流基线异常、
   DNS 泄漏、未固定版本的依赖或二进制、CODEOWNERS 覆盖缺失。
3. 高风险失败默认阻断发布。只有项目负责人 **@hs40** 可以解除；解除时必须记录原因、
   影响范围和复核时间，不得静默跳过。
4. 开发 Agent 不修改真实设备，不提交真实凭据，不以“测试通过”代替真实网络验证。

## 2. GitHub Actions

- 工作流只响应 pull_request 与 push 到 main，不使用 pull_request_target。
- 顶层权限固定为 contents: read，不引用 Secrets；不可信 PR 不获得额外权限。
- 第三方 Action 固定完整 40 位 Commit SHA，不使用浮动 tag；当前 checkout v7.0.1 与
  setup-python v7.1.0 均运行于 node24（2026-11-10 升级，消除 Node 20 弃用告警）。
- actions/checkout 设置 persist-credentials: false，避免把令牌留在工作区。
- 工作流文本由 scripts/ci_policy.py 静态检查；检查失败时 CI 失败。

## 3. Python 依赖

- requirements.txt 每个依赖使用精确版本，并至少提供一个 SHA-256。
- CI 使用 pip install --require-hashes -r requirements.txt，随后执行 pip check。
- scripts/check_dependencies.py 拒绝未固定版本、缺少哈希、哈希格式错误和重复依赖。
- 依赖文件保持 ASCII 注释，避免 Windows 上 pip 以本地代码页解码 UTF-8 文件失败。

## 4. Mihomo 二进制与 GeoIP

- 固定版本清单位于 security/mihomo.yaml，记录官方 URL、压缩包 SHA-256、
  可执行文件名与可执行文件 SHA-256。
- CI 下载官方 release，先校验压缩包，再校验解压后的二进制，然后对两份产物执行 -t。
- Windows 设计基准为 Mihomo v1.19.33；OpenClash 设备基准为 alpha-gbc76c13（仅设备验证）。
- CI 使用的 country.mmdb 来自上游 latest 标签，但内容 SHA-256 固定。上游变更会使
  CI 失败，必须由负责人审查后更新哈希；不得把可变标签当作稳定版本。
- -t 只证明配置可加载，不证明 TUN、透明代理、DNS 泄漏或真实连通性。

## 5. 敏感信息扫描

- scripts/security_scan.py 扫描工作区文本文件，识别私钥、GitHub Token、AWS Access Key、
  疑似密钥赋值、订阅链接凭据与 Bearer Token。
- 输出只包含路径、行号和类型，不回显命中内容。
- 占位标记（如 PLACEHOLDER、NOT-REAL）不会被当作真实凭据；这不是对真实凭据的豁免。
- 已知限制：扫描基于正则，覆盖工作区当前文件，不扫描 git 历史，也不做熵值检测。
  因此它是阻断门槛，不是完整的凭据泄露取证工具。

## 6. CODEOWNERS

- .github/CODEOWNERS 将以下路径分配给 **@hs40**：
  *、/.github/、/scripts/、/configs/common/、/security/、/docs/REQUIREMENTS.md。
- scripts/ci_policy.py 静态检查这些路径和所有者是否齐全；它不能替代 GitHub 的
  CODEOWNERS 实际强制。
- 当前 main 分支保护采用策略 A：PR 合并、必需检查 `test`、分支最新、0 审批、
  管理员受限、禁止强推/删除。**未启用 Require review from Code Owners**；
  GitHub 不允许 PR 作者审批自己的 PR，单人仓库启用后会锁死合并。
- 因此 CODEOWNERS 目前是归属声明与静态检查，不是合并门禁。若必须强制，需要增加第二
  审查人，或由负责人明确批准 bypass 方案；该决定需单独审查。

## 7. 尚未完成与限制

1. 远端 main push CI 与 PR CI 均已通过；PR #1 的 `test` 检查 success，PR 已关闭未合并。
2. main 分支保护策略 A 已启用：PR + 必需检查 `test` + 0 审批 + 禁止强推/删除，管理员受限。
3. CODEOWNERS 强制未启用；当前只做静态检查，原因见第 6 节。
4. 分支保护是配置级验证；本轮未故意制造失败检查来观察 `mergeable_state=blocked`。
5. CI 不替代真实网络连通性、DNS 泄漏、TUN 接管与 OpenClash 透明代理验证（见
   [REQUIREMENTS.md](REQUIREMENTS.md) §14）。
6. ci-report.md 是本地/CI 生成物，不提交；报告内容不包含凭据。
