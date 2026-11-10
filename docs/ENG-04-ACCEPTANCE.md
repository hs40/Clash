# ENG-04 验收报告：双平台完整配置

- 日期：2026-11-10
- 分支：main（本地仓库，未推送远端）
- 环境：Windows，Python 3.12.3，PyYAML 6.0.3，git 2.55.0
- 需求基线：[REQUIREMENTS.md](REQUIREMENTS.md) v1.7
- 结论：**构建期与 Windows 本机 Mihomo v1.19.33 加载验证通过；负责人已确认 OpenClash 设计基准改为设备实际 alpha-gbc76c13（仅 OpenClash），但产物尚未在设备端执行 -t；NAS 端到端未验证，HAOS/Proxmox 尚未部署，因此 ENG-04 不标记全部通过。**

---

## 1. 总览

| 任务 | 状态 | 提交 |
| --- | --- | --- |
| ENG-04 双平台完整配置 | 部分完成（Windows 本机基准通过；OpenClash 基准已改为 alpha，设备端加载未验证） | 本报告所在提交 |

全部自动化测试：**91 项通过，0 失败**（ENG-03 为 91 项，本阶段未新增测试用例，只更新平台端口断言）。

---

## 2. ENG-04 任务报告

1. **任务编号：** ENG-04
2. **完成情况：** 完成 Windows/OpenClash 平台配置对齐、双平台产物本机 Mihomo v1.19.33 加载验证、Clash Verge 覆盖行为核验与需求基线更新；已取得 iStoreOS 实际内核版本，并按负责人确认将其设为 OpenClash 设计基准；设备端加载和真实网络链路仍未完成验证。
3. **修改文件：**
   - 修改 configs/windows/platform.yaml：mixed-port 由 7890 改为负责人确认的 **7897**，并注明 Verge 会覆盖 ipv6/tun、由负责人手动设置；
   - 修改 tests/test_build.py：Windows 端口断言与夹具变更改为 7897/7898；
   - 修改 tests/test_dns.py：DNS 监听端口冲突用例改用 7897；
   - 修改 docs/REQUIREMENTS.md：v1.7，更新 §12/§13.1/§13.2/§14/§15；
   - 修改 README.md：增加 ENG-04 报告链接与当前状态；
   - 新增本报告 docs/ENG-04-ACCEPTANCE.md。
4. **实现内容：**
   - Windows 平台配置与 Clash Verge 实际 mixed-port 对齐为 7897；
   - 保持 Windows TUN、自动路由、dns-hijack: any:53、IPv4-only 配置不变；
   - 保持 OpenClash port: 7893、allow-lan: true、bind-address: "*"，不写入 mixed-port、TUN、redir-port、tproxy-port、iptables、external-controller、secret；
   - 用本机 verge-mihomo.exe v1.19.33 对两份产物执行 -t。
5. **测试命令：**
   .venv\Scripts\python.exe -m unittest discover -s tests -v
6. **测试结果：** Ran 91 tests，OK（本次 5.1 秒）；--platform all 退出码 0；两次构建产物 SHA-256 一致。
7. **需求偏差：** 见第 5 节。
8. **遗留问题：** 见第 6 节。
9. **下一步建议：** 先补齐 OpenClash 设备端 -t（alpha-gbc76c13）与链路核验；未核验项不得写成已验证。

---

## 3. 验收项核对

### 3.1 Windows 配置通过对应 Mihomo 版本验证

本机 Clash Verge Rev 版本：2.5.10；当前核心：verge-mihomo.exe，-v 输出：

    Mihomo Meta v1.19.33 windows amd64 with go1.26.10 Wed Oct 21 16:40:00 UTC 2026
    Use tags: with_gvisor

对 dist/windows/config.yaml 执行：

    & "C:/Program Files/Clash Verge/verge-mihomo.exe" -t -f "dist/windows/config.yaml" -d ".tmp_mihomo_test"

结果：退出码 **0**，日志末行 configuration file ... test is successful。
**通过（本机加载验证）。**

### 3.2 OpenClash 配置通过对应 Mihomo 版本验证

本机 v1.19.33 对 dist/openclash/config.yaml 执行 -t：退出码 **0**，
日志末行 configuration file ... test is successful；产物不含 Windows TUN 键。
这只能说明产物能被 v1.19.33 解析，不能代表设备 alpha 基准。

iStoreOS 设备实际内核（负责人 2026-11-10 只读输出）：

| 项 | 结果 |
| --- | --- |
| 路径 | /etc/openclash/core/clash_meta |
| 大小 | 16021484 字节 |
| 版本 | Mihomo Meta alpha-gbc76c13 linux amd64 with go1.26.9 Mon Oct 12 03:44:17 UTC 2026 |
| tags | with_gvisor |
| 包管理 | opkg 不存在，无法用包版本核对 |
| meta-backup | 目录，不是可执行文件；Permission denied 属预期 |

**负责人 2026-11-10 确认：OpenClash 设计基准改为设备实际 alpha-gbc76c13（仅 OpenClash）。**
Windows 仍为 v1.19.33。设备端 -t 尚未执行，因此“对应 Mihomo 版本验证”**未完成**；
按约束，不擅自替换 iStoreOS 内核，也不把该项写成已通过。

补充只读探测结果：

| 目标 | 结果 |
| --- | --- |
| 192.168.2.10:22/80/443 | 开放（Dropbear / LuCI） |
| 192.168.2.10:7890/7891/7892/7893/9090 | 开放 |
| http://192.168.2.10/cgi-bin/luci/ | 403（需要登录） |
| http://192.168.2.10:9090/version | 401（需要 API secret） |
| http://192.168.2.10:7893 | 407（需要代理认证） |

这些结果只能证明服务在监听并启用了访问控制，不能证明代理链路可用。

### 3.3 平台专属配置未错误合并

tests/test_build.py 的键集合断言仍然通过：

- Windows 产物键：mode, log-level, ipv6, mixed-port, allow-lan, tun, dns, proxies, proxy-groups, rules；
- OpenClash 产物键：mode, log-level, ipv6, port, allow-lan, bind-address, dns, proxies, proxy-groups, rules；
- OpenClash 产物无 mixed-port、无 tun；Windows 产物无 port、无 bind-address。

**通过。**

### 3.4 NAS 显式代理路径

配置层已满足：OpenClash 使用 HTTP port: 7893，不是 mixed-port；allow-lan: true。
NAS 侧探测到 192.168.2.2:5000/5001 开放，但未读取 NAS 的代理设置；
从开发机访问 192.168.2.10:7893 返回 **407**，说明代理认证已启用，
无凭据不能完成真实代理请求。**配置契约通过；端到端未验证。**

### 3.5 HAOS 透明代理路径与 Proxmox 默认网关

- 负责人 2026-11-10 说明：**HAOS、Proxmox 尚未部署**。
- 因此无法在设备上验证 HAOS 静态 IP、默认网关 192.168.2.10、DNS 链路，也无法确认 Proxmox 当前默认网关是否仍为 192.168.2.1。
- 两项均标记为**未部署/未验证**，不得写成已通过；待设备部署后再核验。

### 3.6 Clash Verge 覆盖行为（本机实测）

本机 Clash Verge 生成的 %APPDATA%/io.github.clash-verge-rev.clash-verge-rev/config.yaml 为：

| 键 | 实际值 | 仓库 Windows 平台配置 |
| --- | --- | --- |
| mixed-port | 7897 | 7897（本次对齐） |
| ipv6 | true | 公共配置 false |
| tun.enable | false | true |
| tun.stack | mips | gvisor |

结论：**Verge 会覆盖 mixed-port / ipv6 / tun**。负责人 2026-11-10 决定：
仓库 mixed-port 取 7897；IPv6 关闭与 TUN 启用由负责人在 Verge GUI 手动完成。
开发 Agent 未修改本机 Verge 配置。

### 3.7 OpenClash LAN 限制决策

实测 OpenClash 7893 返回 407（代理认证），9090 返回 401（API secret）。
Mihomo v1.19.33 二进制包含 lan-allowed-ips/lan-disallowed-ips；临时配置同时加入
lan-allowed-ips: [192.168.2.0/24] 与 lan-disallowed-ips: 0.0.0.0/0 后 -t 通过；
但负责人决定**保持现状**：
只使用 allow-lan: true + bind-address: "*"，不加入网段白名单。
本阶段不修改该安全策略。

---

## 4. 产物核对

| 产物 | 字节 | SHA-256（前 16 位） | 策略组数 | 规则数 |
| --- | --- | --- | --- | --- |
| dist/windows/config.yaml | 4127 | 5d5af88581be3282 | 13 | 24 |
| dist/openclash/config.yaml | 4006 | 6d959695f66279a8 | 13 | 24 |

Windows 产物因 mixed-port 改为 7897 而哈希变化；OpenClash 产物未变。

---

## 5. 需求偏差与负责人决策

| 项 | 处理 | 依据 |
| --- | --- | --- |
| Windows mixed-port 由 7890 改为 7897 | 已修改平台配置与测试断言 | 负责人 2026-11-10 决策；与本机 Verge 实际值一致 |
| Verge 覆盖 IPv6/TUN | 仓库不修改真实 Verge 配置，由负责人手动设置 | 负责人 2026-11-10 决策；工作区外只读约束 |
| OpenClash LAN 限制保持现状 | 不加 lan-allowed-ips | 负责人 2026-11-10 决策 |
| OpenClash 设计基准改为设备实际 alpha-gbc76c13 | 已更新需求基线；仅 OpenClash，Windows 保持 v1.19.33；设备端 -t 待执行 | 负责人 2026-11-10 决策 |
| HAOS、Proxmox 尚未部署 | 标记未部署，待部署后验证 | 负责人 2026-11-10 说明 |
| 未修改 NAS/HAOS/Proxmox | 仅验证配置契约与只读网络端口 | 不修改用户真实设备 |

---

## 6. 遗留问题

1. OpenClash 设计基准已改为 alpha-gbc76c13；设备端 -t 仍未执行，不能证明产物在该内核可用。
2. OpenClash 7893 的代理认证凭据未提供，NAS 显式代理端到端请求未验证。
3. HAOS、Proxmox 尚未部署，无法验证 HAOS 网关/DNS 链路与 Proxmox 默认网关是否保持不变。
4. 本机 Clash Verge 当前实际运行的是既有 FIB 配置（55 节点、14 组、1130 规则），不是本仓库产物；本报告只验证产物可被 v1.19.33 内核加载，不验证其已在本机生效。
5. TUN 的真实路由接管、DNS 泄漏、IPv6 绕过未验证；-t 只证明配置可解析/初始化。
