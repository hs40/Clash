# 个人网络部署平台验收报告（Windows + OpenClash）

- 日期：2026-11-13
- 分支：`main`
- 代码基线：`e377fcc`（本报告提交前）
- 需求基线：[PLATFORM-REQUIREMENTS.md](PLATFORM-REQUIREMENTS.md) v1.1（Q13–Q32）
- 结论：**Windows 与 OpenClash 均已完成真实部署，当前自动验收通过；但“选中节点地区比对”“失败回滚实机演练”和浏览器 DoH/WebRTC 等人工项尚未关闭，因此不能表述为“全部验收项已关闭”。**

---

## 1. 总览

| 平台 | 部署 | 当前自动验收 | 结论 |
| --- | --- | --- | --- |
| Windows 本机（Clash Verge Rev 2.5.10 + Mihomo v1.19.33） | 2026-11-13，run `20261113-000005-652752` | `passed: true` | 通过（出口非 CN；节点地区未比对） |
| iStoreOS 192.168.2.10（OpenClash，Mihomo alpha-gbc76c13） | 2026-11-13，run `20261113-151617-826379` | `passed: true` | 通过（出口非 CN；节点地区未比对） |

- Windows：46 个节点、13 个策略组、33 条规则；mixed-port 7897；TUN gvisor；IPv6 关闭；DNS 1053 fake-IP。
- OpenClash：55 个候选节点中 46 个可用、9 个静态坏节点被过滤；13 个策略组、33 条规则；HTTP port 7893；配置 SHA-256 `9cc3ac9981deb47ad11e972de16a378b97423572e302892923f90ba36280b150`。
- 全部自动化测试：**356 项通过，0 失败**（`Ran 356 tests in 237.406s` / `OK`）。

---

## 2. 环境与证据位置

| 项目 | 值 |
| --- | --- |
| Windows 本机 | 192.168.2.8；Clash Verge Rev 2.5.10；Mihomo v1.19.33 |
| iStoreOS | 192.168.2.10；iStoreOS 25.12.6；OpenClash；Mihomo alpha-gbc76c13 |
| Windows 部署报告 | `%LOCALAPPDATA%\ClashPlatform\windows\runs\20261113-000005-652752\report.json` |
| OpenClash 部署报告 | `%LOCALAPPDATA%\ClashPlatform\openclash\runs\20261113-151617-826379\report.json` |
| OpenClash 远端备份 | `/etc/openclash/platform-backups/20261113-151617-826379`（目录 700、文件 600，root:root） |
| OpenClash 当前配置 | `/etc/openclash/config/clash-platform.yaml`；旧 `FIB.yaml` 仍在 |

本地 `ClashPlatform\openclash` 只保留 `report.json`、`config.diff` 与备份清单 `openclash.json`；未保存含真实节点的完整配置。

---

## 3. Windows 本机

### 3.1 部署

- 命令：`deploy-windows.cmd`（经摘要确认一次；`--apply`）。
- 结果：`applied.ok = true`；写入 `profiles/Merge.yaml`、`profiles/Script.js`、`profiles.yaml`、`verge.yaml`。
- 节点/组/规则：46 / 13 / 33；规则哈希 `e19135c7bbc2e23a32b3292b7d12b96b10d4dd58fe7af9d88af566ecdc48b5db`。
- 端口：mixed-port 7897；`allow-lan: false`。
- DNS：`0.0.0.0:1053`、`fake-ip`、`198.18.0.1/16`、国内 DoH 与国外 fallback 分流。
- IPv6：物理网卡绑定已关闭；备份位于 `%LOCALAPPDATA%\ClashPlatform\windows\backups\20261113-000005-652752`。
- DNS 护栏：部署时创建 UDP/TCP 两条 `Clash DNS Guard` 规则；`dns_guard.py --check` 返回 `UDP: OK`、`TCP: OK`、`overall: OK`、退出 0。

### 3.2 当前复验

命令：

```powershell
.venv\Scripts\python.exe scripts\platform.py verify --platform windows --json
```

结果（退出 0）：

| 检查 | 结果 |
| --- | --- |
| 配置 | 46 proxies / 33 rules |
| IPv6 | `passed: true`，物理网卡无启用绑定 |
| DNS fake-IP | `198.18.0.2` 返回 `198.18.0.9`，通过 |
| 路由器 DNS `192.168.2.1:53` | 超时/被阻断，通过 |
| 公共 DNS `223.5.5.5:53` | 返回 fake-IP（无真实 A），通过 |
| HTTP | 经 7897 访问 gstatic `204`，通过 |
| 出口 | 国家码 `HK`（非 CN），通过 |
| 选中节点 | `selected: null`；`exit.verified: false`，仅降级确认“出口非 CN” |

### 3.3 限制

- 未取得 Verge 当前选中节点，无法做“节点地区 vs 出口国家码”比对；按 Q25 降级为“出口非 CN”。
- 失败自动恢复、Verge 应用回滚未在本轮实机演练；单元测试覆盖回滚命令序列。
- 浏览器 DoH/DoT/WebRTC 未在本轮复验。

---

## 4. OpenClash

### 4.1 部署

- 命令：`deploy-openclash.cmd <FIB profile>`（经摘要确认一次；`--apply`）。
- 目标：独立配置 `/etc/openclash/config/clash-platform.yaml`；UCI `config_path` 指向该文件；旧 `FIB.yaml` 保留。
- 设备端 `mihomo -t`：`configuration file /etc/openclash/config/.clash-platform.yaml.tmp test is successful`。
- 端口：HTTP `port: 7893`（非 mixed-port）；`allow-lan: true`、`bind-address: "*"`。
- DNS：`127.0.0.1:7874`、`fake-ip`、`198.18.0.1/16`。
- 节点：55 个候选、46 个可用、9 个静态坏节点被过滤；13 个策略组、33 条规则。
- 配置 SHA-256：`9cc3ac9981deb47ad11e972de16a378b97423572e302892923f90ba36280b150`。
- 远端备份：`/etc/openclash/platform-backups/20261113-151617-826379`（root-only）。

### 4.2 当前复验

7893 启用了代理认证。本次经负责人明确授权，由 PowerShell 从设备 UCI 读取一次认证，仅在当前进程内注入 `CLASH_PROXY_AUTH` 后执行 verify；未写入磁盘、报告或日志，未改平台代码。平台代码仍按 Q32 只读取该环境变量，不读取设备 UCI。

命令（认证由当前进程临时提供，命令本身不含凭据）：

```powershell
.venv\Scripts\python.exe scripts\platform.py verify --platform openclash --json
```

结果（退出 0）：

| 检查 | 结果 |
| --- | --- |
| 端口 | 7893 监听，`port: true` |
| 设备本机 curl | gstatic `204`，通过 |
| Windows 经 7893 | gstatic `204`，通过 |
| DNS `192.168.2.10:53` | 返回 fake-IP `198.18.0.4`，通过 |
| 出口 | 国家码 `HK`（非 CN），通过 |
| 选中节点 | `selected: null`；`exit.verified: false`，按 Q25 降级确认“出口非 CN” |

> 部署报告生成于 `e377fcc` 之前，报告中的 `exit` 为 `null`；上表是当前代码带认证复验的结果。部署报告本身仍保留原样，不修改历史记录。

### 4.3 限制

- 未取得 Mihomo 控制接口的当前选中节点，无法做“节点地区 vs 出口国家码”比对；已按 Q25 降级。
- 未在真实设备上制造部署失败来演练自动回滚；`tests/test_platform_openclash.py` 覆盖失败回滚命令序列。
- 真实 LAN 客户端、WebRTC、重启后长期观察未在本轮执行。

---

## 5. 安全与凭据

- 仓库与部署报告中未写入真实代理认证、订阅 URL 或完整真实节点配置。
- OpenClash 完整备份只在设备 root-only 目录；本地只有哈希、差异与脱敏摘要。
- 本次 7893 认证读取是一次性验收例外，已获负责人授权；使用后立即从进程环境移除。
- `scripts/security_scan.py`：`敏感信息扫描通过`，退出 0。
- 未提交任何真实凭据；未修改主路由、NAS、HAOS、Proxmox 或其他设备。

---

## 6. 自动化验证

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 全量测试 | `.venv\Scripts\python.exe -m unittest discover -s tests -v` | `Ran 356 tests in 237.406s` / `OK` |
| 双平台构建 | `.venv\Scripts\python.exe scripts\build.py --platform all` | 退出 0，生成两份配置 |
| 敏感扫描 | `.venv\Scripts\python.exe scripts\security_scan.py` | `敏感信息扫描通过`，退出 0 |
| DNS 护栏 | `.venv\Scripts\python.exe scripts\dns_guard.py --check` | `UDP: OK` / `TCP: OK` / `overall: OK`，退出 0 |
| Windows 验收 | `scripts\platform.py verify --platform windows --json` | `passed: true`，退出 0 |
| OpenClash 验收 | `scripts\platform.py verify --platform openclash --json` | `passed: true`，退出 0 |

---

## 7. 验收清单

### 7.1 Windows（PLATFORM-REQUIREMENTS §6.1）

| 条目 | 结果 | 说明 |
| --- | --- | --- |
| 1. plan 只读、摘要、默认 No | 通过 | CLI 与单测覆盖；部署时经确认 |
| 2. deploy 写入、失败自动恢复 | 部分 | 部署成功；失败恢复未实机演练 |
| 3. Verge 加载、7897、204、fake-IP、出口非 CN | 通过 | 当前 verify 全部为 true；出口 HK |
| 4. IPv6 关闭、虚拟网卡不受影响、可回滚 | 部分 | IPv6 关闭通过；回滚未实机演练 |
| 5. 业务验证失败时保留配置待决定 | 未触发 | 本轮验证通过，未制造失败 |

### 7.2 OpenClash（§6.2）

| 条目 | 结果 | 说明 |
| --- | --- | --- |
| 1. 旧 FIB 保留、独立文件、UCI 可切回 | 通过 | `FIB.yaml` 存在；`config_path` 指向新文件 |
| 2. `mihomo -t`、服务运行、7893 监听 | 通过 | 设备端测试成功；端口 true |
| 3. Windows 经 7893 204；`.10:53` fake-IP | 通过 | 两项均通过 |
| 4. 出口地区与选中节点一致；否则降级 | 部分 | 出口 HK 非 CN；选中节点未取得，已降级 |
| 5. 失败自动回滚；回滚后 7893/53 恢复 | 未实机 | 单测覆盖命令序列，未制造真实失败 |
| 6. 本地无完整配置；设备备份 root-only | 通过 | 备份目录 700、文件 600；本地仅报告/差异 |

### 7.3 通用（§6.3）

| 条目 | 结果 | 说明 |
| --- | --- | --- |
| 1. DNS 不泄漏自动三项 | 通过 | 默认 fake-IP；路由器 DNS 阻断；公共 DNS 无真实 A |
| 2. dsh-pocket/Tailscale 人工项 | 未复验 | 本轮未重新验证 LAN 数据面、Cloudflare 隧道与 MagicDNS |
| 3. 全量测试、构建、敏感扫描 | 通过 | 356 项测试；构建/扫描退出 0 |
| 4. 不提交真实凭据/节点 | 通过 | 敏感扫描通过；报告只含计数/哈希 |
| 5. 高风险变更部署前确认 | 通过 | 负责人已批准部署；Q32 一次性例外已单独授权 |

---

## 8. 遗留问题

1. **选中节点地区比对未完成**：Windows 与 OpenClash 均只确认“出口非 CN”，未证明当前选中节点与出口地区一致；需控制接口可用后补测（Q25）。
2. **失败回滚未实机演练**：自动回滚只有单元测试覆盖；未在真实设备制造部署失败。
3. **人工项未复验**：浏览器 DoH/DoT/WebRTC、真实 LAN 客户端、重启后长期观察、dsh-pocket/Tailscale 链路。
4. **ENG-04 范围限制仍在**：NAS 显式代理、HAOS 透明代理、Proxmox 默认网关未验证；本报告不改变 ENG-04 的“部分通过”结论。
5. **PR #17 尚未审查合并**：本报告与相关文档更新需提交 PR，等待 CI 与负责人审查。

---

## 9. 结论

Windows 与 OpenClash 的部署、配置加载、端口、HTTP、DNS fake-IP 和“出口非 CN”均已由当前代码自动验证通过；全量测试、构建与敏感扫描通过。由于节点地区比对、失败回滚实机演练和人工项仍未关闭，本次结论为：

**自动验收通过，完整验收尚未全部关闭；不得据此宣称所有安全与网络目标已最终验收。**
