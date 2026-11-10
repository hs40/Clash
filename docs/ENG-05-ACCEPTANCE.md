# ENG-05 验收报告：自动化测试与安全

- 日期：2026-11-10
- 分支：main（本地仓库，未推送远端）
- 环境：Windows，Python 3.12.3，PyYAML 6.0.3，git 2.55.0
- 需求基线：[REQUIREMENTS.md](REQUIREMENTS.md) v1.9
- 安全策略：[SECURITY.md](SECURITY.md)
- 结论：**本地 CI 配置、依赖哈希锁定、敏感信息扫描、Mihomo 固定版本校验、中文测试报告与
  CODEOWNERS 静态检查均已完成并通过；远端 GitHub CI 尚未实际运行，分支保护与 CODEOWNERS
  强制尚未配置/核验，因此 ENG-05 标记为“本地完成、远端部分通过”。**

---

## 1. 总览

| 任务 | 状态 | 提交 |
| --- | --- | --- |
| ENG-05 自动化测试与安全 | 本地完成；远端部分通过 | 本报告所在提交 |

全部自动化测试：**138 项通过，0 失败，0 错误**。

---

## 2. ENG-05 任务报告

1. **任务编号：** ENG-05
2. **完成情况：** 已建立 Windows GitHub Actions CI、依赖版本与哈希锁定、敏感信息扫描、
   Mihomo 固定版本与二进制校验、中文 Markdown 测试报告、CI/CODEOWNERS 静态策略检查与
   安全策略文档。远端 CI 运行、分支保护与 CODEOWNERS 强制未完成。
3. **修改文件：**
   - 新增 .github/workflows/ci.yml；
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
   - 修改 docs/REQUIREMENTS.md：v1.9，新增 §9.1，更新 §4、§12、§14、§15；
   - 新增 docs/SECURITY.md 与本报告；
   - 修改 README.md：CI/安全检查入口、报告链接与当前状态。
4. **实现内容：**
   - CI 在 windows-latest 上使用 Python 3.12.3，由 pull_request 与 push main 触发；
   - 顶层权限 contents: read，不引用 Secrets，不使用 pull_request_target；
   - actions/checkout v4.2.2 与 actions/setup-python v5.6.0 固定完整 Commit SHA，
     checkout 关闭 persist-credentials；
   - 依赖安装使用 pip install --require-hashes，随后 pip check；
   - 构建两份产物后执行敏感信息扫描与 CI 策略检查；
   - 运行全部测试并生成中文 Markdown 报告，写入 ci-report.md 与 GITHUB_STEP_SUMMARY；
   - 下载并校验 Mihomo v1.19.33 压缩包与可执行文件，执行两份产物的 -t；
   - 下载 country.mmdb 并校验固定 SHA-256，再用于 -t；
   - CODEOWNERS 保护 .github/、scripts/、configs/common/、security/ 与 REQUIREMENTS.md。
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
   Mihomo 压缩包与二进制 SHA-256 校验通过；本机两份配置 -t 均退出码 0。
7. **需求偏差：** 见第 5 节。
8. **遗留问题：** 见第 6 节。
9. **下一步建议：** 负责人启用远端分支保护与必需状态检查，推送后完成首个真实 PR CI；
   随后进入 ENG-06（Provider、缓存、发布与回滚）。ENG-04 的 NAS/HAOS/Proxmox 路径仍需
   环境就绪后回补。

---

## 3. 验收项核对

### 3.1 PR 自动测试

.github/workflows/ci.yml 已配置 pull_request 触发，并包含构建、扫描、测试、Mihomo -t 步骤。
scripts/ci_policy.py 对实际工作流文本检查通过。

本地无法创建 GitHub PR，因此“PR 自动触发”只完成配置与静态检查，**远端未验证**。

### 3.2 失败不能合并

工作流中任一命令非零退出都会使 job 失败；ci_report.py 在失败/错误非零时返回 1；
Mihomo -t 后显式检查 LASTEXITCODE。

但远端分支保护尚未启用，GitHub 目前不会仅因 CI 失败自动阻止合并。**待负责人在仓库设置中
启用分支保护与必需状态检查。**

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

本地使用 --no-index，只验证锁定文件语法、哈希与已安装包一致性；CI 的联网下载由 GitHub
Actions 执行，尚未在远端运行。首次本地联网尝试暴露出 requirements.txt 的中文注释会被
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

远端的 CODEOWNERS 强制与分支保护尚未启用/核验。

### 3.9 构建与测试

完整测试：

    .venv\Scripts\python.exe -m unittest discover -s tests -v

结果：Ran 138 tests，OK。

构建：

    .venv\Scripts\python.exe scripts\build.py --platform all

退出码 0，生成 dist/windows/config.yaml 与 dist/openclash/config.yaml；两者均可被
Mihomo v1.19.33 -t 加载。产物 SHA-256 与本阶段代码变更前一致（配置源未变）。

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
| 远端分支保护未启用 | 报告为未完成，不写成已通过 | 本地无法配置 GitHub 仓库设置 |
| 不实现发布工作流 | 高风险发布门禁留到 ENG-06 | ENG-05 范围只含 CI/测试/安全 |
| 仅 Windows CI | 未在 CI 中运行 OpenClash 设备或 alpha 内核 | 设备不可由 GitHub Actions 访问；设备验证见 ENG-04 |

---

## 6. 遗留问题

1. 尚未推送远端，未触发真实 GitHub Actions；需负责人推送并检查首个 PR/CI 运行。
2. 远端分支保护、必需状态检查与 CODEOWNERS 强制未启用/核验。
3. country.mmdb 上游 latest 可变；更新哈希需负责人审查。
4. CI 不能替代真实网络连通性、DNS 泄漏、TUN 接管、OpenClash 透明代理/防火墙验证。
5. ENG-04 的 NAS 显式代理端到端、HAOS 与 Proxmox 路径仍受环境阻塞。
6. ENG-06 尚未开始：Provider、缓存/刷新、发布与回滚。
