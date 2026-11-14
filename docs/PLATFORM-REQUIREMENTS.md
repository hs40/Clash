# 个人网络部署平台需求（v1.1）

- 状态：**平台代码与 389 项本地测试完成；Windows 与 OpenClash 均已真实部署并通过自动验收；Q25 选中节点地区比对、Windows/OpenClash 失败回滚实机演练、8 条 CIDR DNS 护栏 `--remove` 演练、NAS 显式代理端到端均已关闭；dsh-pocket UI 重试与 WorkBuddy UI 重启复验由负责人确认关闭。浏览器 DoH/DoT/WebRTC 只读评估完成，真实 LAN 客户端、重启后长期观察等仍为人工开放项。**
- 代码基线：`08cba52`（PR #23 合并后的 main，2026-11-14 同步；需求条款未变）。PR #17 已合并（`de4d5be`），PR #18 已合并（`3cf7774`），PR #19 已合并（`c680be0`），PR #20 已合并（`0fc58ca`），PR #21 已合并（`5091485`），PR #22 已合并（`953bcde`），PR #23 已合并（`08cba52`）。
- 实现：`scripts/platform*.py`、`deploy-windows.cmd`、`deploy-openclash.cmd`、`rollback.cmd`；单元测试见 `tests/test_platform*.py`、`tests/test_dns_guard.py`。
- 适用范围：本机 Windows（Clash Verge Rev + Mihomo）与 iStoreOS 192.168.2.10（OpenClash）。
- 依据：`Clash 配置工程开发 Plan.md`、负责人 2026-11-11/12/13 的 Q13–Q32 回答、2026-11-12 iStoreOS 只读核查。
- 原则：简单、可靠、可验证、可回滚；不扩范围；不伪造节点/订阅/设备/测试；不提交真实凭据；高风险变更须负责人审查。

## 1. 目标与非目标

### 1.1 目标

1. 用一套命令完成 Windows 与 iStoreOS 的**计划、部署、验证、回滚**。
2. Windows 使用 Clash Verge 的全局 Merge/Script，保留现有 FIB 订阅与节点来源，不把订阅 URL 写入平台。
3. iStoreOS 使用 OpenClash 独立配置文件，保留旧配置，部署失败自动回滚，生产中断控制在 1–3 分钟。
4. DNS 使用 Fake-IP，关闭受管端点 IPv6；对“网关和 DNS 都指向 192.168.2.10 的设备”承诺 DNS 不泄漏，并自动验证可观测项。
5. 为 dsh-pocket（LAN 3081 / Cloudflare 隧道）与 Tailscale 增加 DIRECT 分流规则，避免被 TUN/兜底代理掐断。
6. 保留现有发布工程（CI、Release、Provider 周检查、CODEOWNERS、分支保护）。

### 1.2 非目标

- 不做 Web UI、桌面 GUI、后台常驻自动同步。
- 不管理订阅、不刷新订阅、不保存订阅 URL；节点只从本机已下载的 FIB profile 读取。
- 不改主路由 192.168.2.1；不替其他设备改网关/DNS；不承诺未受管设备的 DNS 不泄漏。
- 不实现完整 Provider 管理、通用规则引擎、自动发布新平台版本。
- 不修改 OpenClash 的 dnsmasq/防火墙/策略路由实现；这些由 OpenClash 运行时负责，平台只配置和验证。
- 不在本地保存含真实节点的完整 OpenClash 配置；完整备份只留 iStoreOS root-only 目录。

## 2. 已确认决策（Q13–Q31）

| ID | 决策 |
|---|---|
| Q13 | Windows 部署前显示摘要差异（节点增删、策略组、端口、DNS 关键值、规则数与哈希、将写文件）；默认 No，输入 y 才继续；无差异则结束；完整 diff 写入报告。 |
| Q14 | 不改主路由；“全接管/DNS 不泄漏”只承诺网关和 DNS 都指向 192.168.2.10 的设备；其他设备范围外。 |
| Q15 | 使用专用 ed25519 密钥 + 口令，交给 Windows ssh-agent；平台只通过 agent 认证，不读取私钥内容。 |
| Q16 | 用环境变量 `CLASH_NODE_SOURCE` 显式指定 FIB profile YAML；平台只读，不依赖当前激活 profile。 |
| Q17 | SSH 为 `root@192.168.2.10:22`，环境变量可覆盖；公钥由负责人手动安装一次；平台不改 SSH 配置、不禁用密码登录；首次核对并固定主机指纹。 |
| Q18 | 单一 `scripts/platform.py` CLI：`status/plan/deploy/rollback/verify`；默认 plan 只读；deploy 必须 `--apply` 且确认一次；`.cmd` 只是包装。 |
| Q19 | 测试接缝：S1 CLI 子进程；S2 纯规划/校验函数；S3 可注入适配器（Windows 文件操作、OpenClash SSH 固定命令、fake runner）；不测私有函数；真实设备只做人工验收。 |
| Q20 | 关闭 IPv6。Windows 关闭物理网卡 IPv6 绑定；iStoreOS 关闭 OpenClash IPv6。 |
| Q21 | 范围仅 Windows 本机 + iStoreOS 自身；其他设备逐台处理，平台只验收不代改。 |
| Q22 | Windows 只对物理网卡执行 `Disable-NetAdapterBinding -ComponentID ms_tcpip6`，保留 Mihomo/Tailscale 虚拟网卡；记录原绑定状态，可 Enable 回滚。 |
| Q23 | 写完 Windows 配置后优先用计划任务 `Clash Verge (Admin)` 重启；等待端口/核心就绪，超时即停并提示手动重启；配置和备份保留，是否回滚等负责人确认。 |
| Q24 | OpenClash 自动验收只做平台能真实观测的：SSH `mihomo -t`、服务/端口、iStoreOS 本机 curl、Windows 经 192.168.2.10:7893 HTTP、Windows 查询 192.168.2.10:53 fake-IP、出口 IP 地区；真实 LAN 客户端、WebRTC、重启后长期观察为人工项。 |
| Q25 | 通过 Mihomo 控制接口读取当前选中节点，按地区关键词映射国家码，再与出口 IP 国家码比对；接口不可用时降级为“出口非 CN”并标注未验证。 |
| Q26 | DNS 不泄漏自动判定：默认 DNS 返回 fake-IP；直连 LAN DNS（192.168.2.1:53）和公共 DNS（如 223.5.5.5:53）被阻断/劫持且无真实 A；受管端点 IPv6 已禁用。浏览器 DoH/WebRTC/第三方泄漏网站为人工项。 |
| Q27 | OpenClash 写独立 `/etc/openclash/config/clash-platform.yaml` 并通过配置选择切换；旧配置原样保留；回滚切回旧配置。 |
| Q28 | 回滚恢复本次部署改过的全部状态：配置/Merge/Script、profile 选择、防火墙 DNS 规则、Windows 物理网卡 IPv6 绑定、iStoreOS UCI/dnsmasq/防火墙/策略路由、服务启停；只回滚平台实际改过的项，部署前状态记入备份清单。 |
| Q29 | 本地不存含真实节点的完整 OpenClash 配置；本地只保留备份清单/哈希/差异报告；完整备份只留 iStoreOS root-only 目录；本地报告保留最近 5 次。 |
| Q30 | 先做 iStoreOS 只读核查，再实现平台。 |
| Q31 | 2026-11-12 补充：Windows DNS 护栏放行受控解析器 192.168.2.10:53；仍阻断 192.168.2.0/24 内其余地址的 53，原因是 OpenClash 验收需要查询 192.168.2.10:53 的 fake-IP。 |
| Q32 | 2026-11-13：OpenClash 7893 代理认证改用一次性环境变量 `CLASH_PROXY_AUTH`（`user:pass`）。平台只在内存读取，用于设备本机 curl 与 Windows 探针；不落盘、不写日志、不放进命令参数；不读取设备 UCI 中的认证。建议用 `Read-Host` 输入，避免凭据进入 PowerShell 命令历史。未设置时按匿名验证，若 407 则验收失败并按 Q28 自动回滚。2026-11-13 验收时经负责人单独授权，由 PowerShell 一次性读取设备 UCI 认证并仅在当前进程注入环境变量；平台代码未改变，不构成 Q32 的常规路径。 |

## 3. 环境与固定参数

| 项 | 值 |
|---|---|
| Windows 本机 | 192.168.2.8；Clash Verge Rev 2.5.10；Mihomo v1.19.33；mixed-port 7897；TUN gvisor；DNS 0.0.0.0:1053 |
| Windows 默认网关/DNS | 192.168.2.1（平台不改） |
| iStoreOS | 192.168.2.10；iStoreOS 25.12.6；OpenClash；Mihomo alpha-gbc76c13 |
| OpenClash 节点入口 | 7893（HTTP port）；LAN 允许；bind-address `*` |
| OpenClash 配置目录 | `/etc/openclash/config/`；部署前生产 `FIB.yaml`，2026-11-13 起 UCI `config_path` 指向 `clash-platform.yaml`；旧 `FIB.yaml` 保留 |
| OpenClash DNS | 生产实际监听 7874；dnsmasq 在 53 接收并转发；nftables 将 LAN 53 重定向到 dnsmasq |
| iStoreOS 网络 | br-lan 192.168.2.10/24；默认网关 192.168.2.1；dnsmasq 不做 DHCP（主路由负责） |
| Tailscale | Windows 100.66.234.80；CGNAT 100.64.0.0/10 已直连 |
| 节点来源 | 本机 FIB profile，inline proxies；不使用订阅 URL；过滤非法 REALITY short-id |

## 4. 架构

### 4.1 CLI

```
scripts/platform.py status  --platform windows|openclash [--json]
scripts/platform.py plan    --platform windows|openclash [--node-source PATH] [--json] [--diff]
scripts/platform.py deploy  --platform windows|openclash --apply [--yes] [--node-source PATH]
scripts/platform.py verify  --platform windows|openclash [--json]
scripts/platform.py rollback --platform windows|openclash --backup-dir PATH [--yes]
```

- 默认命令是 `plan`；`deploy` 不带 `--apply` 不写任何文件并退出 4。
- `--apply` 必须交互确认；`--yes` 只用于非交互/测试，仍打印摘要。
- `--node-source` 优先于 `CLASH_NODE_SOURCE`；Windows 不传时读取 Verge 当前 profile，可用 `--profile` 指定 UID；OpenClash 必须显式指定。
- 无差异时 `deploy` 打印摘要后结束，不创建状态目录，也不要求确认。「差异」按整份配置判定：除节点增删、策略组增删、端口、DNS 关键值、规则、rule-providers 外，**同名策略组的 type/url/interval/tolerance/proxies/icon 等属性变化也计入差异**（2026-11-14 修复漏判缺陷）。
- 退出码：0 成功；1 执行/验证失败；2 参数或配置错误；4 未确认/用户取消。

### 4.2 模块划分（避免过度抽象）

| 文件 | 职责 |
|---|---|
| `scripts/platform.py` | argparse、命令编排、确认、退出码；S1 接缝 |
| `scripts/platform_diff.py` | 摘要差异、完整 diff、脱敏与目标键裁剪；S2 |
| `scripts/platform_windows.py` | Verge 计划/写入/重启/验证/回滚；IPv6 绑定适配器 |
| `scripts/platform_openclash.py` | 读取节点、生成配置、SSH 上传/备份/切换/重启/验证/回滚 |
| `scripts/platform_ssh.py` | 固定 SSH 命令、主机指纹、超时；可注入 runner；S3 |
| `scripts/platform_probe.py` | DNS、HTTP、出口 IP、端口探测；可注入；S3 |
| `scripts/platform_state.py` | 状态目录、报告保留 5 次、备份清单 |
| `scripts/platform_verify.py` | 平台无关的验证编排与结果汇总 |
| `scripts/dns_guard.py` | Windows 防火墙 DNS 护栏；只增删两条规则 |

复用现有：`scripts/build.py`、`scripts/providers.py`、`scripts/regions.py`、`scripts/verge_global.py`、`scripts/verge_apply.py`、`scripts/verge_preflight.py`、`scripts/dns_guard.py`。

### 4.3 状态与报告

- 默认状态目录：`%LOCALAPPDATA%\ClashPlatform\`（可用 `CLASH_PLATFORM_STATE` 覆盖；测试用临时目录）。
- 每次部署创建两个独立目录：`<state>/<platform>/runs/<stamp>/`（`report.json`、`config.diff`）与 `<state>/<platform>/backups/<stamp>/`（备份）。
- `prune_runs` 只保留最近 5 个 runs；不删除 backups，避免删掉可回滚备份。
- Windows 备份沿用 `verge_apply.backup` 的六文件 + manifest；备份目录放在 `backups/<stamp>/`。
- OpenClash 本地只存清单/哈希/差异；设备端 `/etc/openclash/platform-backups/<stamp>/` 存完整配置与 UCI 快照，权限 600/700、root:root。

## 5. 配置契约

### 5.1 节点来源

- Windows：节点来自 **Verge 已有的 profile 文件**（默认当前 profile，可用 `--profile UID` 指定；必须在 `%APPDATA%\io.github.clash-verge-rev.clash-verge-rev\profiles\` 下，且 UID 在 `profiles.yaml` 中）。平台切换到该 profile，不新建 profile；UID 不存在直接报错。`CLASH_NODE_SOURCE` 只用于 OpenClash。
- OpenClash：`CLASH_NODE_SOURCE` 指向本机 FIB profile YAML；只读；只接受 inline `proxies`；遇到 `proxy-providers` 报错并说明“请先在 Verge 中下载/导出 inline profile”。
- 节点过滤：复用 `verge_preflight.valid_short_id`，过滤非法 REALITY short-id；用本地 Mihomo `-t` 逐节点预检；全部不可用则中止。
- 不读取/保存订阅 URL；不访问订阅接口；不把真实节点写入仓库或报告。

### 5.2 Windows 生成

- 复用 `verge_global.build_merge/build_script`，保留全局 Merge/Script 机制。
- 生成后必须满足：`mixed-port 7897`、`mode rule`、`ipv6 false`、`allow-lan false`、`tun.enable true/stack gvisor`、`dns.listen 0.0.0.0:1053`、13 组固定顺序、规则以 `MATCH,PROXY` 唯一结尾。
- `verge_apply.verify_config` 的规则数使用由 `configs/common/rules.yaml` 计算出的期望值（当前 33 条），不硬编码。
- IPv6：仅物理网卡 `Disable-NetAdapterBinding -ComponentID ms_tcpip6`；记录每张网卡原状态；不改 Tailscale/Mihomo 虚拟网卡；不改系统 DNS/hosts/路由；防火墙仅由 `dns_guard.py` 增删两条 DNS 护栏规则。
- 重启：优先计划任务 `Clash Verge (Admin)`；等待 mixed-port 监听和 `clash-verge.yaml` 生成；超时退出 1，保留配置/备份，提示负责人决定回滚。
- 自动回滚边界：写文件/YAML/进程重启失败 → `verge_apply` 自动恢复备份；配置已加载但业务验证失败 → 不自动回滚，报告并等待负责人确认（Q23）。

### 5.3 OpenClash 生成

- 用 `build_platform("openclash")` 生成基线，替换占位节点为 FIB 真实节点，重算策略组与规则；产物写入临时文件，校验后上传。
- 配置写到 `/etc/openclash/config/clash-platform.yaml`；旧 `FIB.yaml` 不改；UCI `config_path` 指向新文件；重启 OpenClash。
- 不写 OpenClash 运行时注入键：`redir-port`、`tproxy-port`、`iptables`、`external-controller`、`secret`；不新增自定义 nftables 规则；不修改 dnsmasq/策略路由；依赖 OpenClash 现有 redirect。
- DNS：OpenClash 实际由 UCI `dns_port=7874` 接管，生产实际监听 7874。平台生成配置时使用 `dns.listen: 127.0.0.1:7874`（负责人已确认；不沿用公共 1053），`enhanced-mode: fake-ip`、`ipv6: false`；LAN 53 仍由 dnsmasq/OpenClash 重定向。
- 部署顺序：本地生成 → 本地静态校验 → SSH 上传临时文件 → 设备 `mihomo -t` → 备份旧配置/UCI → 原子替换新配置 → `uci set config_path` → 重启 → 验证；任一步失败按 Q6/Q28 自动回滚。
- 验证：`mihomo -t`、服务/端口、iStoreOS 本机 curl、Windows 经 7893、Windows 查询 192.168.2.10:53 fake-IP、出口 IP 国家码；LAN 客户端/WebRTC/长期观察为人工项。
- 7893 代理认证（Q32）：部署前在当前 PowerShell 会话执行 `$env:CLASH_PROXY_AUTH = Read-Host "输入 7893 认证（user:pass）"`，避免凭据进入命令历史；平台只从环境变量读取并仅在内存使用；部署后执行 `Remove-Item Env:\CLASH_PROXY_AUTH`。平台不读取设备 UCI 认证，不把凭据写入报告、日志、命令行参数或 SSH 命令。
- `external-controller :9090` 是现有生产配置，不在本次变更范围；平台只通过 SSH 本机访问验证，不新增暴露。

### 5.4 Tailscale 与 dsh-pocket 规则

在 `configs/common/rules.yaml` 的特殊层新增（顺序在 `DOMAIN-SUFFIX,local,DIRECT` 之后、CGNAT 之前或紧随其后）：

- `DOMAIN-SUFFIX,argotunnel.com,DIRECT`
- `DOMAIN-SUFFIX,trycloudflare.com,DIRECT`
- `IP-CIDR,198.41.192.0/24,DIRECT,no-resolve`
- `DOMAIN-SUFFIX,tailscale.com,DIRECT`
- `DOMAIN-SUFFIX,tailscale.io,DIRECT`
- `DOMAIN-SUFFIX,ts.net,DIRECT`
- 保留 `IP-CIDR,100.64.0.0/10,DIRECT,no-resolve`
- 不新增 `IP-CIDR,192.168.2.0/24,DIRECT`；`GEOIP,LAN` 已覆盖 LAN 直连，若 dsh-pocket 诊断需要再单独提案。

DNS 的 Tailscale MagicDNS（`*.ts.net` → 100.100.100.100）先不写 `nameserver-policy`；部署后用 `nslookup`/Tailscale 实测。若 MagicDNS 被 Fake-IP 破坏，再单独提案 DNS 策略并请负责人审查。

### 5.5 规则顺序与测试

- 四层顺序不变：special → business → base → fallback。
- 新规则加在 special 层，使用未占用的 priority；不得改变现有规则优先级或 MATCH 最后一条。
- 测试：规则唯一、目标存在、MATCH 唯一最后、dsh-pocket/Tailscale 命中 DIRECT、规则数由源计算而非硬编码。

### 5.6 Windows DNS 护栏

- `scripts/dns_guard.py` 只增删两条 Windows 防火墙出站 Block 规则（UDP/TCP 53），组名 `Clash DNS Guard`；不改系统 DNS、hosts、路由或代理设置。
- 阻断范围为 `192.168.2.0/24` 去掉 `192.168.2.10/32` 后的精确 CIDR 集合：`192.168.2.0/29`、`192.168.2.8/31`、`192.168.2.11/32`、`192.168.2.12/30`、`192.168.2.16/28`、`192.168.2.32/27`、`192.168.2.64/26`、`192.168.2.128/25`。
- 部署时 `platform_windows.apply_windows` 调用 `dns_guard.apply`；回滚只删除本次创建的规则；`--check` 只读，`--apply`/`--remove` 需要管理员。
- 规则校验同时接受 CIDR 与 Windows 返回的 netmask 形式；旧的整体 `/24` 规则会被判为不合格并重建。

## 6. 验收标准

### 6.1 Windows

1. `plan` 不写文件；摘要显示节点增删/组/端口/DNS/规则哈希/文件列表；默认 No。
2. `deploy --apply` 经确认后写入；失败自动恢复 Merge/Script/profile/verge.yaml/clash-verge.yaml。
3. Verge 加载成功；mixed-port 7897 监听；通过 7897 访问 gstatic 204；DNS 返回 fake-IP；出口 IP 非 CN。
4. 物理网卡 IPv6 绑定关闭；Tailscale/Mihomo 虚拟网卡不受影响；回滚可恢复原绑定。
5. 配置加载成功但业务验证失败时，配置/备份保留并明确要求负责人决定回滚。

### 6.2 OpenClash

1. 不改旧 `FIB.yaml`；新配置独立文件；UCI `config_path` 可切回。
2. 设备 `mihomo -t` 通过；OpenClash 服务运行；7893 监听。
3. Windows 经 192.168.2.10:7893 HTTP 访问 gstatic 204；查询 192.168.2.10:53 返回 fake-IP。若 7893 启用代理认证，先按 Q32 设置一次性 `CLASH_PROXY_AUTH`，否则预期 407 并使验收失败。
4. 出口 IP 地区与当前选中节点一致（API 可用时）；不可用时标注“出口非 CN，未验证节点地区”。
5. 任意部署失败自动回滚旧配置并重启；回滚后 7893/53 恢复。
6. 本地无完整 OpenClash 真实配置；设备备份 root-only。

### 6.3 通用

1. DNS 不泄漏自动三项（Q26）通过或明确失败；浏览器 DoH/WebRTC 为人工项。
2. dsh-pocket：LAN 访问 DSH 数据面通过；Cloudflare 隧道（如启用）不再被 TUN 掐断；Tailscale 连接与 MagicDNS 可用（人工确认）。
3. 全量测试（含平台与 DNS 护栏）全过，最终数量记录在 `docs/PLATFORM-ACCEPTANCE.md`；`build --platform all` 退出 0；`security_scan` 退出 0。
4. 不提交真实凭据/节点；报告只含哈希和脱敏摘要。
5. 所有高风险变更（DNS 端口、IPv6、OpenClash 切换、规则新增）已在部署前由负责人确认。

## 7. 测试接缝与测试计划

- S1：`tests/test_platform_cli.py` 子进程；`--help`、未知平台、默认 plan 不写、`--apply` 无确认退出 4、`--yes` 进入、错误退出码。
- S2：`tests/test_platform_diff.py`、`tests/test_platform_state.py`、`tests/test_platform_probe.py`、`tests/test_platform_verify.py`；纯函数/临时目录；断言节点增删/组增删/组属性变化/端口/DNS/规则哈希、脱敏、状态保留、fake-IP/出口国家码。
- S3：`tests/test_platform_windows.py`、`tests/test_platform_openclash.py`、`tests/test_platform_ssh.py`；fake runner 记录命令；断言顺序、超时、回滚、未执行危险命令、无真实网络。
- 规则与护栏：`tests/test_platform_rules.py`、`tests/test_dns_guard.py`；dsh-pocket/Tailscale DIRECT、顺序、唯一性、MATCH 最后；LAN 53 排除 192.168.2.10。
- 真实设备：只做人工验收，不在 unittest 中执行 SSH/写配置。

## 8. 已确认的默认值

负责人 2026-11-12 回复“同意”，以下 7 项作为实现契约：

1. **Windows 节点来源**：必须是 Verge 已有 profile，平台切换到该 profile，不新建 profile。
2. **OpenClash DNS 端口**：生成配置使用 `dns.listen: 127.0.0.1:7874`，不沿用公共 1053。
3. **iStoreOS IPv6**：只设 OpenClash `ipv6_enable=0`、`ipv6_dns=0`，不改 sysctl。
4. **Tailscale DNS**：先只加路由 DIRECT 规则，不写 `nameserver-policy`；实测 MagicDNS 后再决定。
5. **Windows 验证失败**：配置已加载但业务验证失败时保留配置/备份，等负责人确认是否回滚（Q23），不自动回滚。
6. **状态目录**：默认 `%LOCALAPPDATA%\ClashPlatform\`，报告保留 5 次。
7. **dsh-pocket 范围**：本次只加 DIRECT 规则并做 LAN/隧道验证；若仍失败，另开插件诊断，不直接改插件。

## 9. 下一步

1. DNS 护栏已应用 A 决策的 8 条 CIDR 新策略；`dns_guard.py --check` 返回 UDP/TCP/overall OK，`192.168.2.10:53` 返回 fake-IP，`192.168.2.1:53` 超时。
2. Windows 已完成真实部署（run `20261113-000005-652752`）；当前 verify 通过，Q25 选中节点地区比对已通过命名管道控制接口取得叶子节点并验证出口 HK 一致（见 `docs/PLATFORM-ACCEPTANCE.md` §3.4）；失败→自动回滚→重部署实机演练已完成（§3.5）。
3. OpenClash 已完成真实部署；PR #18 的 DNS `#PROXY` 补丁已重部署（run `20261113-195320-018656`）；2026-11-14 按 v1.33 再次重部署（run `20261114-162319-318535`，设备当前 SHA-256 `b6c385148c53c54ac10f855701f2c45a4377ddbbb0edecdd2906e1a36f2499e0`，13 组 PNG 图标 + url-test/fallback 契约逐项复核）；受控失败→自动回滚→设备恢复实机演练已完成且 16 项检查全过（§4.5）；OpenClash 端 Q25 按契约仍降级为「出口非 CN」（设备控制接口需认证，按 Q3 决定不新增凭据读取）。
4. 已写 `docs/PLATFORM-ACCEPTANCE.md`；本轮已关闭 Q25、双平台失败回滚实机演练、DNS 护栏 `--remove`、NAS 显式代理端到端、dsh-pocket/WorkBuddy UI 复验；浏览器 DoH/DoT/WebRTC 完成只读策略/netlog 评估，真实 LAN 客户端/重启后长期观察/可见浏览器开关/第三方泄漏站点仍为人工开放项。
5. PR #17（`de4d5be`）与 PR #18（`3cf7774`）已由负责人审查合并；OpenClash 新配置已部署。
6. ENG-04：NAS 显式代理端到端已验证（网关仍 192.168.2.1、经 192.168.2.10:7893 带一次性认证 204、出口非 CN）；HAOS/Proxmox 仍未部署，设备就绪后回补。

---

平台代码已实现并通过 389 项本地测试；**Windows 与 OpenClash 均已完成真实部署、自动验收与失败回滚实机演练，未提交真实凭据或节点**；PR #17 已 squash 合并为 `de4d5be`，PR #18 已 squash 合并为 `3cf7774` 并完成 OpenClash 重部署（见 `docs/PLATFORM-ACCEPTANCE.md` §4.4）。OpenClash 代理认证按 Q32 只使用一次性环境变量；验收读取 UCI 的一次性例外已在 `docs/PLATFORM-ACCEPTANCE.md` 记录。
