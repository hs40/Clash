# ENG-05 验收报告：自动化测试与安全

- 日期：2026-11-10（初版）；2026-11-11（分支保护与 PR 验证更新）
- 分支：main（https://github.com/hs40/Clash）
- 环境：Windows，Python 3.12.3，PyYAML 6.0.3，git 2.55.0
- 需求基线：[REQUIREMENTS.md](REQUIREMENTS.md) v1.11
- 安全策略：[SECURITY.md](SECURITY.md)
- 结论：**本地 CI 配置、依赖哈希锁定、敏感信息扫描、Mihomo 固定版本校验、中文测试报告与
  CODEOWNERS 静态检查均已完成并通过；远端 main push CI、PR CI 与 main 分支保护策略 A 已实际
  运行/启用并通过验证。CODEOWNERS 的实际合并门禁未启用，是单人仓库下的已知限制，因此 ENG-05
  标记为“完成（策略 A），CODEOWNERS 强制为已知限制”。**

---

## 1. 总览

| 任务 | 状态 | 提交 |
| --- | --- | --- |
| ENG-05 自动化测试与安全 | 完成（策略 A）；CODEOWNERS 强制为已知限制 | 36e5361、aec4b9b、本次文档提交 |

全部自动化测试：**138 项通过，0 失败，0 错误**。

远端验证：

- main push CI：run 42785717956（36e5361）success；文档提交 run 42786357297（aec4b9b）success。
- PR CI：PR #1（head `2982220803297bf088b920457d562ad1a60bde94`）触发 `test` success，
  run 42956763427 / job 130313590289；PR 以 closed/unmerged 关闭，临时分支已删除。

---

## 2. ENG-05 任务报告

1. **任务编号：** ENG-05
2. **完成情况：** 已建立 Windows GitHub Actions CI、依赖版本与哈希锁定、敏感信息扫描、
   Mihomo 固定版本与二进制校验、中文 Markdown 测试报告、CI/CODEOWNERS 静态策略检查与
   安全策略文档。远端 main push CI、PR CI 和 main 分支保护策略 A 均已验证；CODEOWNERS
   的实际强制未启用，原因与替代方案见 §3.8、§5、§6。
3. **修改文件：**
   - 新增 .github/workflows/ci.yml；修改该文件与 tests/test_ci_policy.py，把 checkout 升级到
     v7.0.1、setup-python 升级到 v7.1.0（node24），并同步测试 fixture 的固定 SHA；
   - 新增 .github/CODEOWNERS；
   - 新增 security/mihomo.yaml；
   - 新增 scripts/check_dependencies.py、scripts/security_scan.py、scripts/check_mihomo.py、
     scripts/ci_report.py、scripts/ci_policy.py；
   - 修改 requirements.txt：PyYAML==6.0.3 加入 Windows/Linux SHA-256，注释改为 ASCII；
   - 修改 scripts/build.py：规则类型为 RULE-SET 时，在 Provider 尚未实现前拒绝构建；
   - 新增 tests/test_dependencies.py、tests/test_security.py、tests/test_mihomo.py、
     tests/test_ci_report.py、tests/test_ci_policy.py；
   - 修改 tests/test_rules.py：增加 RULE-SET 无 Provider 支持的失败用例；
   - 修改 .gitignore：忽略生成的 ci-report.md；
   - 修改 docs/REQUIREMENTS.md：v1.9 → v1.11，新增 §9.2，更新 §4、§12、§14、§15；
   - 新增 docs/SECURITY.md 与本报告；
   - 修改 README.md：CI/安全检查入口、报告链接与当前状态。
4. **实现内容：**
   - CI 在 windows-latest 上使用 Python 3.12.3，由 pull_request 与 push main 触发；
   - 顶层权限 contents: read，不引用 Secrets，不使用 pull_request_target；
   - actions/checkout v7.0.1 与 actions/setup-python v7.1.0 固定完整 Commit SHA
     （两者均为 node24），checkout 关闭 persist-credentials；
   - 依赖安装使用 pip install --require-hashes，随后 pip check；
   - 构建两份产物后执行敏感信息扫描与 CI 策略检查；
   - 运行全部测试并生成中文 Markdown 报告，写入 ci-report.md 与 GITHUB_STEP_SUMMARY；
   - 下载并校验 Mihomo v1.19.33 压缩包与可执行文件，执行两份产物的 -t；
   - 下载 country.mmdb 并校验固定 SHA-256，再用于 -t；
   - CODEOWNERS 覆盖 .github/、scripts/、configs/common/、security/ 与 REQUIREMENTS.md；
   - main 分支保护策略 A：PR 合并、必需检查 `test`、分支最新、0 审批、管理员受限、
     禁止强推/删除。
5. **测试命令：**
   - .venv\Scripts\python.exe -m unittest discover -s tests -v
   - .venv\Scripts\python.exe -m pip install --require-hashes --no-index -r requirements.txt
   - .venv\Scripts\python.exe -m pip check
   - .venv\Scripts\python.exe scripts\check_dependencies.py
   - .venv\Scripts\python.exe scripts\build.py --platform all
   - .venv\Scripts\python.exe scripts\security_scan.py
   - .venv\Scripts\python.exe scripts\ci_policy.py
   - .venv\Scripts\python.exe scripts\ci_report.py --output ci-report.md
   - .venv\Scripts\python.exe scripts\check_mihomo.py --archive .tmp_mihomo/mihomo.zip --binary .tmp_mihomo/mihomo-windows-amd64.exe
   - mihomo -t 对 dist/windows/config.yaml 与 dist/openclash/config.yaml
6. **测试结果：** 138 项测试通过；依赖锁定校验通过；pip check 无损坏依赖；
   敏感信息扫描无发现；CI 策略检查通过；中文报告 138 项、0 失败/错误；
   Mihomo 压缩包与二进制 SHA-256 校验通过；本机两份配置 -t 均退出码 0；
   远端 main push run 42785717956 与文档提交 run 42786357297 均成功；
   PR #1 的 `test` 检查 success，PR 状态 closed/unmerged。
7. **需求偏差：** 见第 5 节。
8. **遗留问题：** 见第 6 节。
9. **下一步建议：** 进入 ENG-06（Provider、缓存、发布与回滚）；ENG-04 的 NAS/HAOS/Proxmox
   路径仍需环境就绪后回补。CODEOWNERS 强制若必须启用，需增加第二审查人或由负责人明确
   bypass 方案。

---

## 3. 验收项核对

### 3.1 PR 自动测试

.github/workflows/ci.yml 已配置 pull_request 触发，并包含构建、扫描、测试、Mihomo -t 步骤。
scripts/ci_policy.py 对实际工作流文本检查通过。

实际验证：临时分支 `test/branch-protection-probe-20261111` 提交 `2982220` 创建 PR #1，
GitHub Actions 自动运行 `test`，结论 success（run 42956763427 / job 130313590289）。
PR 页面：https://github.com/hs40/Clash/pull/1

验证后 PR 以 closed/unmerged 关闭，远端与本地临时分支均已删除；main 未接收探针文件。

### 3.2 失败不能合并

main 分支保护已启用：

- Require a pull request before merging：true；Required approvals：0；
- Require status checks to pass：`test`；Require branches to be up to date：true；
- Enforce admins：true；
- Allow force pushes：false；Allow deletions：false。

工作流中任一命令非零退出都会使 job 失败；ci_report.py 在失败/错误非零时返回 1；
Mihomo -t 后显式检查 LASTEXITCODE。由于 `test` 是必需检查，检查失败时 GitHub 不允许合并。

本轮没有故意制造失败检查来观察 `mergeable_state=blocked`；上述结论来自分支保护配置与
GitHub 的必需检查语义，属于配置级验证，不是失败 PR 的运行时复现（见 §6）。

### 3.3 高风险不能发布

SECURITY.md 已记录阻断规则：高风险失败默认阻断发布，只有 @hs40 可解除。
ENG-05 不实现发布工作流，因此这是策略与审查约束，不是自动发布门禁；正式发布门禁属 ENG-06。
**策略已记录，技术门禁待 ENG-06。**

### 3.4 CI 生成中文 Markdown 测试报告

运行：

    .venv\Scripts\python.exe scripts\ci_report.py --output ci-report.md

输出：

    测试报告：ci-report.md（138 项，失败/错误 0 项）

报告标题为“# Clash 配置工程测试报告”，包含汇总、逐项明细与失败详情（无失败时省略）。
退出码 0；ci-report.md 已加入 .gitignore，不作为源文件提交。

### 3.5 依赖版本与哈希锁定

requirements.txt 当前只有 PyYAML==6.0.3，带两个哈希：

- 5fcd34e47f6e0b794d17de1b4ff496c00986e1c83f7ab2fb8fcfe9616ff7477b（win_amd64）
- ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc（manylinux x86_64）

本地命令与结果：

    pip install --require-hashes --no-index -r requirements.txt
    Requirement already satisfied: PyYAML==6.0.3
    EXIT=0

    pip check
    No broken requirements found.

    python scripts/check_dependencies.py
    PyYAML==6.0.3

本地使用 --no-index，只验证锁定文件语法、哈希与已安装包一致性；CI 的联网下载已在
远端 run 42785717956 执行并通过。首次本地联网尝试暴露出 requirements.txt 的中文注释会被
Windows pip 按本地代码页解码而失败，已把注释改为 ASCII，避免该环境问题。

### 3.6 敏感信息扫描

运行 scripts/security_scan.py，输出“敏感信息扫描通过”，退出码 0。
tests/test_security.py 覆盖占位值忽略、私钥、GitHub Token、AWS Access Key、通用密钥赋值、
订阅链接凭据；scan_repository(ROOT) 返回空列表。

已知限制：只扫描工作区文本文件，不扫描 git 历史，不做熵值检测。

### 3.7 Mihomo 固定版本与 -t

security/mihomo.yaml 固定：

- version: v1.19.33
- archive_sha256: 6ab2180875f9f6fff8b19386d760daec257f66b45f72b3afc650634272fa837a
- executable: mihomo-windows-amd64.exe
- executable_sha256: 1cde41cfffd3de0aedad63c0a8515e1ce5eea507e8133aed0f637d316c93800a

本地已下载官方 Windows 资产，大小 22,512,121 字节；可执行文件 61,247,488 字节。
check_mihomo.py 输出“Mihomo 校验通过：v1.19.33”。用该二进制对两份产物执行 -t：
Windows 退出码 0（约 104 ms），OpenClash 退出码 0（约 2 ms）。GeoIP 使用本地下载的
country.mmdb，SHA-256 为 c0c6ea5661a3167abb24bbbaf629605aa3856c425384cbf2897c5a0f41027663，
7,621,999 字节。

CI 中 country.mmdb 来自上游 latest 标签；内容哈希固定，上游变化会使 CI 失败，需负责人审查。

### 3.8 CODEOWNERS 与 CI 策略

.github/CODEOWNERS 覆盖 *、/.github/、/scripts/、/configs/common/、/security/、
/docs/REQUIREMENTS.md，所有者均为 @hs40。scripts/ci_policy.py 对实际工作流与 CODEOWNERS
检查通过，输出“CI 策略检查通过”。

**限制：** main 分支保护策略 A 未启用 Require review from Code Owners。GitHub 不允许 PR
作者审批自己创建的 PR；在单人仓库启用 Code Owner 审查会使负责人无法合并自己的 PR。
因此 CODEOWNERS 当前是归属声明与静态检查，不是实际合并门禁。若必须强制，需要增加第二
审查人，或由负责人明确批准 bypass 方案。

### 3.9 构建与测试

完整测试：

    .venv\Scripts\python.exe -m unittest discover -s tests -v

结果：Ran 138 tests，OK。

构建：

    .venv\Scripts\python.exe scripts\build.py --platform all

退出码 0，生成 dist/windows/config.yaml 与 dist/openclash/config.yaml；两者均可被
Mihomo v1.19.33 -t 加载。产物 SHA-256 与本阶段代码变更前一致（配置源未变）。

### 3.10 远端 main push CI

- run 42781834757（提交 2ab8a48）：success；check “test” 带 1 条 Node.js 20 弃用 annotation。
- 已升级 actions/checkout 到 v7.0.1（3d3c42e5aac5ba805825da76410c181273ba90b1）、
  actions/setup-python 到 v7.1.0（6d4fd22b20465ccc0f7354476588e8df7c9ca0e0）；两者 action.yml
  的 runs.using 均为 node24，且保留 persist-credentials / python-version 输入。
- run 42785717956（提交 36e5361）：success；全部步骤成功；check “test” 的
  annotations_count 为 0。
- run 42786357297（提交 aec4b9b）：success；文档提交也通过 main push CI。

### 3.11 分支保护与 PR 验证

分支保护设置（通过 GitHub REST API 写入并回读）：

| 设置 | 值 |
| --- | --- |
| Require PR before merging | true |
| Required approvals | 0 |
| Require Code Owner reviews | false |
| Required status checks | `test` |
| Require branches up to date | true |
| Enforce admins | true |
| Allow force pushes | false |
| Allow deletions | false |

PR #1 验证：

- 临时分支：`test/branch-protection-probe-20261111`
- head：`2982220803297bf088b920457d562ad1a60bde94`
- check：`test` success，run 42956763427 / job 130313590289
- PR 状态：closed；merged：false
- 临时分支：已删除

---

## 4. 产物与固定值核对

| 项目 | 值 |
| --- | --- |
| Windows 配置 SHA-256 | 5d5af88581be3282334f23b5c589b7ce68a2eb1b005448a9d4676632b6e6679e |
| OpenClash 配置 SHA-256 | 6d959695f66279a8e75d48854e01068a0aa89b5ffc804a42c5a8d675ddbca33e |
| Mihomo 版本 | v1.19.33（Windows 基准） |
| country.mmdb SHA-256 | c0c6ea5661a3167abb24bbbaf629605aa3856c425384cbf2897c5a0f41027663 |

---

## 5. 需求偏差与决策

| 项 | 处理 | 依据 |
| --- | --- | --- |
| 本地缓存/定期刷新推迟 | ENG-05 不实现，记录到 ENG-06 Provider | 负责人 2026-11-10 确认 |
| RULE-SET 在 Provider 前不可用 | build.py 对 RULE-SET 直接报错，避免悬空 Provider 引用 | 负责人批准的 ENG-05 范围 |
| 依赖文件中文注释导致 pip 解码失败 | 注释改为 ASCII | 本地验收发现，不改变依赖版本/哈希 |
| country.mmdb 使用 latest 标签 | 固定内容 SHA-256，上游变化阻断 CI | 上游只提供 latest 可变标签；需负责人更新 |
| 分支保护采用策略 A | PR + 必需检查 `test` + 0 审批 + 禁止强推/删除；管理员受限 | 负责人 2026-11-11 确认 |
| CODEOWNERS 未强制 | 单人仓库无法审批自己的 PR；保留静态检查，不启用 Code Owner 审查 | 负责人 2026-11-11 选择策略 A |
| 未做失败检查的 PR 运行时复现 | 记录为配置级验证限制，不声称已复现 | 避免为测试而故意破坏 main/PR |
| 不实现发布工作流 | 高风险发布门禁留到 ENG-06 | ENG-05 范围只含 CI/测试/安全 |
| 仅 Windows CI | 未在 CI 中运行 OpenClash 设备或 alpha 内核 | 设备不可由 GitHub Actions 访问；设备验证见 ENG-04 |

---

## 6. 遗留问题

1. CODEOWNERS 强制未启用；当前仅是归属声明与静态检查。启用需要第二审查人或负责人批准的
   bypass 方案。
2. 未通过“故意失败的 PR”复现 `mergeable_state=blocked`；分支保护对 `test` 的必需检查
   是配置级保证。
3. country.mmdb 上游 latest 可变；更新哈希需负责人审查。
4. CI 不能替代真实网络连通性、DNS 泄漏、TUN 接管、OpenClash 透明代理/防火墙验证。
5. ENG-04 的 NAS 显式代理端到端、HAOS 与 Proxmox 路径仍受环境阻塞。
6. ENG-06 尚未开始：Provider、缓存/刷新、发布与回滚。

---

## 7. 临时管理凭据处理

本次分支保护设置使用负责人提供的临时 fine-grained PAT，仅通过本地临时脚本读取，未写入
仓库、测试输出或日志。设置与验证完成后删除本地临时 token 文件，并请负责人立即撤销该 PAT。
仓库中不保存任何真实 token。
