# ENG-06 验收报告：Provider、发布与回滚

- 日期：2026-11-11
- 分支：`feat/eng-06-provider-release`（基于 main `cc2c938`）；PR #3，代码提交 `d05611e`，文档提交 `566a3d5`
- 环境：Windows，Python 3.12.3，PyYAML 6.0.3，git 2.55.0，Mihomo v1.19.33（Windows）
- 需求基线：[REQUIREMENTS.md](REQUIREMENTS.md) v1.12
- 回滚手册：[ROLLBACK.md](ROLLBACK.md)
- 安全策略：[SECURITY.md](SECURITY.md)
- 结论：**本地 Provider 锁定/内嵌、每周检查脚本、发布包、配置差异报告、回滚文档与
  tag 触发 Release 工作流已完成并通过测试；本机双平台配置通过 Mihomo `-t`。
  Provider 检查与 Release 工作流尚未在 GitHub 远端实际触发，iStoreOS 设备尚未用
  内嵌 Provider 的新产物重测，因此 ENG-06 标记为“本地完成、远端与设备待验证”。**

---

## 1. 总览

| 任务 | 状态 | 提交 |
| --- | --- | --- |
| ENG-06 Provider、发布与回滚 | 本地完成；PR CI 通过，Provider/Release 工作流与设备重测待验证 | `d05611e` + `566a3d5` |

本地自动化测试：**184 项通过，0 失败，0 错误**（107.221 秒）。

关键证据：

- 双平台构建退出码 0，配置分别 2,282,529 / 2,282,408 字节；
- 发布包构建与 `release.py --verify` 均退出码 0；
- 本机 Mihomo v1.19.33 对两份产物执行 `-t` 均退出码 0；
- 敏感信息扫描、CI 策略检查、依赖锁定检查均退出码 0；
- 上游 Provider 检查：两个集合均“已是最新”。

---

## 2. ENG-06 任务报告

1. **任务编号：** ENG-06
2. **完成情况：** 已建立 Provider 白名单、固定 commit + SHA-256 + 字节数锁定、
   本地快照、构建期内嵌与 `RULE-SET` 引用校验；新增每周上游检查工作流与本地
   `--check` / `--apply` 脚本；新增双平台独立发布包、中文 Release Notes、
   `SHA256SUMS`、`CONFIG-DIFF.md` 与 `release.py --verify`；新增 tag 触发 Release
   工作流与 `docs/ROLLBACK.md`。远端工作流与设备端重测未完成，见第 5 节。
3. **修改文件：**
   - 新增 `VERSION`（0.1.0）、`THIRD_PARTY_NOTICES.md`；
   - 新增 `providers/lock.yaml`、`providers/snapshots/geosite-private.list`、
     `providers/snapshots/geosite-cn.list`、`providers/LICENSE-metacubex.txt`；
   - 新增 `scripts/providers.py`（锁文件、快照校验、payload 解析、inline 渲染）；
   - 新增 `scripts/update_providers.py`（上游检查、JSON 报告、`--apply` 原子更新）；
   - 新增 `scripts/release.py`（发布包、差异报告、校验、CLI）；
   - 修改 `scripts/build.py`：加入 `rule-providers` 公共键、Provider 注入与
     `RULE-SET` 引用校验；
   - 修改 `configs/common/rules.yaml`：基础层加入
     `RULE-SET,geosite-private,DIRECT`（90）与 `RULE-SET,geosite-cn,DIRECT`（110）；
   - 新增 `.github/workflows/provider-check.yml`、`.github/workflows/release.yml`；
   - 修改 `scripts/ci_policy.py`：检查 Provider 与 Release 工作流的权限、触发、
     Action SHA、checkout 持久化凭据与关键命令；
   - 新增 `tests/test_providers.py`、`tests/test_update_providers.py`、
     `tests/test_release.py`；
   - 修改 `tests/test_build.py`、`tests/test_dns.py`、`tests/test_groups.py`、
     `tests/test_rules.py`、`tests/test_ci_policy.py`，覆盖 Provider 注入与工作流策略；
   - 修改 `docs/REQUIREMENTS.md`（v1.12）、`docs/SECURITY.md`、`README.md`；
   - 新增 `docs/ROLLBACK.md` 与本报告。
4. **实现内容：**
   - **来源白名单**：仅 `MetaCubeX/meta-rules-dat`，ref `meta`，GPL-3.0；
     lock 记录 `owner/repository/license/approval/ref`，未知来源或身份不符直接失败。
   - **两个 domain 集合**：`geo/geosite/private.list`、`geo/geosite/cn.list`；
     业务规则保持内联，Provider 不能覆盖。
   - **固定版本**：commit `458e716abd80ff8c6aee2b7d15c4f94b20e9d279`；
     private 2,741 字节 / SHA-256 `db9b2da8...b7b57`；
     cn 1,613,591 字节 / SHA-256 `703c706f...9332f`。
   - **构建期内嵌**：`rule-providers.<name>.type: inline`，payload 为快照内容；
     构建只读仓库快照，不访问网络；缺失、字节数或 SHA-256 不符即失败。
   - **规则校验**：`RULE-SET` 必须恰好三段，Provider 必须存在；未知 Provider、
     多余字段、悬空目标均失败。
   - **每周检查**：周一 03:00 UTC + 手动触发；`contents: read`、job 级
     `issues: write`；有变化时创建 issue，不自动改 `main`。
   - **本地更新**：`--apply --commit <40位sha>` 校验 payload 后原子写快照与锁文件；
     不执行 git/PR，只打印建分支、提交、推送、`gh pr create` 命令。
   - **发布**：`release.py --version X.Y.Z` 要求与 `VERSION` 完全一致；每个平台
     生成 `config.yaml` 与 zip；zip 含配置、第三方声明、GPL 许可证与
     `CONFIG-DIFF.md`；发布目录含中文 Notes、差异报告、`SHA256SUMS`。
   - **发布校验**：哈希覆盖/重复/多余文件、必需文件、配置可解析、`MATCH` 最后、
     Provider 存在、zip 成员与配置/差异报告一致。
   - **Release 工作流**：仅 `v*` tag；`contents: write`；固定 Action SHA、
     `persist-credentials: false`；测试 → 构建 → 校验 → `gh release create`。
   - **回滚**：平台独立、先备份、SHA 校验、至少保留五个版本、当前生产版本不删除，
     全部手动执行。
5. **测试命令：**
   - `.venv\Scripts\python.exe -m unittest discover -s tests -v`
   - `.venv\Scripts\python.exe scripts\build.py --platform all`
   - `.venv\Scripts\python.exe scripts\release.py --version 0.1.0`
   - `.venv\Scripts\python.exe scripts\release.py --verify dist\release\0.1.0`
   - `.venv\Scripts\python.exe scripts\security_scan.py`
   - `.venv\Scripts\python.exe scripts\ci_policy.py`
   - `.venv\Scripts\python.exe scripts\check_dependencies.py`
   - `.venv\Scripts\python.exe scripts\update_providers.py --check --json .tmp_provider_check.json`
   - `"C:\Program Files\Clash Verge\verge-mihomo.exe" -t -f dist\windows\config.yaml -d .tmp_mihomo_test`
   - `"C:\Program Files\Clash Verge\verge-mihomo.exe" -t -f dist\openclash\config.yaml -d .tmp_mihomo_test`
6. **测试结果：** 184 项测试通过；构建退出码 0；发布构建/校验退出码 0；敏感信息扫描、
   CI 策略、依赖锁定均退出码 0；Provider 检查两个集合均“已是最新”；Mihomo `-t`
   两份配置均退出码 0（Windows 359 ms，OpenClash 280 ms）。详见第 3 节。
7. **需求偏差：** 见第 4 节。
8. **遗留问题：** 见第 5 节。
9. **下一步建议：** 合并本分支后，由负责人在 GitHub 手动触发一次
   `Provider Check`；确认首个 `v0.1.0` tag 的 Release 流程；在 iStoreOS 上只读执行
   `-t` 验证新产物。完成后再决定是否进入后续阶段。

---

## 3. 验收项核对

### 3.1 Provider 来源白名单与锁定

`providers/lock.yaml`：

- `version: 1`；
- 来源 `metacubex`：owner `MetaCubeX`、repository `meta-rules-dat`、
  license `GPL-3.0`、ref `meta`、approval 记录负责人 2026-11-11 批准；
- `geosite-private`：commit `458e716abd80ff8c6aee2b7d15c4f94b20e9d279`，
  2,741 字节，SHA-256 `db9b2da8d7e90f09e183dcde096f72adaacd8de21e0f09d364b413085ecb7b57`；
- `geosite-cn`：同一 commit，1,613,591 字节，SHA-256
  `703c706f925afa756a404136ce2cbea856763969d241280ce55345519dc9332f`。

构建、测试与发布前都会重新校验字节数与 SHA-256；测试覆盖缺失文件、长度不符、
同长度篡改、非法 behavior、路径穿越、未知来源与多余字段。**通过。**

### 3.2 配置只使用已验证 Provider

`build_platform` 在合并公共/平台配置后读取锁文件，渲染 `rule-providers`；公共
YAML 若直接定义 `rule-providers` 会失败，平台配置也不允许该键。规则中的
`RULE-SET` 必须引用锁文件中的 Provider。

实际产物顶层键包含 `rule-providers`；两份产物均含 `geosite-cn`、`geosite-private`，
类型 `inline`。**通过。**

### 3.3 更新失败不破坏当前生产配置

- 锁文件缺失、快照缺失、大小不符、SHA-256 不符、payload 含空白或冒号域名字段，
  均使构建失败，不会回退到“最新版”。
- `--apply` 先解析并校验全部变化，再写临时文件并原子替换；任何一项失败都不会
  触碰现有快照或锁文件（测试覆盖）。
- 前端构建只读仓库快照，不访问网络，因此上游不可用不影响构建。**通过。**

### 3.4 每周检查与人工审批

`.github/workflows/provider-check.yml`：

- `schedule: 0 3 * * 1` + `workflow_dispatch`；
- `contents: read`、`issues: write`；
- 运行 `update_providers.py --check --json`，只在 `changed` 为 true 时创建 issue；
- 不自动修改 `main`，不自动应用快照。

本地实际检查：`changed: false`，两个集合均“已是最新”。**本地通过；远端未触发。**

### 3.5 发布包完整且无敏感信息

`dist/release/0.1.0/`：

| 文件 | 大小 |
| --- | ---: |
| `windows/config.yaml` | 2,282,529 |
| `openclash/config.yaml` | 2,282,408 |
| `windows-0.1.0.zip` | 511,738 |
| `openclash-0.1.0.zip` | 511,688 |
| `SHA256SUMS` | 685 |
| `RELEASE-NOTES.md` | 1,112 |
| `CONFIG-DIFF.md` | 699 |
| `THIRD_PARTY_NOTICES.md` | 913 |
| `LICENSE-metacubex.txt` | 35,149 |

zip 成员为 `config.yaml`、`THIRD_PARTY_NOTICES.md`、`LICENSE-metacubex.txt`、
`CONFIG-DIFF.md`；`release.py --verify` 通过。`security_scan.py` 未发现未豁免敏感信息；
发布包不含订阅、Token、密码或本机路径。**通过。**

### 3.6 配置差异报告

`CONFIG-DIFF.md` 为中文，逐平台记录 SHA-256、顶层键、策略组数、规则数、Provider、
节点数，并在存在更早 SemVer 目录时比较策略组/规则/Provider/顶层键的增删。当前
`dist/release` 无更早版本，因此报告明确写“未找到上一版本”，不伪造历史差异。
测试覆盖“无变化”和“新增/删除规则”两种渲染结果。**通过。**

### 3.7 双平台独立回滚

`docs/ROLLBACK.md` 规定：

- Windows 与 OpenClash 分开备份、校验、回滚，不跨平台覆盖；
- 部署前核对 `SHA256SUMS`，回滚前备份当前配置；
- 至少保留最近五个已验证版本，当前生产版本不删除；
- 回滚由负责人手动执行，不自动修改设备。

本次没有在真实设备上执行回滚；验收范围是文档与包结构。**文档通过；运行时未演练。**

### 3.8 Release 工作流

`release.yml` 仅由 `v*` tag 触发；`permissions: contents: write`；固定 Action SHA；
`persist-credentials: false`；运行测试、构建、`--verify`，再用 `gh release create`
上传两个 zip、`SHA256SUMS` 和中文 Notes。`ci_policy.py` 对工作流文本检查通过。

**未在远端实际触发。** 推送 tag 会创建真实 GitHub Release，本轮没有执行；首个
正式 tag 发布需负责人审查。

### 3.9 本机 Mihomo 加载

```text
Mihomo Meta v1.19.33 windows amd64 with go1.26.10
configuration file ...\dist\windows\config.yaml test is successful
configuration file ...\dist\openclash\config.yaml test is successful
```

Windows `WIN_EXIT=0`，OpenClash `OC_EXIT=0`。这只证明配置可加载，不证明 TUN、
透明代理、DNS 泄漏或真实连通性。**通过（仅加载）。**

### 3.10 自动化测试

```text
Ran 184 tests in 107.221s
OK
```

新增覆盖：Provider 锁/快照/payload/inline、`--check` 与 `--apply` 失败路径、
发布包/zip/SHA256SUMS/差异报告/重构建一致性、Provider 与 Release 工作流策略。**通过。**

### 3.11 PR CI

PR #3（https://github.com/hs40/Clash/pull/3）的必需检查 `test` 已通过：
run 42962911064 / job 130333415834，head `566a3d5`。该运行包含依赖哈希安装、
双平台构建、敏感扫描、CI 策略检查、184 项测试与 Mihomo `-t`。

Provider Check 与 Release 工作流没有被 PR 触发（前者只看 schedule/dispatch，后者只看
`v*` tag），因此仍需单独验证。**PR CI 通过；两个新工作流未运行。**

---

## 4. 需求偏差与负责人决策

| 项 | 处理 | 依据 |
| --- | --- | --- |
| Release 改为 tag 触发，不是 main 合并自动发布 | `release.yml` 只响应 `v*` tag；负责人合并后显式推 tag | 负责人 2026-11-11 选择方案 A；偏离 Plan §10.1，已记录 |
| GPL-3.0 数据内嵌再分发 | 发布包附 `THIRD_PARTY_NOTICES.md` 与完整 `LICENSE-metacubex.txt` | 负责人 2026-11-11 批准方案 A |
| Provider 更新不自动建 PR | 每周检查只开 issue；`--apply` 本地写文件并打印建分支/PR 命令 | 负责人选择“Release 自动；Provider 检查开 issue，更新用本地脚本建分支/PR” |
| 使用 MetaCubeX 而非其他规则源 | 仅 private/cn 两个 domain 集合 | 负责人 2026-11-11 选择“MetaCubeX：private + cn” |
| 配置体积增大约 2.28 MB | 接受 inline 自包含，换取无运行时下载 | 负责人 2026-11-11 选择“inline 内嵌” |
| 节点识别无持久化缓存 | 项目不拉取节点订阅，节点在仓库内；Provider 快照承担规则数据缓存 | REQUIREMENTS §4.2 第 6 条；如负责人要求节点级缓存需另立项 |
| 最近五个版本不自动清理 | GitHub Release 历史保留，负责人手动维护；不实现删除逻辑 | 保留多于五个不违反“至少保留五个”；自动清理属额外范围 |

---

## 5. 遗留问题与未验证项

1. **远端 Provider Check 未运行。** 工作流只通过本地静态策略检查；未验证
   `gh issue create` 在真实仓库中的权限与 issue 内容。
2. **Release 工作流未运行。** 没有推送 `v0.1.0` tag，未验证 `gh release create`、
   Release 页面、资产上传与 Notes 渲染。首个正式发布需负责人审查。
3. **iStoreOS 未重测。** 内嵌 Provider 后 OpenClash 配置为 2,282,408 字节；
   设备 alpha-gbc76c13 尚未加载该新产物。旧产物 4,006 字节的 `-t` 结果不能代表新产物。
4. **NAS/HAOS/Proxmox 仍环境阻塞。** 与 ENG-04 相同，未做端到端透明代理/DNS 验证。
5. **GPL 许可证文件来源。** 固定 commit `458e716...` 的 `meta` 分支根目录没有
   LICENSE；`providers/LICENSE-metacubex.txt` 取自仓库 master 根目录（35,149 字节，
   SHA-256 `3972dc97...b36986`）。`THIRD_PARTY_NOTICES.md` 记录了来源、commit 和
   修改说明；若上游许可证变化，需负责人复核。
6. **Provider 内容安全未审计。** 锁定 SHA-256 只证明内容未变，不证明规则无恶意或
   误伤；高风险更新仍需人工阅读差异。
7. **未做失败 PR 的运行时复现。** 分支保护与必需检查仍是配置级保证。
8. **未演练真实回滚。** 只有文档与包结构校验，没有在 Windows/OpenClash 上执行
   备份、恢复和回滚后验证。
9. **每周 issue 可能重复。** 当前每次变化都创建新 issue，没有按 Provider/commit 去重；
   这是可用性限制，不影响安全性。

---

## 6. 凭据与设备边界

- 未读取、写入或提交任何真实 Token、订阅、密码、SSH 私钥。
- 未修改 Clash Verge、OpenClash 或 iStoreOS 的真实配置；`-t` 使用本机临时目录
  `.tmp_mihomo_test`，不启动代理、不接管流量。
- 发布包中的节点仍为 TEST-NET-1 占位节点（`192.0.2.x`，`PLACEHOLDER-NOT-REAL`），
  不得用于真实部署。
- 测试与日志中的临时文件（`.tmp_*`）未提交。
