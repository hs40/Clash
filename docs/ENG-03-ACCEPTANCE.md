# ENG-03 验收报告：DNS、Fake-IP 与 IPv4-only

- 日期：2026-11-10
- 分支：`main`（本地仓库，未推送远端）
- 环境：Windows，Python 3.12.3，PyYAML 6.0.3，git 2.55.0
- 需求基线：[REQUIREMENTS.md](REQUIREMENTS.md) v1.4
- 结论：**ENG-03 的构建期静态验收项通过**；DNS 泄漏与 OpenClash 运行时适配
  未在真实网络/设备上验证，本报告不将其写成已验证事实。

---

## 1. 总览

| 任务 | 状态 | 提交 |
| --- | --- | --- |
| ENG-03 DNS、Fake-IP 与 IPv4-only | 已完成（静态校验） | 本报告所在提交 |

全部自动化测试：**91 项通过，0 失败**（ENG-02 为 63 项，本阶段新增 28 项）。

---

## 2. ENG-03 任务报告

1. **任务编号：** ENG-03
2. **完成情况：** 已完成构建期 DNS 校验与双平台 DNS 一致性验证；运行时兼容性待核验。
3. **修改文件：**
   - 修改 `scripts/build.py`：新增 `DNS_REQUIRED_KEYS`、`DNS_SERVER_KEYS`、
     `_dns_error`、`_validate_dns_list`、`_parse_dns_listen`、
     `_is_dns_self_reference`、`validate_dns`，并在 `build_platform` 中接入
     DNS、顶层 IPv4、端口冲突与 Windows `dns-hijack` 校验；
   - 新增 `tests/test_dns.py`（28 项）；
   - 修改 `configs/common/dns.yaml` 文件头注释（取值未变）；
   - 修改 `docs/REQUIREMENTS.md`（v1.4，新增 §7.1，更新 §12/§13.3/§14/§15）；
   - 修改 `README.md`（测试覆盖、ENG-03 链接与状态）；
   - 新增本报告 `docs/ENG-03-ACCEPTANCE.md`。
4. **实现内容：**
   - `validate_dns(dns)` 纯函数校验 11 个必填键、Fake-IP 模式、IPv4-only、
     `listen` 地址与端口、`fake-ip-range` 前缀、Filter 列表、四类 DNS 服务器列表、
     `nameserver`/`fallback` 交集、自指转发循环与 `fallback-filter`。
   - `build_platform` 在策略组展开前校验顶层 `ipv6: false`、`dns.listen` 与
     `mixed-port`/`port` 的端口冲突；Windows 要求 `tun.dns-hijack` 含 `any:53`。
   - 校验失败统一抛出 `ConfigError`，CLI 退出码 2；错误信息带 `dns：` 或键名前缀。
5. **测试命令：**
   `.venv\Scripts\python.exe -m unittest discover -s tests -v`
6. **测试结果：** `Ran 91 tests`，`OK`（约 4-5 秒）；`--platform all` 退出码 0，
   两次构建产物 SHA-256 一致。
7. **需求偏差：** 见第 5 节。
8. **遗留问题：** 见第 6 节。
9. **下一步建议：** 进入 ENG-04（双平台完整配置与平台差异）；先确认平台独占键与
   OpenClash 运行时注入边界，再实现。

---

## 3. 验收项核对

### 3.1 Fake-IP 基线

产物中两份配置的 `dns` 完全相同：`enable: true`、`enhanced-mode: fake-ip`、
`fake-ip-range: 198.18.0.1/16`、`dns.ipv6: false`。`fake-ip-filter` 固定为
`*.lan`、`*.local`、`+.msftconnecttest.com`、`+.msftncsi.com` 4 条。
`tests/test_dns.py::ProductionDnsTest` 逐项断言。**通过。**

### 3.2 IPv4-only

顶层 `ipv6` 为 false，`dns.ipv6` 为 false，`default-nameserver` 不含冒号，
`fake-ip-range` 为 IPv4 网段。构建器拒绝顶层 `ipv6: true` 与 `dns.ipv6: true`。
**通过。**

### 3.3 国内外 DNS 分流与节点域名解析路径

`nameserver` 固定为阿里 DoH 与腾讯 DoH；`fallback` 固定为 Cloudflare 与 Google DoH；
两者无交集。`proxy-server-nameserver` 独立配置为腾讯 DoH、阿里 DoH，未与
`fallback` 混用。`fallback-filter` 为 `{geoip: true, geoip-code: CN}`。**通过（静态）。**

### 3.4 无 DNS 循环与无明显泄漏路径

- `nameserver` 与 `fallback` 无交集；
- 四类服务器均不得指向 `dns.listen` 自身；`0.0.0.0:1053` 视为包含
  `127.0.0.1:1053` 与 `localhost:1053`；
- 测试覆盖 `127.0.0.1:1053` 与 `https://127.0.0.1:1053/dns-query` 两种自指形式。

**无循环：通过（静态）。无泄漏：未验证**——构建期无法证明运行时不泄漏；
需要真实设备抓包与 `dnsleaktest` 类检查，列入第 6 节遗留问题。

### 3.5 双平台差异

Windows 使用 TUN，`tun.dns-hijack` 含 `any:53`；OpenClash 使用 HTTP `port: 7893`，
不写 `mixed-port` 与 `tun`。两平台共用同一份 `dns`，没有把 Windows TUN 配置
复制到 OpenClash。OpenClash 的 DNS 监听端口、Fake-IP 与防火墙适配属运行时能力，
未在构建期模拟。**通过（构建期契约）。**

### 3.6 失败路径与确定性

28 项测试覆盖：非映射、11 个必填键缺失、`enable` 关闭、非法 `listen`（无端口、
0、65536、域名、IPv6、非数字）、`dns.ipv6: true`、非 Fake-IP、非法 Fake-IP 网段、
Filter 为空/非列表/重复/空项、`default-nameserver` 非 IPv4、服务器列表重复、
`nameserver`/`fallback` 重叠、自指循环、`fallback-filter` 非法，以及
`build_platform` 的端口冲突、顶层 IPv6、Windows `dns-hijack` 缺失。
两次构建产物逐字节一致（SHA-256 相同）。**通过。**

---

## 4. 产物核对

| 产物 | 字节 | SHA-256（前 16 位） | 策略组数 | 规则数 |
| --- | --- | --- | --- | --- |
| `dist/windows/config.yaml` | 4127 | `aef1eecacc3355d7` | 13 | 24 |
| `dist/openclash/config.yaml` | 4006 | `6d959695f66279a8` | 13 | 24 |

本阶段只增加校验，不改变产物内容，因此字节数与哈希与 ENG-02 一致。

---

## 5. 需求偏差与负责人决策

| 项 | 处理 | 依据 |
| --- | --- | --- |
| `dns` 仍由公共配置单所有者提供 | 不新增 OpenClash 专属 DNS 文件 | 负责人 2026-11-10 决策 |
| OpenClash DNS/防火墙适配不做进构建期 | 仅做静态校验，运行时兼容性待核验 | 同上；不得把未验证能力写成已实现 |
| Fake-IP Filter 固定 4 条 | 不猜测额外域名 | 负责人 2026-11-10 决策 |
| 未做 Mihomo 运行时加载与 DNS 泄漏测试 | 无固定版本二进制，且自动测试不能替代真实网络测试 | §9 第 11 条、§14 |
| `dns.yaml` 仅改注释 | 取值未变，避免无依据调整已确认参数 | 需求基线约束 |

---

## 6. 遗留问题

1. 未在 Mihomo v1.19.33 上加载产物，`dns.listen: 0.0.0.0:1053` 与 TUN
   `dns-hijack` 的实际配合未验证。
2. 未做真实 DNS 泄漏、污染与绕过路径测试；自动化测试只覆盖静态配置。
3. OpenClash 运行时是否注入自己的 DNS 监听端口、Fake-IP 与防火墙规则，未在
   iStoreOS 设备上核验。
4. Windows Clash Verge Rev 是否覆盖 `tun` / `mixed-port` 设置，未在设备上核验。
5. `fallback-filter` 的 GeoIP 行为依赖内核与数据库版本，尚未在目标内核验证。
6. DNS 缓存与定期刷新仍未实现，随 ENG-05 处理。
