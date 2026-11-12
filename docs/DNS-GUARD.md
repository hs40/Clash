# Windows DNS 泄漏护栏（C 决策）

状态：代码与测试已按 2026-11-12 负责人 A 决策更新为「阻断 `192.168.2.0/24`、放行 `192.168.2.10:53`」，
但**新地址规则尚未在本机管理员上下文重新应用**；当前实际生效的仍是旧的 `192.168.2.0/24` 全阻断规则。
旧规则已通过 DNS 路径、站点回归与管理员 `check`，并完成一次 `--remove` 回滚演练。
本机 DSH 进程为 Low Integrity，不能在 DSH 内直接读取或写入防火墙。

## 1. 背景与决策

2026-11-12 负责人选择 **C**：阻断本机到 `192.168.2.0/24` 的 53 端口出站，
保留 Mihomo TUN DNS `198.18.0.2`。

原因：本机默认解析路径返回 fake-IP，但显式查询路由器 DNS
`192.168.2.1:53` 会绕过 TUN，返回真实地址。该路径会让 ISP/路由器看到 DNS
查询内容，不满足“全网级 DNS 不泄漏”的验收目标。

2026-11-12 负责人进一步选择 **A**：在 OpenClash 验收需要 Windows 查询 `192.168.2.10:53` 返回 fake-IP 的约束下，护栏放行受控解析器 `192.168.2.10:53`，继续阻断路由器与其他 LAN 地址的 53 端口。`192.168.2.10` 是已确认的 iStoreOS/OpenClash 设备。

此决策覆盖此前“Windows 部署不改防火墙”的默认边界；只新增两条**出站阻断**
规则，不改系统 DNS、hosts、路由、代理设置或任何入站规则。

## 2. 规则契约

| 项目 | 值 |
| --- | --- |
| 组 | `Clash DNS Guard` |
| 显示名 | `Clash DNS Guard - Block LAN DNS (UDP)` / `(TCP)` |
| 方向 | Outbound |
| 动作 | Block |
| 协议 | UDP、TCP |
| 远程地址 | `192.168.2.0/29`、`192.168.2.8/31`、`192.168.2.11/32`、`192.168.2.12/30`、`192.168.2.16/28`、`192.168.2.32/27`、`192.168.2.64/26`、`192.168.2.128/25`（`.10` 放行） |
| 远程端口 | 53 |
| 配置文件 | Any |
| 启用 | True |

脚本只增删上述两条规则；按显示名精确识别，不触碰其他防火墙规则。
上述地址集合等价于 `192.168.2.0/24` 排除 `192.168.2.10/32`；Windows 可能把 CIDR 规范化为点分掩码；
`--check` 同时接受 CIDR 与点分掩码，但要求解析后的地址集合精确等于上述 8 条，旧的 `/24` 全阻断判为不合格。

## 3. 使用

只读检查（不会修改防火墙）：

    dns-guard.cmd check

若返回退出码 2（无法读取防火墙配置），请以管理员身份运行同一命令；
`check` 不会自提权。

管理员应用（会自提权；也可右键“以管理员身份运行”）：

    dns-guard.cmd

移除并回滚：

    dns-guard.cmd remove

直接调用 Python（需管理员）：

    .venv\Scripts\python.exe scripts\dns_guard.py --check
    .venv\Scripts\python.exe scripts\dns_guard.py --apply
    .venv\Scripts\python.exe scripts\dns_guard.py --remove

`dns-guard.cmd` 会优先从 `.venv\pyvenv.cfg` 的 `home` 读取基础解释器，
避免 `.venv\Scripts\python.exe` 启动器在管理员窗口中可能未保持高完整性的问题；
`dns_guard.py` 只使用标准库，因此不依赖 venv 中的第三方包。

`--check` 只读；`--apply` 幂等，已存在的正确规则会跳过；`--remove` 只删除
两条具名规则。应用失败时脚本会尝试删除本次已创建的规则。
`--check` 在无法读取防火墙配置时返回退出码 2 并显示原因，不会把“无权限”误报为“规则缺失”。

## 4. 验收

### 4.1 旧策略（`192.168.2.0/24` 全阻断）应用记录

以下为 A 决策前的历史证据；当前生效规则仍是该旧规则，已被新地址集合取代，待重新应用。

管理员上下文（`High Mandatory Level S-1-16-12288`）使用基础解释器
`D:\Programs\Python\python.exe` 调用 `dns_guard.apply()`，返回：

    APPLY_OK {"created": ["UDP", "TCP"], "skipped": []}

实际规则（Windows 规范化后的值）：

| 协议 | 显示名 | 方向/动作 | 远程地址 | 远程端口 | 配置文件 | 启用 |
| --- | --- | --- | --- | --- | --- | --- |
| UDP | `Clash DNS Guard - Block LAN DNS (UDP)` | Outbound / Block | `192.168.2.0/255.255.255.0` | 53 | Any | True |
| TCP | `Clash DNS Guard - Block LAN DNS (TCP)` | Outbound / Block | `192.168.2.0/255.255.255.0` | 53 | Any | True |

### 4.2 已完成的验证

1. `192.168.2.1:53` UDP 查询 -> `TimeoutError`（被阻断）。
2. `198.18.0.2:53` -> 45 字节响应，A 记录 `198.18.0.85`（fake-IP）。
3. `223.5.5.5:53` -> 45 字节响应，A 记录 `198.18.0.85`（被 TUN 劫持）。
4. 站点回归：百度 200 / 0.22s；gstatic 204 / 2.61s；Google 200 / 11.09s；YouTube 200 / 5.25s。

### 4.3 管理员 check（2026-11-12 17:21）

在管理员 PowerShell 中执行：

    cd "F:\WorkBuddy AI\Clash"
    .\dns-guard.cmd check *> .tmp_dns_check.txt

输出：

    UDP: OK
    TCP: OK
    overall: OK
    Exit code: 0

`dns-guard.cmd` 已优先使用 `pyvenv.cfg` 中的基础解释器，管理员窗口不再返回拒绝访问。

### 4.4 回滚演练（2026-11-12 17:48）

在负责人确认的维护窗口、管理员上下文中执行。演练会短暂恢复
`192.168.2.1:53` 泄漏路径，演练脚本在 `finally` 中重新应用规则。

| 阶段 | 规则状态 | `192.168.2.1:53` | `198.18.0.2:53` | 站点 |
| --- | --- | --- | --- | --- |
| 移除前 | UDP/TCP OK | 超时 | fake-IP `198.18.0.85` | 百度 200、gstatic 204 |
| `--remove` 后 | `[]`，`--check` 退出 1 | 返回真实地址 `172.66.147.243`（泄漏恢复） | fake-IP `198.18.0.85` | 百度 200、gstatic 204 |
| `--apply` 后 | 重新创建 UDP/TCP，`--check` 退出 0 | 超时 | fake-IP `198.18.0.85` | 百度 200、gstatic 204 |

时间线：开始 17:48:01，结束 17:48:27；泄漏窗口约 26 秒。演练结束后再次从普通
DSH 进程复核：`192.168.2.1:53` 超时，`198.18.0.2:53` 与 `223.5.5.5:53`
返回 fake-IP，百度 200、gstatic 204。结论：移除与恢复均按预期工作，规则已恢复。

验收记录同步写入 [VERGE-GLOBAL.md](VERGE-GLOBAL.md) §6.2。

### 4.5 新策略（放行 `.10`）待应用

2026-11-12 代码与 11 项测试已完成，生成脚本已通过 PowerShell 解析（`PARSE_OK`），但尚未以管理员写入。重新应用后应满足：

1. `dns-guard.cmd check` 退出 0，UDP/TCP 远程地址为上述 8 条 CIDR（或等价点分掩码）。
2. `192.168.2.10:53` 返回 fake-IP。
3. `192.168.2.1:53` 超时，`223.5.5.5:53` 被 TUN 劫持返回 fake-IP。
4. 站点回归通过。

在上述实测完成前，不得宣称新护栏已生效。

## 5. 回滚

    dns-guard.cmd remove

该命令只删除两条 `Clash DNS Guard` 规则。回滚后如需恢复完整防火墙策略，
使用应用前的策略导出文件（如果已创建）；本脚本不修改其他规则。

2026-11-12 17:48 已按 §4.4 完成一次移除/恢复演练：移除后路由器 DNS 恢复可达，
重新执行 `dns-guard.cmd apply` 后阻断与 fake-IP 均恢复。

2026-11-12 A 决策后的新地址集合要求重新执行 `dns-guard.cmd`（或 `--apply`）替换旧规则；该步骤尚未执行。

## 6. 限制

- 只覆盖 IPv4 与 `192.168.2.0/24`（放行 `192.168.2.10`）；若未来新增其他受控 LAN DNS 地址，需要扩展。
- **只在 Mihomo TUN 已接管、默认 DNS 为 `198.18.0.2` 时使用**；TUN 关闭或 Mihomo 停止时，
  本机会失去 DNS，应先执行 `dns-guard.cmd remove`。
- 不阻断 DoH/DoT；浏览器自带 DoH 仍可能绕过系统 DNS，需在浏览器层单独验收。
- 需要管理员权限。若企业策略或安全软件锁定防火墙，`New-NetFirewallRule` 会
  返回拒绝访问；此时不得绕过策略，应改用手工防火墙配置或回到方案 A/B。
- 本机 DSH 进程本身为 Low Integrity（`S-1-16-4096`），普通 DSH 进程不能读写防火墙；
  管理员操作必须在 DSH 之外的桌面管理员会话执行。本次应用通过 DSH 的
  `danger-full-access` 审批在 High 上下文完成，不能用普通 DSH 终端重复。
- `.venv\Scripts\python.exe` 在本机是 `py.exe` 启动器（274,712 B，OriginalFilename `py.exe`），
  在管理员窗口可能未保持高完整性；`dns-guard.cmd` 已改为优先使用 `pyvenv.cfg` 中的基础解释器。
- 本脚本不改 Verge 配置，也不进入 `dist/` 或 GitHub Release。

## 7. 测试

    .venv\Scripts\python.exe -m unittest discover -s tests -p test_dns_guard.py -v

覆盖：规则规格、协议校验、空状态、runner 错误传播、创建 UDP/TCP、已存在时跳过、
删除两条规则、新 CIDR 集合、拒绝旧 `/24`、Windows 返回点分掩码时的匹配（共 11 项）。
防火墙实际写入由管理员在真实 Windows 上验收；CI 不执行该系统变更。
