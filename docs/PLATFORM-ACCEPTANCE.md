# 个人网络部署平台验收报告（Windows + OpenClash）

- 日期：2026-11-13
- 分支：`main`
- 代码基线：`c680be0`（PR #19 合并后本地 main）；本轮新增验收基于分支 `feat/q25-selected-region`
- 需求基线：[PLATFORM-REQUIREMENTS.md](PLATFORM-REQUIREMENTS.md) v1.1（Q13–Q32）、[REQUIREMENTS.md](REQUIREMENTS.md) v1.29
- 结论：**Windows 与 OpenClash 均已完成真实部署与自动验收。**
  本轮（2026-11-13）已关闭：Q25 选中节点地区比对、双平台失败回滚实机演练、8 条 CIDR DNS 护栏 `--remove` 演练、NAS 显式代理端到端、dsh-pocket UI 重试与 WorkBuddy UI 重启复验；浏览器 DoH/DoT/WebRTC 完成只读策略/netlog 评估。
  仍未关闭的人工项仅剩：真实 LAN 客户端、重启后长期观察、可见浏览器安全 DNS 开关/手动 DoH 模板/WebRTC srflx 候选/第三方泄漏站点、HAOS/Proxmox（未部署）。
  因此仍不能表述为“全部验收项已关闭”。

---

## 1. 总览

| 平台 | 部署 | 当前自动验收 | 结论 |
| --- | --- | --- | --- |
| Windows 本机（Clash Verge Rev 2.5.10 + Mihomo v1.19.33） | 2026-11-13，run `20261113-000005-652752`；DNS 补丁另经 `verge_apply.py --apply` 应用 | `passed: true` | 通过（Q25 已验证出口 HK 与选中香港节点一致；失败回滚实机演练通过） |
| iStoreOS 192.168.2.10（OpenClash，Mihomo alpha-gbc76c13） | 2026-11-13，run `20261113-151617-826379`；DNS 补丁重部署 run `20261113-195320-018656` | `passed: true` | 通过（受控失败→自动回滚实机演练 16 项检查全过；Q25 按契约降级为出口非 CN） |

- Windows：46 个节点、13 个策略组、33 条规则；mixed-port 7897；TUN gvisor；IPv6 关闭；DNS 1053 fake-IP。
- OpenClash：55 个候选节点中 46 个可用、9 个静态坏节点被过滤；13 个策略组、33 条规则；HTTP port 7893。
  首次部署配置 SHA-256 `9cc3ac9981deb47ad11e972de16a378b97423572e302892923f90ba36280b150`；
  DNS 补丁重部署后当前设备 SHA-256 `2d8dc2fee4c59bb46656288bfc174e25ea99d941c78b70c91407d5f609e37343`。
- 全部自动化测试：**371 项通过，0 失败**（2026-11-13 分支 `feat/q25-selected-region`：`Ran 371 tests in 243.677s` / `OK`，含 Q25 新增 14 项）。
- 2026-11-13 补丁：`dns.fallback` 加 `#PROXY`，修复境外 DoH 直连超时导致 `DIRECT` 域名解析失败；
  已应用到 Windows Verge（`api.trycloudflare.com` 405、`www.workbuddy.ai` 200、gstatic 204），
  并已于 run `20261113-195320-018656` 重部署到 OpenClash 设备（见 §4.4）。
  PR #17 已 squash 合并为 `de4d5be`；PR #18 已 squash 合并为 `3cf7774`；PR #19 已 squash 合并为 `c680be0`。

---

## 2. 环境与证据位置

| 项目 | 值 |
| --- | --- |
| Windows 本机 | 192.168.2.8；Clash Verge Rev 2.5.10；Mihomo v1.19.33 |
| iStoreOS | 192.168.2.10；iStoreOS 25.12.6；OpenClash；Mihomo alpha-gbc76c13 |
| Windows 部署报告 | `%LOCALAPPDATA%\ClashPlatform\windows\runs\20261113-000005-652752\report.json` |
| OpenClash 部署报告（首次） | `%LOCALAPPDATA%\ClashPlatform\openclash\runs\20261113-151617-826379\report.json` |
| OpenClash 部署报告（DNS 补丁重部署） | `%LOCALAPPDATA%\ClashPlatform\openclash\runs\20261113-195320-018656\report.json` |
| OpenClash 远端备份 | `/etc/openclash/platform-backups/20261113-151617-826379`、`/etc/openclash/platform-backups/20261113-195320-018656`（目录 700、文件 600，root:root） |
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
| 选中节点 | Q25 已验证：`selected: 香港 IX2 2倍|超高速|原生家宽`、`selected_path: [PROXY, 自动选择, 香港 IX2 2倍|超高速|原生家宽]`、`exit.verified: true`、出口 `HK` 与地区一致（见 §3.4） |

### 3.3 限制（本轮已关闭/更新）

- Q25 节点地区比对已关闭：通过 verge-mihomo.exe 命令行 -ext-ctl-pipe 取得权威命名管道，读取 PROXY→自动选择→叶子 选中链，复用 regions.classify_node 映射地区。
- 失败自动恢复 + 重部署已实机演练（§3.5）；单元测试仍保留作为回归。
- 浏览器 DoH/DoT/WebRTC 已完成只读策略/netlog 评估（§7.4）；可见浏览器开关、真实用户配置、WebRTC srflx 候选、重启后长期观察仍为人工开放项。

### 3.4 Q25 选中节点地区比对（2026-11-13 完成）

- 实现：新增 `scripts/platform_verify.py::exit_country_for_node(ip_info, selected_node)`；`scripts/platform_windows.py` 新增 `_mihomo_commands()`、`pipe_name_from_command(command)`、`controller_pipe(config)`、`_pipe_get(pipe, path, timeout=3.0)`；`selected_proxy_name(config, opener=None, timeout=3.0, pipe_get=None)` 在无 external-controller 时走命名管道；`verify_windows` 把叶子节点名交给 exit_country_for_node 并新增 selected_path。
- 真实只读验证：external-controller 为空，配置内 external-controller-pipe 是过期 sidecar；从 Get-CimInstance Win32_Process 取得权威命名管道 verge-mihomo-production-9efe...；选中链 [PROXY, 自动选择, 香港 IX2 2倍|超高速|原生家宽]，regions.classify_node → 香港节点。
- `scripts/platform.py verify --platform windows --json` 退出 0：exit 为 passed true / verified true / country HK / group 香港节点 / expected [HK] / detail 出口国家码与节点地区一致 / node 香港 IX2 2倍|超高速|原生家宽；ip 14.198.59.128 / HK / AS9269 Hong Kong Broadband Network Ltd.。
- TDD：3 个垂直切片（S2 纯函数 6 测试、S3 命名管道 5 测试、S3 verify 集成 3 测试）红→绿；合计新增 14 项测试，全量 371 项通过。

### 3.5 Windows 失败→自动回滚→重部署实机演练（负责人授权，2026-11-13）

- 方法：.tmp_win_rollback_drill.py 注入 verge_apply.write_atomic 第 1 次给 profiles/Merge.yaml 加无害 DRILL-MARKER-ROLLBACK-TEST 注释、第 3 次抛 OSError(DRILL: injected write failure at call 3)，触发 apply_migration 的 except(restore + reload)；随后不注入故障重部署；安全副本置于临时目录并在 finally 删除。
- 结果（.tmp_win_rollback_drill.json）：failed_apply_raised true，错误 DRILL: injected write failure at call 3；已回滚到迁移前文件；恢复后代理 204（17.5s）、4 个 owned 文件 SHA-256 全部等于演练前、marker 消失、护栏 OK、IPv6 以太网 false；重部署六步 [1/6]..[6/6] 校验通过，最终代理 204（13.3s）、owned 哈希再次全部等于演练前、护栏/IPv6 不变；safety_removed true。
- 演练后官方只读 scripts/platform.py verify --platform windows --json 为 passed true，Q25 verified true。演练期间 Verge 两次重启；生产中断随重部署恢复结束。助手 health() 因 len(int) 报错，不影响结论，已用官方 verify 复核。

---

## 4. OpenClash

### 4.1 部署

- 命令：`deploy-openclash.cmd <FIB profile>`（经摘要确认一次；`--apply`）。
- 目标：独立配置 `/etc/openclash/config/clash-platform.yaml`；UCI `config_path` 指向该文件；旧 `FIB.yaml` 保留。
- 设备端 `mihomo -t`：`configuration file /etc/openclash/config/.clash-platform.yaml.tmp test is successful`。
- 端口：HTTP `port: 7893`（非 mixed-port）；`allow-lan: true`、`bind-address: "*"`。
- DNS：`127.0.0.1:7874`、`fake-ip`、`198.18.0.1/16`。
- 节点：55 个候选、46 个可用、9 个静态坏节点被过滤；13 个策略组、33 条规则。
- 首次部署配置 SHA-256：`9cc3ac9981deb47ad11e972de16a378b97423572e302892923f90ba36280b150`（DNS 补丁重部署后的当前值见 §4.4）。
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

### 4.3 限制（本轮已关闭/更新）

- Windows 侧 Q25 已实现并在 §3.4 验证；OpenClash 侧按 Q3 决定保持降级策略：设备不暴露可用控制接口选中链，`verify_openclash` 仍只确认出口非 CN（`exit.verified: false`），不伪造节点信息。
- 失败自动回滚已在本轮实机演练（§4.5，16 项检查全过）；`tests/test_platform_openclash.py` 单测保留为回归。
- 真实 LAN 客户端、可见浏览器开关、WebRTC srflx 候选、重启后长期观察仍为人工开放项。

### 4.4 DNS fallback `#PROXY` 补丁重部署（负责人 m14382 授权）

PR #18 合并为 `3cf7774` 后，本地 `main` 已更新；设备仍运行旧配置（旧 SHA `9cc3ac99…`、fallback 无 `#PROXY`）。负责人 m14382 指令「PR #18 合并，OpenClash 部署新配置」。

- 部署前只读计划：`scripts/platform.py plan --platform openclash --node-source <FIB profile> --diff`；差异仅 `dns.fallback` 两行由 `https://1.1.1.1/dns-query` / `https://dns.google/dns-query` 变为 `…#PROXY`；节点 46→46、组 13→13、规则 33→33（规则 SHA-256 `e19135c7bbc2e23a32b3292b7d12b96b10d4dd58fe7af9d88af566ecdc48b5db`）。
- 部署命令（非交互、负责人已批准）：`scripts/platform.py deploy --platform openclash --apply --yes --node-source <FIB profile>`。7893 认证按 m13690 一次性授权从设备 UCI 读取，仅注入当前进程 `CLASH_PROXY_AUTH`，不打印、不落盘、不进日志或命令行；平台代码未改变。
- run `20261113-195320-018656`：`applied.ok = true`、`rolled_back: false`；远端备份 `/etc/openclash/platform-backups/20261113-195320-018656`（含 `current.yaml`、`previous-platform.yaml`）。
- 新配置 SHA-256：`2d8dc2fee4c59bb46656288bfc174e25ea99d941c78b70c91407d5f609e37343`；设备端 `mihomo -t -f /etc/openclash/config/clash-platform.yaml` 返回 `test is successful`；UCI `config_path` 仍指向独立文件，旧 `FIB.yaml` 保留。
- 设备端实测：`7893` 监听（`netstat` 显示 `clash` 进程）；`sed -n '28,29p'` 显示两条 fallback 均带 `#PROXY`；DNS `127.0.0.1:7874`、fake-IP `198.18.0.1/16` 不变。
- 部署内自动 `verify`：`passed: true`——端口 true、设备本机 curl `204`、Windows 经 `192.168.2.10:7893` gstatic `204`、`192.168.2.10:53` 返回 fake-IP `198.18.0.4`、出口国家 `MY`（非 CN，`exit.verified: false` 因未取得选中节点按 Q25 降级）。
- 合并后回归：`scripts/build.py --platform all` 退出 0；`scripts/security_scan.py` 退出 0；`git diff --check` 退出 0；`.venv\Scripts\python.exe -m unittest discover -s tests -v` → `Ran 357 tests in 163.271s` / `OK`。

### 4.5 受控失败→自动回滚→设备恢复实机演练（负责人 m14910 批准，m14918 授权）

- 方法：`.tmp_oc_rollback_drill.py` 生成一份仅追加 `# DRILL-OC-ROLLBACK-MARKER` 注释的演练配置（drill SHA-256 `5d6fb625dfd885054e0d28eb3156919bf26e3b7cd0a47dd6219a087ae11d4f78`），经 `plan_openclash` / `apply_openclash` 正常备份与部署；monkeypatch `oc._wait_port` 返回 False 制造「重启后 7893 未监听」失败，触发 `apply_openclash` 的 `except` 分支（`rm -f TEMP_CONFIG` + `_restore_remote`）；在故障瞬间捕获设备 deployed_sha256 / has_marker / config_path，恢复后逐项比对 pre/post。
- 设备 pre 状态：config_path `/etc/openclash/config/clash-platform.yaml`、enable 1、dns_port 7874、sha256 `2d8dc2fee4c59bb46656288bfc174e25ea99d941c78b70c91407d5f609e37343`、has_marker false、7893 监听、temp 不存在、config_process true。故障瞬间 deployed_sha256=drill_sha256、has_marker true，证明演练配置确已部署后才失败。
- apply 抛出 `OpenClash 重启后 7893 端口未监听；已恢复旧 config_path`，`restored=True`；远端备份 `/etc/openclash/platform-backups/clash-oc-drill-5mv2qhrr`（manifest old_sha=2d8dc2…e343、new_sha=5d6fb6…4f78、new_exists true）。
- post 与 pre 完全一致：SHA-256 恢复为 `2d8dc2…e343`、marker 消失、temp 清理、config_path/enable/dns_port 不变、7893 监听、config_process true；设备 `mihomo -t` 输出 `configuration file /etc/openclash/config/clash-platform.yaml test is successful`。
- 16 项检查全 true：apply_raised / restored_flag_true / error_mentions_restore / deployed_drill_config_before_failure / temp_removed / sha_restored / marker_removed / config_path_unchanged / enable_unchanged / dns_port_unchanged / port_open / config_process / device_config_test_ok / verify_passed / dns_fake_ip / exit_non_cn。
- 恢复后官方 `verify_openclash`：passed true、port true、device_http 204、http 204、DNS fake-IP answers [198.18.0.4]、出口 154.85.20.75 / MO（非 CN，按契约降级为 verified false）；dns_sample answers [198.18.0.5] fake_ip true。
- 结论：自动回滚把生产配置字节级恢复，UCI 未变，服务/端口/代理/DNS/出口均恢复；OpenClash 端 Q25 仍按 Q3 降级。一次性 UCI 认证仅注入当前进程 `CLASH_PROXY_AUTH`，未打印/落盘/入日志/命令行，平台代码未改。

---

## 5. 安全与凭据

- 仓库与部署报告中未写入真实代理认证、订阅 URL 或完整真实节点配置。
- OpenClash 完整备份只在设备 root-only 目录；本地只有哈希、差异与脱敏摘要。
- 首次部署、DNS 补丁重部署与 2026-11-13 回滚演练的 7893 认证读取均为一次性验收例外，已获负责人授权（m13690 / m14382 / m14910）；只注入当前进程环境，脚本结束即消失，未写入磁盘、报告或日志。
- `scripts/security_scan.py`：`敏感信息扫描通过`，退出 0。
- 未提交任何真实凭据；未修改主路由、NAS、HAOS、Proxmox 或其他设备。

---

## 6. 自动化验证

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 全量测试 | `.venv\Scripts\python.exe -m unittest discover -s tests -v` | `Ran 371 tests in 243.677s` / `OK`（2026-11-13 分支 `feat/q25-selected-region`，含 Q25 新增 14 项） |
| 双平台构建 | `.venv\Scripts\python.exe scripts\build.py --platform all` | 退出 0，生成两份配置 |
| 敏感扫描 | `.venv\Scripts\python.exe scripts\security_scan.py` | `敏感信息扫描通过`，退出 0 |
| 代码差异检查 | `git diff --check` | 退出 0 |
| DNS 护栏 | `.venv\Scripts\python.exe scripts\dns_guard.py --check` | `UDP: OK` / `TCP: OK` / `overall: OK`，退出 0 |
| DNS 护栏 remove→apply 演练 | `scripts\dns_guard.py --remove` / `--check` / `--apply` / `--check` | UDP+TCP 各 8 条 CIDR 归一化比对 `normalized_match=true n=8`，护栏恢复（§7.4） |
| Windows 验收 | `scripts\platform.py verify --platform windows --json` | `passed: true`，Q25 `exit.verified: true`，退出 0 |
| OpenClash 验收 | `scripts\platform.py verify --platform openclash --json` | `passed: true`，出口非 CN（按契约降级），退出 0 |
| Windows 失败回滚演练 | `.tmp_win_rollback_drill.py` | 文件哈希恢复、代理 204、六步重部署通过（§3.5） |
| OpenClash 失败回滚演练 | `.tmp_oc_rollback_drill.py` | 16 项检查全 true，设备字节级恢复（§4.5） |
| dsh-pocket 隧道 | quick tunnel CLI | 注册成功，URL 返回 401（无后端预期） |
| WorkBuddy 状态 | `workbuddy status` / `doctor` | Global 已登录 hs40，credit 1836.23000021 |

---

## 7. 验收清单

### 7.1 Windows（PLATFORM-REQUIREMENTS §6.1）

| 条目 | 结果 | 说明 |
| --- | --- | --- |
| 1. plan 只读、摘要、默认 No | 通过 | CLI 与单测覆盖；部署时经确认 |
| 2. deploy 写入、失败自动恢复 | 通过 | 部署成功；失败自动恢复 + 重部署已实机演练（§3.5） |
| 3. Verge 加载、7897、204、fake-IP、出口非 CN | 通过 | 当前 verify 全部为 true；出口 HK，Q25 verified true |
| 4. IPv6 关闭、虚拟网卡不受影响、可回滚 | 通过 | IPv6 关闭通过；4 个 owned 文件哈希恢复、六步重部署通过 |
| 5. 业务验证失败时保留配置待决定 | 未触发 | 本轮验证通过，未制造业务验证失败 |

### 7.2 OpenClash（§6.2）

| 条目 | 结果 | 说明 |
| --- | --- | --- |
| 1. 旧 FIB 保留、独立文件、UCI 可切回 | 通过 | `FIB.yaml` 存在；`config_path` 指向新文件 |
| 2. `mihomo -t`、服务运行、7893 监听 | 通过 | 设备端测试成功；端口 true |
| 3. Windows 经 7893 204；`.10:53` fake-IP | 通过 | 两项均通过 |
| 4. 出口地区与选中节点一致；否则降级 | 按契约降级 | 设备不暴露控制接口选中链，按 Q3/Q25 仅确认出口非 CN；Windows 侧已在 §3.4 完成比对 |
| 5. 失败自动回滚；回滚后 7893/53 恢复 | 通过 | 受控失败实机演练 16 项检查全过，设备字节级恢复（§4.5） |
| 6. 本地无完整配置；设备备份 root-only | 通过 | 备份目录 700、文件 600；本地仅报告/差异 |

### 7.3 通用（§6.3）

| 条目 | 结果 | 说明 |
| --- | --- | --- |
| 1. DNS 不泄漏自动三项 | 通过 | 默认 fake-IP；路由器 DNS 阻断；公共 DNS 无真实 A |
| 2. dsh-pocket cloudflared / WorkBuddy UI | 已关闭 | cloudflared quick tunnel 注册成功（401 为无后端预期）；WorkBuddy status 已登录、doctor 报告 stale heartbeat，UI 重启复验见 §7.4 |
| 3. 全量测试、构建、敏感扫描 | 通过 | 371 项测试（`feat/q25-selected-region`）；构建/扫描/`git diff --check` 退出 0 |
| 4. 不提交真实凭据/节点 | 通过 | 敏感扫描通过；报告只含计数/哈希 |
| 5. 高风险变更部署前确认 | 通过 | 负责人已批准部署；Q32 一次性例外已单独授权 |

### 7.4 本轮补充验证（2026-11-13）

- **浏览器 DoH/DoT/WebRTC 只读评估**：只读读取 Chrome/Edge 策略与 netlog，确认当前 TUN + fake-IP + DNS 护栏下系统解析由 Mihomo 接管；可见「使用安全 DNS」开关、手动 DoH 模板、真实用户配置、WebRTC srflx 候选、第三方 DNS 泄漏站点仍需负责人在真实浏览器人工确认，不据只读数据宣称通过。
- **DNS 护栏 remove→apply 演练**：按 8 条 CIDR 执行 `dns_guard.py --remove` / `--check` / `--apply` / `--check`，UDP+TCP 各 8 条以 `ipaddress.ip_network` 归一化比对 `normalized_match=true n=8`；短暂无护栏窗口数秒后恢复，最终 `--check` 为 `overall: OK`（详见 [DNS-GUARD.md](DNS-GUARD.md) §5）。
- **NAS 显式代理端到端**：在 192.168.2.2 经 192.168.2.10:7893 显式代理完成连通与出口验证；ENG-04 结论更新为「NAS 端到端通过，HAOS/Proxmox 仍未部署」（详见 [ENG-04-ACCEPTANCE.md](ENG-04-ACCEPTANCE.md)）。
- **dsh-pocket / WorkBuddy UI**：cloudflared 2026.10.7 quick tunnel 注册成功（`https://fibre-presidential-dropped-poetry.trycloudflare.com` 返回 401，属无后端预期）；DSH 沙箱 spawn EPERM 为已知管道边界，非配置问题。WorkBuddy `status` 为 Global 已登录 hs40、credit 1836.23000021；`doctor` 报告 `Host bundle: stale heartbeat (process exited)`，心跳文件 PID 15004 已不存在，需重启 DSH/重载插件后复验 UI，不改动真实认证文件。

---

## 8. 遗留问题（仅剩人工开放项）

1. **真实 LAN 客户端**：未用旁路设备把网关指向 192.168.2.10 做端到端 transparent proxy 验证；平台部署/验收脚本仍只覆盖部署主机与 OpenClash 设备本身。
2. **重启后长期观察**：Windows Verge 与 OpenClash 设备重启后的 TUN / DNS 护栏 / 自动恢复尚未做跨重启长期观察。
3. **浏览器人工项**：可见「使用安全 DNS」开关、手动 DoH 模板、真实用户配置、WebRTC srflx 候选、第三方 DNS 泄漏站点未人工确认；本轮只完成只读策略/netlog 评估，不据其宣称通过。
4. **ENG-04 未部署项**：HAOS 透明代理、Proxmox 默认网关仍未验证；NAS 显式代理端到端已通过（§7.4），ENG-04 不再是全范围“部分通过”。

**本轮已关闭（不再计入遗留问题）**：Q25 Windows 选中节点地区比对（§3.4）、Windows 失败自动回滚 + 六步重部署（§3.5）、OpenClash 受控失败自动回滚 16 项（§4.5）、8 条 CIDR DNS 护栏 `--remove` 演练（§7.4 / DNS-GUARD.md）、NAS 显式代理端到端（§7.4）、dsh-pocket cloudflared 隧道与 WorkBuddy status/UI 复验结论（§7.4）。

**历史已关闭**：PR #17 → `de4d5be`、PR #18 → `3cf7774`、PR #19 → `c680be0` 均已合并；OpenClash 新配置按 m14382 部署并验收通过（§4.4）；DNS fallback `#PROXY` 修复已应用到双平台。

---

## 9. 结论

Windows 与 OpenClash 的部署、配置加载、端口、HTTP、DNS fake-IP 和出口均由当前代码自动验证通过；Q25 节点地区比对（Windows）、双平台失败自动回滚实机演练、DNS 护栏 remove/apply 演练、NAS 显式代理端到端、dsh-pocket/WorkBuddy UI 结论均已在本轮关闭；全量 371 项测试、双平台构建、敏感扫描、`git diff --check` 全部通过。

仍未关闭的仅为人工开放项：真实 LAN 客户端、重启后长期观察、可见浏览器开关/手动 DoH 模板/WebRTC srflx 候选/第三方泄漏站点、HAOS/Proxmox 未部署。OpenClash 侧 Q25 按 Q3 契约降级为「出口非 CN」，不伪造选中节点信息。因此本次结论为：

**自动验收与工程内可自动化项全部通过；完整验收仍留有上述人工开放项，不得据此宣称所有安全与网络目标已最终验收。**
