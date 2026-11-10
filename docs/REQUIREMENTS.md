# 需求基线（REQUIREMENTS）

**版本：** v1.1
**来源：** 《Clash 配置工程开发 Plan》v1.0 第二章、第三章，以及项目负责人 2026-11-10 的确认记录
**地位：** 本文件是配置、脚本与测试的唯一需求基线。修改必须经项目负责人确认，
并在文末「变更记录」中留痕。开发 Agent 不得自行扩大、缩减或改变本文件的范围。

标注约定：

- **【确定】** 已确认，可以直接实现。
- **【草案】** 为通过 MVP 而采用的临时取值，**必须在真实设备上核验后才算确定**。
- **【待核验】** 尚未验证的假设，不得在任何报告或文档中写成已验证事实。

---

## 1. 目标与非目标

**目标：** 用一套公共配置生成 Windows 与 OpenClash 两份完整 Mihomo 配置，
做到可校验、可重复构建、可持续维护。

**非目标：** 独立 GUI、后台服务、通用代理管理平台、自动修改用户设备、
GitHub 以外的灾难恢复备份系统。

---

## 2. 平台基线【确定】

| 项目 | Windows | OpenClash |
| --- | --- | --- |
| 客户端 | Clash Verge Rev v2.5.10 | iStoreOS + OpenClash |
| 内核 | Mihomo Meta | Mihomo Meta |
| 配置模式 | Rule | Rule |
| 代理方式 | TUN | 旁路由透明代理 |
| DNS | Fake-IP | Fake-IP |
| 网络协议 | IPv4-only | IPv4-only |
| 兼容基准 | Mihomo v1.19.33 | Mihomo v1.19.33 |

**注意：** Mihomo v1.19.33 是工程设计与测试基准，**不代表设备上已经运行该版本**。
实际部署前必须核对内核版本与 OpenClash 兼容性。【待核验】

---

## 3. 网络环境【确定】

| 设备 | 地址或配置 | 说明 |
| --- | --- | --- |
| 主路由 | 192.168.2.1 | 保持主路由和 DHCP 功能 |
| NAS | 192.168.2.2 | 使用 HTTP 显式代理 |
| iStoreOS 旁路由 | 192.168.2.10 | OpenClash 运行环境 |
| NAS 代理地址 | 192.168.2.10:7893 | HTTP 代理端口 |

具体要求：

1. NAS 默认网关保持 `192.168.2.1`。
2. NAS 使用 `192.168.2.10:7893` 作为 HTTP 显式代理。
3. OpenClash 的 `7893` 使用 HTTP `port`，**不是** `mixed-port`。
4. HTTP 代理只允许 LAN 内授权设备访问，不能暴露到 WAN。
5. HAOS 使用静态 IP，默认网关指向 `192.168.2.10`。
6. HAOS DNS 通过 iStoreOS / OpenClash DNS 链路。
7. Proxmox 宿主机默认网关保持主路由。
8. Proxmox 虚拟机根据需要选择主路由或旁路由作为默认网关。
9. 不启用 IPv6。

---

## 4. 节点与策略组

1. 识别节点名称中的中文地区信息。【确定】
2. 至少支持香港、日本、美国、韩国等地区。【确定】
3. 节点识别结果定期更新，并保留本地缓存。【确定】
4. 提供全局代理策略组。【确定】
5. 全局代理策略组包含自动选择和七个地区入口。【确定】
6. 不要求所有节点都能逐个手动选择。【确定】
7. Google 服务优先使用美国节点。【确定】
8. 美国节点不可用时，允许回退至指定地区白名单内的其他节点。【确定；白名单名单本身尚未确定】
9. Google 地区选择遵循用户选择的策略组。【确定】

### 4.1 七个地区入口【确定，2026-11-10 负责人确认】

| # | 入口名称 | 说明 |
| --- | --- | --- |
| 1 | 香港节点 | |
| 2 | 台湾节点 | |
| 3 | 日本节点 | |
| 4 | 韩国节点 | |
| 5 | 狮城节点 | 狮城即新加坡；识别时「新加坡」作为同义词 |
| 6 | 美国节点 | Google 美国优先依赖此入口 |
| 7 | 其他节点 | 未匹配到上述地区的节点 |

七个入口的**完整名称如上**，不得改写或增删；地区识别关键词表与成员规则属 ENG-01 范围。

`其他节点` 的语义【确定，2026-11-10 负责人确认】：**未匹配地区的兜底节点池**——名称未命中任何地区关键词的节点归入此组。它不是其他地区组的回退目标，地区组只包含本地区节点。ENG-01 据此实现关键词表与成员归属。

---

## 5. 分流规则【确定】

统一采用四层结构：

1. 特殊规则：最高优先级。
2. 业务规则。
3. 基础规则。
4. 兜底规则：最低优先级，`MATCH` 必须最后。

层内按数字优先级排序，数字越小越靠前；同层重复优先级禁止；保留规则模块内部顺序。
必须测试特殊规则、业务规则和基础规则之间的冲突，确认最终命中策略。

---

## 6. 关键业务【确定】

只纳入以下五类，不得自行扩大：

- AI 服务
- Google 服务
- Apple 服务
- 国内金融服务
- BT

---

## 7. DNS 与网络要求

1. Windows 使用 TUN 接管流量。【确定】
2. OpenClash 使用旁路由透明代理。【确定】
3. 两端使用 Fake-IP。【确定】
4. 统一 IPv4-only。【确定】
5. 统一管理 Fake-IP Filter。【确定】
6. 国内外 DNS 分流。【确定】
7. 节点域名使用适当的独立解析路径。【确定】
8. 避免 DNS 循环、DNS 泄漏和明显绕过代理。【确定】
9. 局域网地址直连。【确定】
10. 不将 Windows TUN 配置直接复制到 OpenClash。【确定】
11. Fake-IP-Mix 可作为 OpenClash 设计起点，但必须按实际 OpenClash 版本做兼容性验证。【待核验】

---

## 8. Provider 管理【确定】

1. 通用规则集采用可信远程来源。
2. 特殊业务规则和自定义规则保存在自己的仓库。
3. 远程来源使用固定白名单。
4. Provider 版本和 SHA-256 锁定。
5. 每周检查上游更新。
6. 自动创建专用更新分支和 PR，不直接修改 `main`。
7. 自定义业务规则不能被上游覆盖。
8. 新来源、来源域名、仓库、下载地址或维护主体变化必须人工审批。
9. 高风险更新必须人工审批，不自动切换未经批准的来源。
10. 保留最近五个已验证版本；当前正式使用版本不能因超出数量而被删除。

---

## 9. 自动化与安全【确定】

1. 使用 Python 作为配置构建和测试工具。
2. 使用 GitHub Actions 执行 CI。
3. Actions 默认最小权限。
4. 第三方 Actions 固定完整 Commit SHA。
5. 不可信 PR 不暴露 Secrets。
6. 不提交订阅链接、节点密码、Token、API Key 等敏感信息。
7. Python 依赖精确锁定版本和哈希。
8. Mihomo 测试二进制固定版本和 SHA-256。
9. 核心脚本、安全策略、业务基线和工作流受 CODEOWNERS 保护。
10. 高风险问题阻止正式发布，只有项目负责人可以解除发布阻断。
11. 自动化测试不能代替真实网络连通性和 DNS 泄漏测试。

---

## 10. 发布与回滚【确定】

1. `main` 分支有效合并且 CI 通过后，自动创建 GitHub Release。
2. 使用 SemVer。
3. 发布 Windows 和 OpenClash 两份独立配置包。
4. 包含 `SHA256SUMS`、中文 Release Notes 和配置差异报告。
5. 不在发布包中包含订阅、凭据或其他敏感信息。
6. Windows 和 OpenClash 可以独立回滚。
7. 回滚由用户手动执行，不自动修改设备。
8. 不建设 GitHub 以外的灾难恢复备份系统。

---

## 11. 公共配置与平台配置的边界【确定，MVP 实现契约】

`configs/<platform>/platform.yaml` 是一段 **Mihomo 顶层配置片段**，顶层键直接对应
最终配置的顶层键。构建时做**顶层浅合并**，不做递归深合并，每个顶层键只有一个所有者。

| 归属 | 顶层键 | 说明 |
| --- | --- | --- |
| 公共独占 | `proxies`、`proxy-groups`、`rules`、`dns` | 由 `configs/common/` 提供 |
| 公共独占（标量） | `mode`、`log-level`、`ipv6` | 由 `configs/common/` 提供 |
| Windows 独占 | `mixed-port`、`allow-lan`、`tun` | 只允许出现在 `configs/windows/platform.yaml` |
| OpenClash 独占 | `port`、`allow-lan`、`bind-address` | 只允许出现在 `configs/openclash/platform.yaml` |

约束：

1. 白名单之外的顶层键 → 构建失败，并报告文件名与键名。
2. 同一顶层键同时出现在公共配置与平台配置 → 构建失败；**不做**「平台覆盖公共」的隐式优先级。
3. MVP 不实现覆盖机制；将来确需覆盖时，必须显式设计并更新本文件。
4. OpenClash 运行时会自行注入的键（`redir-port`、`tproxy-port`、iptables 相关、
   `external-controller`、`secret`）**不写入**平台配置。
5. 相同输入必须产生字节一致的输出：固定键顺序、无时间戳、UTF-8 无 BOM。

---

## 12. MVP 阶段实现边界【确定】

必须实现：仓库目录、需求基线、公共配置、Windows 平台配置、OpenClash 平台配置、
Python 最小构建程序、YAML 基础校验、两份配置生成结果、基础自动化测试。

暂不实现：自动节点地区识别、自动策略组生成、完整四层规则系统、Provider 自动更新、
完整 DNS/Fake-IP 测试体系、Mihomo 多版本兼容测试、完整安全扫描体系、自动 Release、
自动设备部署、OpenClash 防火墙自动部署。

---

## 13. MVP 草案参数【草案，2026-11-10 负责人同意作为起点，部署前必须核验】

### 13.1 Windows（Clash Verge Rev v2.5.10）

| 键 | 草案值 | 说明 |
| --- | --- | --- |
| `mixed-port` | `7890` | Verge 可能用自己的 GUI 设置覆盖，【待核验】 |
| `allow-lan` | `false` | |
| `tun.enable` | `true` | |
| `tun.stack` | `gvisor` | 用户态栈，Windows 兼容性优先，【待核验】 |
| `tun.auto-route` | `true` | |
| `tun.auto-detect-interface` | `true` | |
| `tun.dns-hijack` | `["any:53"]` | |
| `tun.strict-route` | `false` | |

### 13.2 OpenClash（iStoreOS 旁路由）

| 键 | 草案值 | 说明 |
| --- | --- | --- |
| `port` | `7893` | HTTP 代理端口，NAS 显式代理依赖此值【确定】 |
| `allow-lan` | `true` | |
| `bind-address` | `"*"` | |
| LAN 访问限制 | 仅 `allow-lan` + `bind-address` | `lan-allowed-ips` 与防火墙规则属 ENG-03/04，【待核验】 |

### 13.3 DNS

| 键 | 草案值 | 说明 |
| --- | --- | --- |
| `dns.enable` | `true` | |
| `dns.listen` | `0.0.0.0:1053` | 与 Windows TUN `dns-hijack` 的配合【待核验】；OpenClash 可能用自己的监听端口 |
| `dns.ipv6` | `false` | |
| `dns.enhanced-mode` | `fake-ip` | |
| `dns.fake-ip-range` | `198.18.0.1/16` | |
| `dns.default-nameserver` | `223.5.5.5`、`119.29.29.29` | |
| `dns.nameserver` | `https://dns.alidns.com/dns-query`、`https://doh.pub/dns-query` | 国内 |
| `dns.proxy-server-nameserver` | `https://doh.pub/dns-query`、`https://dns.alidns.com/dns-query` | 节点域名独立解析路径 |
| `dns.fallback` | `https://1.1.1.1/dns-query`、`https://dns.google/dns-query` | 国外 |
| `dns.fallback-filter` | `{geoip: true, geoip-code: CN}` | |

### 13.4 占位节点

MVP 的 `configs/common/proxies.yaml` 使用占位节点：`type: ss`、
`server: 192.0.2.x`（TEST-NET-1，永不指向真实主机）、`port: 443`、
`cipher: aes-128-gcm`、`password: PLACEHOLDER-NOT-REAL`、`udp: false`，
并在文件头注明「占位节点，禁止部署」。占位内容不得被描述为真实节点。

---

## 14. 待核验清单【待核验】

1. 设备上实际的 Mihomo 版本是否为 v1.19.33，以及与 OpenClash 的兼容性。
2. Clash Verge Rev v2.5.10 是否会覆盖 `platform.yaml` 中的 `mixed-port` / `tun` 设置。
3. OpenClash 是否自行注入 `redir-port` / `tproxy-port` 与 DNS 监听（如 7874）。
4. `dns.listen: 0.0.0.0:1053` 与 TUN `dns-hijack` 的实际配合方式。
5. Mihomo v1.19.33 是否支持 `lan-allowed-ips`（决定 OpenClash LAN 限制的实现方式）。
6. 真实网络连通性、DNS 泄漏与绕过代理路径（自动化测试不能替代）。
7. Google 回退的「指定地区白名单」具体地区。

---

## 15. 变更记录

| 日期 | 版本 | 变更 | 确认人 |
| --- | --- | --- | --- |
| 2026-11-09 | v1.0-draft | 从 Plan v1.0 提取需求基线 | — |
| 2026-11-10 | v1.0 | 确认七个地区入口名称；确认 MVP 草案参数与合并契约 | 项目负责人 |
| 2026-11-10 | v1.1 | 追认新增公共文件 `configs/common/general.yaml`；确认 `其他节点` 为未匹配地区的兜底节点池 | 项目负责人 |
