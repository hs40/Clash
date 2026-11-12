# Clash 配置工程（hs40/Clash）

用一套公共配置，生成 **Windows（Clash Verge Rev）** 与 **OpenClash（iStoreOS 旁路由）**
两份完整的 Mihomo 配置：

```
configs/common/*.yaml  ─┐
configs/windows/*.yaml ─┼─> scripts/build.py ─> dist/windows/config.yaml
configs/openclash/*.yaml┘                   └─> dist/openclash/config.yaml
```

- 需求基线：[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
- MVP 验收报告：[docs/MVP-ACCEPTANCE.md](docs/MVP-ACCEPTANCE.md)
- ENG-01 验收报告：[docs/ENG-01-ACCEPTANCE.md](docs/ENG-01-ACCEPTANCE.md)
- ENG-02 验收报告：[docs/ENG-02-ACCEPTANCE.md](docs/ENG-02-ACCEPTANCE.md)
- ENG-03 验收报告：[docs/ENG-03-ACCEPTANCE.md](docs/ENG-03-ACCEPTANCE.md)
- ENG-04 验收报告：[docs/ENG-04-ACCEPTANCE.md](docs/ENG-04-ACCEPTANCE.md)
- ENG-05 验收报告：[docs/ENG-05-ACCEPTANCE.md](docs/ENG-05-ACCEPTANCE.md)
- ENG-06 验收报告：[docs/ENG-06-ACCEPTANCE.md](docs/ENG-06-ACCEPTANCE.md)
- 回滚手册：[docs/ROLLBACK.md](docs/ROLLBACK.md)
- 本机 Verge 全局复用：[docs/VERGE-GLOBAL.md](docs/VERGE-GLOBAL.md)
- 安全策略：[docs/SECURITY.md](docs/SECURITY.md)
- 原始开发计划：[Clash 配置工程开发 Plan.md](Clash 配置工程开发 Plan.md)
- 兼容基准：Windows Mihomo v1.19.33；OpenClash Mihomo Meta alpha-gbc76c13（仅 OpenClash）

## 源文件与构建产物

| 类别 | 路径 | 是否入库 | 说明 |
| --- | --- | --- | --- |
| 公共配置源 | `configs/common/` | 是 | 节点、策略组、DNS、规则、全局标量 |
| 平台配置源 | `configs/windows/`、`configs/openclash/` | 是 | 仅平台专属键 |
| 构建与安全检查脚本 | `scripts/` | 是 | 构建、Provider 校验/更新、发布、依赖锁定、敏感扫描、Mihomo 校验、CI 报告/策略 |
| Provider 锁与快照 | `providers/` | 是 | 固定 commit、SHA-256、字节数和内嵌数据 |
| 第三方声明 | `THIRD_PARTY_NOTICES.md` | 是 | MetaCubeX 数据来源与 GPL-3.0 说明 |
| CI 与 CODEOWNERS | `.github/` | 是 | PR/push 测试、Provider 检查、tag Release、审查归属 |
| 安全清单 | `security/mihomo.yaml` | 是 | 固定 Mihomo 版本、URL 与 SHA-256 |
| 测试 | `tests/` | 是 | 构建结果、安全与 CI 策略校验 |
| 本机 Verge 部署辅助 | `scripts/verge_global.py`、`scripts/verge_preflight.py`、`scripts/verge_apply.py`、`verge-sync.cmd` | 是 | 生成/预检/应用 Verge 全局 Merge 与 Script；不进入 `dist/` 或 Release |
| 本机 DNS 泄漏护栏 | `scripts/dns_guard.py`、`dns-guard.cmd`、`docs/DNS-GUARD.md` | 是 | 可选的 Windows 两条出站防火墙规则；不改 DNS/路由；需管理员 |
| 构建产物 | `dist/` | 否（见 `.gitignore`） | 每次构建重新生成 |
| 文档 | `docs/` | 是 | 需求基线、验收报告 |

原则：**源文件入库，产物不入库**。产物必须能由源文件重复构建得到，
因此产物中不允许出现无法重建的内容（时间戳、随机值、真实订阅）。

合并契约（详见 REQUIREMENTS §11）：`platform.yaml` 是 Mihomo 顶层片段，构建时做
**顶层浅合并**，每个顶层键只有一个所有者；白名单之外的键、公共与平台重复定义的键、
同一文件内的重复键都会让构建失败，并报告文件名与键名。

策略组成员由构建期按地区识别生成（`include: all` / `include: region:<入口名>`），
不手写节点名单；规则见 REQUIREMENTS §4.2。

构建会读取 `providers/lock.yaml`，逐项校验 `providers/snapshots/*.list` 的字节数与
SHA-256，再把数据内嵌为 `rule-providers`；锁文件缺失、快照缺失或被篡改都会使构建失败。
Provider 契约见 REQUIREMENTS §8.1。

规则源文件 `configs/common/rules.yaml` 按 special / business / base / fallback 四层组织，
层内用整数 `priority` 排序；构建期校验层级、重复优先级、规则类型、目标策略组与
`MATCH` 位置，再编译为扁平规则列表。契约见 REQUIREMENTS §5。

## 环境准备

需要 Python 3.12（本项目在 3.12.3 上验证）。Windows 上请使用真实的 Python 解释器，
不要使用 `WindowsApps` 的 `python.exe` 存根。

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.txt
```

依赖锁定在 `requirements.txt`（`PyYAML==6.0.3`，精确版本 + SHA-256）；CI 使用
`pip install --require-hashes`，并在安装后执行 `pip check`。

## 构建

```powershell
.venv\Scripts\python.exe scripts\build.py --platform all
```

- `--platform`：`all`（默认用法）、`windows` 或 `openclash`。
- `--out`：输出根目录，默认 `dist/`；实际产物为 `<out>/windows/config.yaml`、
  `<out>/openclash/config.yaml`。
- `--root`：源文件根目录，默认仓库根目录；用于测试夹具或异地构建。

构建成功时退出码为 0；配置不满足合并契约时退出码为 2，错误信息包含文件名与键名，
例如：

```
构建失败：F:\...\configs\windows\platform.yaml：未登记的顶层键 'foo-bar'（允许：mixed-port, allow-lan, tun）
```

相同输入必须产生字节一致的输出：键顺序固定、无时间戳、UTF-8 无 BOM、LF 换行。

## 测试

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖（`tests/`）：

- 源文件存在性、非空与 YAML 合法性；
- 公共 / 平台配置的顶层键归属，以及平台配置不得写入公共键或运行时注入键；
- 合并契约错误路径：未登记键、公共与平台重复键、同文件重复键、缺失键、未知平台；
- 命令行：一份命令生成两份产物、两次构建字节一致、配置错误退出码 2；
- 变更传播：公共配置修改反映到两个平台，平台配置修改只影响对应平台；
- Provider：锁文件结构、来源白名单、快照大小/SHA-256、payload 解析、inline 渲染，
  以及上游检查、`--apply` 原子更新、非法 commit / payload 失败路径；
- 地区识别：七个入口名称、关键词匹配、ASCII 整词边界、多地区命中优先级；
- 策略组生成：`include` 展开、空地区回退到「自动选择」、Google 回退顺序、
  增删改节点不改变组名、无效引用与循环引用使构建失败；
- AI 策略组：OpenAI / Claude / Cursor 的成员顺序与默认选中项；
- 规则编译：四层顺序、层内 priority 排序、类型 / 目标 / `MATCH` 位置校验、
  五类业务路由基线，以及 special 压过 business 的首条匹配冲突测试；
- DNS：双平台共用同一份 DNS、Fake-IP 与 IPv4-only、Filter 4 条、国内外服务器分离、
  节点域名独立解析、无自指循环、Windows `dns-hijack`，以及多类静态校验失败路径；
- 依赖锁定：未固定版本、缺哈希、格式错误、重复依赖被拒绝；
- 敏感信息：私钥、Token、Access Key、通用密钥赋值与订阅链接凭据被识别，占位值不误报；
- Mihomo：清单字段/版本/哈希校验、`-v` 版本匹配；
- CI：中文报告计数与失败详情、工作流权限/SHA/触发条件、CODEOWNERS 核心路径；
  Provider 检查工作流与 tag Release 工作流的权限、触发和命令校验；
- 发布：SemVer 与 `VERSION` 一致性、双平台独立包、zip 成员、`SHA256SUMS`、
  中文发布说明、`CONFIG-DIFF.md`、重新构建字节一致、篡改/缺文件/zip 不一致失败路径；
- Verge 全局扩展：Merge 只含 `profile.store-selected` 与两个 inline Provider；Script 生成
  13 组/27 规则/DNS/端口、过滤坏 `short-id`、空地区回退；预检逐节点 `-t`；备份与失败回滚；
  Node 执行真实 Script（无 Node 时跳过）。
- DNS 护栏：UDP/TCP 规则规格、幂等创建/跳过、删除、Windows 点分掩码匹配（9 项）；真实防火墙已应用并完成 DNS 路径/站点验收，管理员 `check` 复核与回滚演练待完成。

## CI 与安全检查

本地可执行：

```powershell
.venv\Scripts\python.exe scripts\check_dependencies.py
.venv\Scripts\python.exe scripts\security_scan.py
.venv\Scripts\python.exe scripts\ci_policy.py
.venv\Scripts\python.exe scripts\ci_report.py --output ci-report.md
```

CI 定义在 `.github/workflows/ci.yml`：PR 与 `main` push 自动运行，固定 Action SHA、
只读权限、依赖哈希安装、双平台构建、敏感扫描、中文测试报告，并下载/校验 Mihomo
v1.19.33 后对两份产物执行 `-t`。Mihomo 版本与哈希见 `security/mihomo.yaml`。

远端 main push CI、PR CI 与 main 分支保护策略 A 已通过/启用；CODEOWNERS 强制未启用（负责人 @hs40 已明确批准该 bypass，属单人仓库限制）；`ci-report.md` 为生成物，不提交。

`.github/workflows/provider-check.yml` 每周检查上游 Provider 并创建 issue，不自动修改
`main`。`.github/workflows/release.yml` 只在推送 `v*` tag 时运行，执行测试、构建、
`release.py --verify` 并创建 GitHub Release。tag 触发是负责人 2026-11-11 批准的取舍，
与 Plan §10.1 的「main 合并后自动发布」不同，详见 REQUIREMENTS §10.1。

## Provider 更新与发布

```powershell
# 只检查，不写文件
.venv\Scripts\python.exe scripts\update_providers.py --check

# 负责人本地应用某个已审查的上游 commit（写快照与锁文件）
.venv\Scripts\python.exe scripts\update_providers.py --apply --commit <40位commit>

# 构建并校验发布包
.venv\Scripts\python.exe scripts\release.py --version 0.1.1
.venv\Scripts\python.exe scripts\release.py --verify dist\release\0.1.1
```

发布目录包含两个平台配置、两个 zip、`SHA256SUMS`、`RELEASE-NOTES.md` 与
`CONFIG-DIFF.md`。`SHA256SUMS` 只列出 Release 实际上传的两个平台 zip，下载全部
Release 资产后可直接运行 `sha256sum -c SHA256SUMS`；发布目录内的配置与说明副本由
zip 内同名文件核对。回滚步骤见 [docs/ROLLBACK.md](docs/ROLLBACK.md)，全部手动执行。

## 本机 Verge 全局复用（可选）

仓库还提供一套**本机部署辅助**工具，把同一套 MVP 设置写入 Clash Verge 的全局
Merge/Script，使所有使用 inline proxies 的订阅自动复用 13 个策略组、27 条规则与
MVP DNS；该能力不进入 dist/ 或 Release。

- 固定组顺序、预检/剔除、备份/回滚与限制见 [docs/VERGE-GLOBAL.md](docs/VERGE-GLOBAL.md)。
- 应用入口：管理员运行 verge-sync.cmd；失败自动恢复六个备份文件并重启。
- 只写 Verge AppData 的全局文件与 current，不改订阅文件、订阅 URL、系统 DNS、hosts 或路由。
- DNS 泄漏护栏是独立可选步骤，只增删两条出站防火墙规则；仅在 Mihomo TUN 接管时使用，见 [docs/DNS-GUARD.md](docs/DNS-GUARD.md)。
- 旧本地 profile mvpClash0001 保留为回退，未自动删除。

2026-11-12 已在本机 FIB 上重新部署并验证：46 节点 / 13 组 / 27 规则，7897 与 1053 监听，
TUN 与 fake-ip 正常，百度/Google/YouTube 连通；显式查询 `192.168.2.1:53` 曾绕过
TUN 返回真实地址，负责人选择方案 C 后已在管理员上下文应用两条出站阻断规则：
路由器 DNS 已超时，198.18.0.2 与 223.5.5.5 返回 fake-IP，站点回归通过；管理员 `check`
复核与 `--remove` 回滚演练仍待完成。

## 占位内容说明

MVP 阶段的 `configs/common/proxies.yaml` 使用 **TEST-NET-1（192.0.2.0/24）** 地址、
`PLACEHOLDER-NOT-REAL` 口令的占位节点。它们不是可用的代理节点，不得用于真实部署，
也不代表任何真实订阅、节点或凭据。DNS 与平台参数为 MVP 草案值，部署前必须按
REQUIREMENTS §14 在真实设备上核验。

## 当前状态

MVP-01 至 MVP-06、ENG-01、ENG-02、ENG-03、ENG-05、ENG-06 已完成本地实现并通过自动化测试；
ENG-04 已完成双平台配置，Windows 本机 v1.19.33 与 OpenClash 设备 alpha-gbc76c13 均通过
`-t` 加载验证，但 NAS 端到端、HAOS/Proxmox 路径未验证，标记为部分通过。ENG-05 的远端
main push CI、PR CI 与 main 分支保护策略 A 已验证；CODEOWNERS 强制未启用（负责人已批准），
标记为完成（策略 A）。ENG-06 的 Provider Check 与 tag 触发的 Release 工作流均已于
2026-11-11 远端运行并通过：`v0.1.0` 已发布为
[GitHub Release](https://github.com/hs40/Clash/releases/tag/v0.1.0)（run 42997351203），
`v0.1.1` 已发布为
[GitHub Release](https://github.com/hs40/Clash/releases/tag/v0.1.1)（run 43003842864）。
`v0.1.0` 的 `SHA256SUMS` 覆盖完整发布目录，与 Release 仅上传两个 zip 不一致；`v0.1.1`
已改为只覆盖两个平台 zip，发布目录其余文件由结构校验与 zip 内副本核对，下载全部资产后
可直接 `sha256sum -c`。`v0.1.1` 远端资产为 `windows-0.1.1.zip`（511,738 B，SHA-256
`e55796c9fa7f9f5396743153d9569029b8062cf614d56baba812198254405aee`）与
`openclash-0.1.1.zip`（511,688 B，SHA-256
`3016674d09f82493df4572d588ff37a5a4f803b3e748713eecc0ab4661f6efa5`）；下载后
独立哈希校验通过，解出的配置在本机 Mihomo v1.19.33 上 `-t` 通过。干净目录本地构建
可复现上述远端 zip 哈希。
Provider Check 的 issue 创建路径也用临时分支实际验证（issue #6 创建，随后 #6–#8 全部关闭）。
已知限制：Release 工作流在干净检出中构建，`CONFIG-DIFF.md` 会显示“未找到上一版本”，
尚未实现从上一 GitHub Release 读取比较基线；详见
[docs/ENG-06-ACCEPTANCE.md](docs/ENG-06-ACCEPTANCE.md) §3.14 与 §5。
内嵌 Provider 后的新产物尚未在 iStoreOS 设备上重测，因此 ENG-06 标记为
「本地完成、远端 Provider Check/Release 通过；设备待验证」。
PR #3（`c3436d3`）、PR #5（`d4a7a4a`）与 PR #10（`4cb9148`）已合并；
PR CI、main CI（run 43003765690）与 Provider Check 均通过，发布记录见
[docs/ENG-06-ACCEPTANCE.md](docs/ENG-06-ACCEPTANCE.md) §3.8、§3.13、§3.14。
验收记录见
[docs/MVP-ACCEPTANCE.md](docs/MVP-ACCEPTANCE.md)、
[docs/ENG-01-ACCEPTANCE.md](docs/ENG-01-ACCEPTANCE.md)、
[docs/ENG-02-ACCEPTANCE.md](docs/ENG-02-ACCEPTANCE.md)、
[docs/ENG-03-ACCEPTANCE.md](docs/ENG-03-ACCEPTANCE.md)、
[docs/ENG-04-ACCEPTANCE.md](docs/ENG-04-ACCEPTANCE.md)、
[docs/ENG-05-ACCEPTANCE.md](docs/ENG-05-ACCEPTANCE.md) 与
[docs/ENG-06-ACCEPTANCE.md](docs/ENG-06-ACCEPTANCE.md)。

本机 Clash Verge 全局复用已于 2026-11-12 在 FIB 订阅上重新部署并验证：46 节点 / 13 组 /
27 规则，7897 与 1053 监听，TUN 与 fake-ip 正常，关键站点连通；旧本地 profile
mvpClash0001 保留作回退。该能力是部署辅助，不进入 Release；只验证 FIB 一个订阅，
其他订阅、DNS 泄漏与回滚演练未验证。DNS 泄漏护栏见 [docs/DNS-GUARD.md](docs/DNS-GUARD.md)，
当前等待管理员应用。详见 [docs/VERGE-GLOBAL.md](docs/VERGE-GLOBAL.md)。
