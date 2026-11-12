# Windows DNS 泄漏护栏（C 决策）

状态：代码与测试已加入；**尚未在本机应用**（当前 DSH 进程为 Low Integrity，
Windows 防火墙 WMI 返回“拒绝访问”）。需要负责人在桌面以管理员权限运行
`dns-guard.cmd`，应用后再做验收。

## 1. 背景与决策

2026-11-12 负责人选择 **C**：阻断本机到 `192.168.2.0/24` 的 53 端口出站，
保留 Mihomo TUN DNS `198.18.0.2`。

原因：本机默认解析路径返回 fake-IP，但显式查询路由器 DNS
`192.168.2.1:53` 会绕过 TUN，返回真实地址。该路径会让 ISP/路由器看到 DNS
查询内容，不满足“全网级 DNS 不泄漏”的验收目标。

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
| 远程地址 | `192.168.2.0/24` |
| 远程端口 | 53 |
| 配置文件 | Any |
| 启用 | True |

脚本只增删上述两条规则；按显示名精确识别，不触碰其他防火墙规则。

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

`--check` 只读；`--apply` 幂等，已存在的正确规则会跳过；`--remove` 只删除
两条具名规则。应用失败时脚本会尝试删除本次已创建的规则。
`--check` 在无法读取防火墙配置时返回退出码 2 并显示原因，不会把“无权限”误报为“规则缺失”。

## 4. 验收

应用后依次检查：

1. `dns-guard.cmd check` 显示 UDP/TCP 均为 `OK`。
2. 默认解析仍返回 fake-IP，例如 `nslookup www.google.com` -> `198.18.0.x`。
3. 显式查询 `192.168.2.1:53` 应超时（被阻断），不再返回真实地址。
4. `223.5.5.5:53` 仍被 TUN 劫持为 fake-IP。
5. 回归：百度、gstatic 204、Google、YouTube 均可访问。
6. 移除规则后，`--check` 显示缺失，路由器 DNS 恢复可解析。

验收记录写入 [VERGE-GLOBAL.md](VERGE-GLOBAL.md) §6。

## 5. 回滚

    dns-guard.cmd remove

该命令只删除两条 `Clash DNS Guard` 规则。回滚后如需恢复完整防火墙策略，
使用应用前的策略导出文件（如果已创建）；本脚本不修改其他规则。

## 6. 限制

- 只覆盖 IPv4 和 `192.168.2.0/24`；若未来新增其他 LAN DNS 地址，需要扩展。
- **只在 Mihomo TUN 已接管、默认 DNS 为 `198.18.0.2` 时使用**；TUN 关闭或 Mihomo 停止时，
  本机会失去 DNS，应先执行 `dns-guard.cmd remove`。
- 不阻断 DoH/DoT；浏览器自带 DoH 仍可能绕过系统 DNS，需在浏览器层单独验收。
- 需要管理员权限。若企业策略或安全软件锁定防火墙，`New-NetFirewallRule` 会
  返回拒绝访问；此时不得绕过策略，应改用手工防火墙配置或回到方案 A/B。
- 当前 DSH 进程为 Low Integrity（`S-1-16-4096`），即使 `Start-Process -Verb RunAs`
  也继承低完整性，无法写防火墙；必须在 DSH 之外的桌面管理员会话执行。
- 本脚本不改 Verge 配置，也不进入 `dist/` 或 GitHub Release。

## 7. 测试

    .venv\Scripts\python.exe -m unittest discover -s tests -p test_dns_guard.py -v

覆盖：规则规格、协议校验、空状态、runner 错误传播、创建 UDP/TCP、已存在时跳过、删除两条规则。
防火墙实际写入由管理员在真实 Windows 上验收；CI 不执行该系统变更。
