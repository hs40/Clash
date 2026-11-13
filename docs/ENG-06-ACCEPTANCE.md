# ENG-06 验收报告：Provider、发布与回滚

- 日期：2026-11-11
- 分支：`docs/eng-06-v0.1.1-release-record`（基于 main `4cb9148`）；代码分支 `fix/release-checksum-assets` 已由 PR #10 合并为 `4cb9148`；发布修正代码提交 `6d0555b`
- 后续 CI 修复：PR #5（squash merge `d4a7a4a`）；Provider Check UTF-8 修复，见 §3.12
- 发布记录：annotated tag `v0.1.0` 指向 `3c8773f`（Release run 42997351203）；`v0.1.1` 指向 `4cb9148`（Release run 43003842864）
- 环境：Windows，Python 3.12.3，PyYAML 6.0.3，git 2.55.0，Mihomo v1.19.33（Windows）
- 需求基线：[REQUIREMENTS.md](REQUIREMENTS.md) v1.16
- 发布修正：`v0.1.1`（负责人 2026-11-11 要求修正 `SHA256SUMS` 资产覆盖并生成新版本）；远端发布、资产校验与配置 `-t` 已完成
- 回滚手册：[ROLLBACK.md](ROLLBACK.md)
- 安全策略：[SECURITY.md](SECURITY.md)
- 结论：**本地 Provider 锁定/内嵌、每周检查脚本、发布包、配置差异报告与回滚文档已完成；
  Provider Check、`v0.1.0` 与 `v0.1.1` Release、issue 创建均已远端验证；Windows/OpenClash
  发布配置在本机 Mihomo 上 `-t` 通过。`v0.1.0` 的 `SHA256SUMS` 资产覆盖限制已在
  `v0.1.1` 修正为只覆盖两个 Release zip；远端资产下载、独立哈希校验、zip 结构与
  解出配置 `-t` 均通过，干净本地构建可复现远端 zip 哈希。Release 的 `CONFIG-DIFF.md`
  在干净检出中仍显示“未找到上一版本”，作为已知遗留记录。平台部署已将内嵌 Provider 的
  构建产物写入 iStoreOS 并通过 `mihomo -t`；Release zip 本身未单独在设备上重测，因此
  ENG-06 保留“本地完成、远端 Provider Check/Release 通过；Release 包设备重测待完成”。**

---

## 1. 总览

| 任务 | 状态 | 提交 |
| --- | --- | --- |
| ENG-06 Provider、发布与回滚 | 已合并 main；PR CI、main CI、Provider Check、v0.1.0/v0.1.1 Release 与 issue 创建远端通过；iStoreOS 设备重测待验证 | `d05611e` + `c3436d3` + `d4a7a4a` + `6d0555b` + `4cb9148` + 本记录 |

本地自动化测试：**188 项通过，0 失败，0 错误**（195.607 秒）。

关键证据：

- 双平台构建退出码 0，配置分别 2,282,529 / 2,282,408 字节；
- 发布包构建与 `release.py --verify` 均退出码 0；
- 本机 Mihomo v1.19.33 对两份产物执行 `-t` 均退出码 0；
- 敏感信息扫描、CI 策略检查、依赖锁定检查均退出码 0；
- 上游 Provider 检查：两个集合均“已是最新”；
- 远端 Provider Check run 42972389013 与 main CI run 42972337584 均成功；
- `v0.1.0` Release run 42997351203 成功，Release 资产下载后哈希与提取配置均校验通过；
- 临时分支触发 Provider Check run 42996296022，issue #6 由 `app/github-actions` 创建成功；
- `v0.1.1` 本地发布包只含两个 zip 的 `SHA256SUMS`，`release.py --verify` 通过；
- `v0.1.1` Release run 43003842864 成功；远端两个 zip 哈希、`SHA256SUMS` 两行覆盖与
  解出配置 `-t` 均验证通过；干净本地目录构建复现了远端 zip 哈希。

---

## 2. ENG-06 任务报告

1. **任务编号：** ENG-06
2. **完成情况：** 已建立 Provider 白名单、固定 commit + SHA-256 + 字节数锁定、
   本地快照、构建期内嵌与 `RULE-SET` 引用校验；新增每周上游检查工作流与本地
   `--check` / `--apply` 脚本；新增双平台独立发布包、中文 Release Notes、
   `SHA256SUMS`、`CONFIG-DIFF.md` 与 `release.py --verify`；新增 tag 触发 Release
   工作流与 `docs/ROLLBACK.md`。远端工作流与设备端重测未完成，见第 5 节。
3. **修改文件：**
   - 新增 `VERSION`（0.1.0，发布修正后为 0.1.1）、`THIRD_PARTY_NOTICES.md`；
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
   - 修改 `docs/REQUIREMENTS.md`（v1.12，后续 v1.13）、`docs/SECURITY.md`、`README.md`；
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
   - `.venv\Scripts\python.exe scripts\release.py --version 0.1.1`
   - `.venv\Scripts\python.exe scripts\release.py --verify dist\release\0.1.1`
   - `.venv\Scripts\python.exe scripts\security_scan.py`
   - `.venv\Scripts\python.exe scripts\ci_policy.py`
   - `.venv\Scripts\python.exe scripts\check_dependencies.py`
   - `.venv\Scripts\python.exe scripts\update_providers.py --check --json .tmp_provider_check.json`
   - `"C:\Program Files\Clash Verge\verge-mihomo.exe" -t -f dist\windows\config.yaml -d .tmp_mihomo_test`
   - `"C:\Program Files\Clash Verge\verge-mihomo.exe" -t -f dist\openclash\config.yaml -d .tmp_mihomo_test`
6. **测试结果：** 188 项测试通过；构建退出码 0；发布构建/校验退出码 0；敏感信息扫描、
   CI 策略、依赖锁定均退出码 0；Provider 检查两个集合均“已是最新”；Mihomo `-t`
   两份配置均退出码 0（v0.1.1 解出配置 Windows 873 ms，OpenClash 827 ms）。详见第 3 节。
7. **需求偏差：** 见第 4 节。
8. **遗留问题：** 见第 5 节。
9. **下一步建议：** 合并本记录；由负责人安排 iStoreOS 对 `v0.1.1` 新产物只读执行
   `-t`；后续版本再决定是否实现从上一 GitHub Release 读取 `CONFIG-DIFF` 基线。
   完成设备重测前不把 ENG-06 写成“全部通过”。

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

2026-11-11 推送 annotated tag `v0.1.0`（指向 main `3c8773f`）实际触发
run 42997351203（job 130444646182），3 分 5 秒后 success，创建
https://github.com/hs40/Clash/releases/tag/v0.1.0。发布资产为
`windows-0.1.0.zip`（511,738 B，SHA-256
`38f95d6c876254142b5347146921c76a9a2dc9f1243197b87480a0412f03d7a6`）、
`openclash-0.1.0.zip`（511,688 B，SHA-256
`99fbb6157afbc3dc8b9974e8332eb3d286b6232ba445bffa31248dc5cd7980ee`）与
`SHA256SUMS`（685 B）。

用 `gh release download` 下载全部资产后复核：两个 zip 的哈希与 `SHA256SUMS` 一致；
zip 均只含 `CONFIG-DIFF.md`、`LICENSE-metacubex.txt`、`THIRD_PARTY_NOTICES.md`、
`config.yaml`；解出的配置 SHA-256 分别为
`11eceed5e5760981b691c046c0a70dc2880d348eb0e3fdf3ac1b2c2a4281c265`（Windows）与
`7bc3d2eed0cd5abc78833279896802ba5e8da075d8a07af80cd3784d403eb787`（OpenClash），
与 `SHA256SUMS` 的配置行一致。本机 Mihomo Meta v1.19.33 对两个解出的配置执行 `-t`
均退出 0（759 ms / 537 ms）。**通过。**

已知限制：`SHA256SUMS` 按完整发布目录生成 8 行，而 Release 只上传 2 个 zip 与
校验文件；单独下载全部资产后执行全量 `sha256sum -c SHA256SUMS` 会因缺少 6 个
非资产条目（两个 `config.yaml`、`CONFIG-DIFF.md`、`RELEASE-NOTES.md`、
`THIRD_PARTY_NOTICES.md`、`LICENSE-metacubex.txt`）失败。zip 行可直接校验，
回滚手册也要求按 zip 行核对。修复需要修改发布流程并生成新版本，不能改写 `v0.1.0`；
已在 `v0.1.1` 修正，见 §3.14。

2026-11-11 又推送 annotated tag `v0.1.1`（指向 main `4cb9148`），
Release run 43003842864（job 130466302486）成功，耗时 2 分 13 秒，
创建 https://github.com/hs40/Clash/releases/tag/v0.1.1 。远端发布资产、独立哈希、
zip 结构与解出配置 `-t` 的证据见 §3.14。**两次 Release 工作流均通过。**

### 3.9 本机 Mihomo 加载

```text
Mihomo Meta v1.19.33 windows amd64 with go1.26.10
configuration file ...\.tmp_release_remote_011\windows\config.yaml test is successful
configuration file ...\.tmp_release_remote_011\openclash\config.yaml test is successful
```

Windows `WIN_EXIT=0`（873 ms），OpenClash `OC_EXIT=0`（827 ms）。两份配置分别为
2,282,529 / 2,282,408 字节。这只证明配置可加载，不证明 TUN、透明代理、DNS 泄漏或
真实连通性。**通过（仅加载）。**

### 3.10 自动化测试

```text
Ran 188 tests in 195.607s
OK
```

新增覆盖：Provider 锁/快照/payload/inline、`--check` 与 `--apply` 失败路径、
发布包/zip/SHA256SUMS/差异报告/重构建一致性、清单只覆盖 Release 资产、下载目录
独立校验、篡改压缩包失败路径、Provider 与 Release 工作流策略，以及 Provider Check
的 UTF-8 控制台回归测试。**通过。**

### 3.11 PR CI

PR #3（https://github.com/hs40/Clash/pull/3）的必需检查 `test` 已通过：
代码提交 `566a3d5` 为 run 42962911064 / job 130333415834；`dc6e47c`
为 run 42963182242 / job 130334276545；最终文档提交 `22c1133` 为
run 42963854278 / job 130336409369。三次运行均包含依赖哈希安装、双平台构建、
敏感扫描、CI 策略检查、184 项测试与 Mihomo `-t`。

合并后 main CI 为 run 42964259372，head `c3436d3`，结论 success。

`v0.1.1` 修正的 PR #10（https://github.com/hs40/Clash/pull/10）head `6d0555b`，
必需检查 `test` 为 run 43003297837 / job 130464452035，success，3 分 00 秒；
squash merge 为 `4cb9148`。合并后 main CI run 43003765690 / job 130466035098，
success，2 分 19 秒。

Provider Check 与 Release 工作流不会被 PR 触发（前者只看 schedule/dispatch，后者只看
`v*` tag）。Provider Check 见 §3.12，Release 见 §3.8，issue 创建见 §3.13。
**PR CI、main CI、Provider Check 与两次 Release 均通过。**

### 3.12 远端 Provider Check（2026-11-11）

首次在 main 手动触发 run 42969347805 失败：`scripts/update_providers.py` 第 177 行
中文输出在 windows-latest 的 cp1252 控制台触发
`UnicodeEncodeError: 'charmap' codec can't encode characters...`，job 130353951706 在
“Check pinned provider sources” 步骤退出 1。

修复：`.github/workflows/provider-check.yml` 在 job 级设置 `PYTHONUTF8: "1"`，与
`ci.yml` 的 Windows 中文输出处理一致；`tests/test_ci_policy.py` 增加回归测试断言该
工作流启用 UTF-8。PR #5（https://github.com/hs40/Clash/pull/5）的 `test` 检查
run 42972002163 成功，squash merge 为 `d4a7a4a`；修复分支预验证 run 42971641453
（head `fix/provider-check-utf8`）成功。

合并后 main 的 Provider Check run 42972389013（job 130363628182）成功，步骤
“Check pinned provider sources” 与 “Open review issue when upstream changed” 均成功；
同一 commit 的 main CI run 42972337584 成功。上游当前无变化，因此该次运行未执行
`gh issue create`；issue 创建路径随后由 §3.13 的临时分支单独验证。
**Provider Check 远端运行通过；issue 创建路径见 §3.13。**

### 3.13 远端 issue 创建与清理验证（2026-11-11）

为验证 Provider Check 的变化分支，创建临时分支
`test/provider-issue-probe-20261111`，仅把 `providers/lock.yaml` 中
`geosite-private` 的 `upstream_path` 从 `geo/geosite/private.list` 改为
`geo/geosite/cn.list`。本地 `update_providers.py --check` 报告
private `changed=true`（上游 1,613,591 B，SHA-256 `703c706f...`），cn 未变化。

推送 commit `aa5c276` 后触发 Provider Check run 42996296022，运行成功；
issue #6“Provider 上游更新待审核”由 `app/github-actions` 创建，正文记录
private 从 `db9b2da8...` 变为 `703c706f...`（1,613,591 字节）：
https://github.com/hs40/Clash/issues/6 。issue 创建权限与正文内容**验证通过**。

清理阶段发现长期 Token 的 Issues 权限仍为只读：本地 API 调用 addComment 与
closeIssue 均返回 `Resource not accessible by personal access token`。新建
`close-probe-issue.yml` 并通过 `workflow_dispatch` 触发返回 404
（新 workflow_dispatch 文件必须已在默认分支）；改用测试分支上已有的
`provider-check.yml` 临时追加关闭步骤，以 `github.token` 搜索标题并关闭 issue。
run 42996752062 与 42997036944 成功，#6、#7、#8 均已关闭；测试分支本地与远端删除，
main 未改动，当前无开放 issue。**清理通过。**

长期 Token 的 Issues 权限在清理时为只读；负责人 2026-11-11 已将其改为 Read and write。
本地关闭 issue 路径尚未在该授权后重新执行，本轮不把它计为已验证。

### 3.14 v0.1.1 发布清单修正（2026-11-11）

**问题。** `v0.1.0` 的 `SHA256SUMS` 有 8 行，覆盖完整发布目录；GitHub Release 只上传
两个平台 zip 与 `SHA256SUMS`。在下载目录执行全量 `sha256sum -c SHA256SUMS` 会因为
缺少配置、说明和许可证等 6 个非资产条目失败，只有 zip 行能校验。

**修正。** `scripts/release.py` 新增 `_asset_names(version)`，构建时只把
`windows-<version>.zip` 与 `openclash-<version>.zip` 写入 `SHA256SUMS`；
`verify_release` 要求清单与该资产集合完全一致，同时仍校验发布目录的完整文件集合
（两份配置、两个 zip、说明、许可证、差异报告、`SHA256SUMS`）以及 zip 内配置与差异
报告副本。发布说明与 [ROLLBACK.md](ROLLBACK.md) 改为“只校验两个 zip，下载目录可直接
`sha256sum -c`”。`VERSION` 升为 `0.1.1`；`v0.1.0` 不改写。

**本地证据。**
- 先写失败测试：旧清单下 `test_checksums_cover_only_release_assets`、
  `test_downloaded_assets_verify_with_checksum_file` 失败；修正后 15 项发布测试
  109.976 秒通过，3 项关键测试在 0.1.1 下 16.553 秒通过。
- 全量测试：188 项通过，0 失败，0 错误（195.607 秒）。
- `release.py --version 0.1.1 --out dist\release` 与
  `release.py --verify dist\release\0.1.1` 退出码均为 0。
- 带 `dist/release/0.1.0` 基线构建时，`dist/release/0.1.1/SHA256SUMS` 的 zip 行为
  `openclash-0.1.1.zip` `5f044fca...d8a137`（511,744 B）与
  `windows-0.1.1.zip` `3dbe9705...9d01b4`（511,794 B）；这是 `CONFIG-DIFF.md`
  包含与 0.1.0 比较内容的结果。
- 在不含任何旧版本的干净目录 `.tmp_release_clean` 重新构建，得到与远端完全相同的
  `openclash-0.1.1.zip` `3016674d...f6efa5`（511,688 B）与
  `windows-0.1.1.zip` `e55796c9...5405aee`（511,738 B），证明发布 zip 可复现；
  差异仅来自 `CONFIG-DIFF.md` 是否有上一版本基线。

**远端证据（`v0.1.1`，2026-11-11）。**
- annotated tag `v0.1.1` 指向 `4cb9148`；Release run 43003842864 / job 130466302486
  成功，耗时 2 分 13 秒，创建
  https://github.com/hs40/Clash/releases/tag/v0.1.1 。
- Release 资产恰好 3 个：`openclash-0.1.1.zip` 511,688 B / SHA-256
  `3016674d09f82493df4572d588ff37a5a4f803b3e748713eecc0ab4661f6efa5`；
  `windows-0.1.1.zip` 511,738 B / SHA-256
  `e55796c9fa7f9f5396743153d9569029b8062cf614d56baba812198254405aee`；
  `SHA256SUMS` 170 B。清单恰好两行，分别匹配上述两个 zip；不再包含非资产条目。
- 用 `gh release download v0.1.1` 下载全部资产到 `.tmp_release_remote_011`，独立计算
  两个 SHA-256 与清单一致；两个 zip 的成员均恰好为 `CONFIG-DIFF.md`、
  `LICENSE-metacubex.txt`、`THIRD_PARTY_NOTICES.md`、`config.yaml`。
- 解出的配置分别为 2,282,529 / 2,282,408 字节，SHA-256 为
  `11eceed5e5760981b691c046c0a70dc2880d348eb0e3fdf3ac1b2c2a4281c265`（Windows）与
  `7bc3d2eed0cd5abc78833279896802ba5e8da075d8a07af80cd3784d403eb787`（OpenClash）。
- 本机 Mihomo Meta v1.19.33 对解出配置执行 `-t` 均退出 0（873 ms / 827 ms）。
- **已知限制。** Release 工作流在干净检出中构建，没有更早的 SemVer 目录，因此远端
  `CONFIG-DIFF.md` 显示“未找到上一版本”，即使上一版 `v0.1.0` 已存在；当前发布流程
  没有从 GitHub 上一 Release 取比较基线。该限制不影响 `SHA256SUMS`、zip 与配置正确性，
  本版不扩展修复范围，记入第 5 节。

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

1. **issue 创建已验证，长期 Token 管理 issue 待复测。** 临时分支 run 42996296022
   创建了 issue #6，#6–#8 随后关闭，当前无开放 issue。清理时长期 Token 的 Issues 权限
   为只读，本地 API 无法 addComment/closeIssue；清理使用了 `github.token`。负责人
   2026-11-11 已把长期 Token 的 Issues 升为 Read and write，但本轮未再执行本地关闭
   issue，不能据此声称该路径已验证。
2. **`SHA256SUMS` 资产覆盖已在 `v0.1.1` 修正并远端验证。** `v0.1.0` Release
   （run 42997351203）的清单覆盖完整发布目录 8 行，而 Release 只上传 2 个 zip 与
   `SHA256SUMS`；全量 `sha256sum -c` 会因缺少 6 个非资产条目失败。`v0.1.1`
   （run 43003842864）改为清单只列两个 zip，发布目录其余文件仍做结构校验并由 zip
   内副本核对；远端 3 个资产下载后独立哈希、zip 结构、解出配置与 `-t` 均通过，
   本地 188 项测试与干净目录构建复现也通过。`v0.1.0` 保持原样，不重写。
3. **iStoreOS 的 Release 包未重测。** 内嵌 Provider 后 OpenClash 配置为 2,282,408 字节；
   平台部署已将构建产物写入设备 `clash-platform.yaml` 并通过 `mihomo -t`，但 Release zip
   本身未单独解包重测。旧产物 4,006 字节的 `-t` 结果不能代表新产物。
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
10. **远端 `CONFIG-DIFF.md` 缺少上一版本基线。** Release 工作流在干净检出中构建，
    `dist/release` 没有更早的 SemVer 目录，因此 `v0.1.0` 与 `v0.1.1` 的发布包都写
    “未找到上一版本”。本地构建只有在 `dist/release` 预先存在旧版本时才会比较。
    当前未实现从 GitHub 上一 Release 下载基线；这是发布可观测性限制，不影响清单、
    zip 或配置正确性。修复需要新的发布流程变更，建议后续版本单独评审。

---

## 6. 凭据与设备边界

- 未读取、写入或提交任何真实 Token、订阅、密码、SSH 私钥。
- 未修改 Clash Verge、OpenClash 或 iStoreOS 的真实配置；`-t` 使用本机临时目录
  `.tmp_mihomo_test`，不启动代理、不接管流量。
- 发布包中的节点仍为 TEST-NET-1 占位节点（`192.0.2.x`，`PLACEHOLDER-NOT-REAL`），
  不得用于真实部署。
- 测试与日志中的临时文件（`.tmp_*`）未提交。
