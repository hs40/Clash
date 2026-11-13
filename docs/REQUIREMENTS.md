# 需求基线（REQUIREMENTS）

**版本：** v1.28
**来源：** 《Clash 配置工程开发 Plan》v1.0 第二章、第三章，以及项目负责人 2026-11-10、2026-11-11、2026-11-12、2026-11-13 的确认记录
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
| 兼容基准 | Mihomo v1.19.33（本机实际） | Mihomo Meta alpha-gbc76c13（设备实际，仅本平台） |

**注意：** 兼容基准按平台分别记录：Windows 为 Mihomo v1.19.33；OpenClash 由负责人
2026-11-10 确认改为设备实际 Mihomo Meta alpha-gbc76c13（仅 OpenClash）。2026-11-10
设备端 `-t` 已通过：`dist/openclash/config.yaml` 4006 字节，SHA-256
`6d959695f66279a8e75d48854e01068a0aa89b5ffc804a42c5a8d675ddbca33e`。

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
3. 节点识别结果定期更新，并保留本地缓存。【确定；ENG-01 做构建期识别。项目不拉取节点订阅，节点来自仓库内 `proxies.yaml`，因此节点识别结果没有持久化缓存；ENG-06 的 Provider 快照承担规则数据的本地缓存。此解释已记录，若负责人要求节点级缓存需另行立项】
4. 提供全局代理策略组。【确定】
5. 全局代理策略组包含自动选择和七个地区入口。【确定】
6. 不要求所有节点都能逐个手动选择。【确定】
7. Google 服务优先使用美国节点。【确定】
8. 美国节点不可用时，回退至指定地区白名单：狮城、日本、香港。【确定，2026-11-10 负责人确认】
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

### 4.2 地区识别与策略组生成【确定，2026-11-10 负责人确认】

**关键词表**（按表中顺序匹配，先命中者优先）：

| 入口 | 关键词 |
| --- | --- |
| 香港节点 | 香港、HK、Hong Kong |
| 台湾节点 | 台湾、台北、台灣、TW |
| 日本节点 | 日本、东京、大阪、JP |
| 韩国节点 | 韩国、首尔、韓國、KR |
| 狮城节点 | 新加坡、狮城、獅城、SG |
| 美国节点 | 美国、美國、洛杉矶、圣何塞、纽约、US、USA |
| 其他节点 | 不匹配以上任何关键词 |

- 纯 ASCII 关键词按整词匹配：前后不能紧邻英文字母。`HK01`、`US-01` 命中，
  `RUSSIA`、`JPEG` 不命中。
- 一个节点名命中多个地区时，按上表顺序取第一个：`美国-香港-01` 归香港节点。
- ASCII 匹配不区分大小写。

**生成规则**：

1. 策略组成员在**构建期**由 `proxies.yaml` 与关键词表生成，不手写节点名单；
   `proxy-groups.yaml` 通过 `include: all` 或 `include: region:<入口名>` 声明成员来源，
   该指令不进入产物。
2. 某地区没有节点时，该地区组填入 `自动选择`（不留空）。
3. `自动选择` 为 `url-test`，成员为全部节点。
4. Google 组为 `fallback`，顺序固定：美国节点 → 狮城节点 → 日本节点 → 香港节点。
5. 七个地区入口必须全部存在；缺失入口、未知 `include`、引用不存在的节点或策略组、
   策略组循环引用，均使构建失败。
6. ENG-01 只做构建期识别；§4 第 3 条的「本地缓存」在 ENG-06 由 Provider 快照实现（规则数据），节点识别结果本身不缓存（2026-11-10 负责人确认从 ENG-05 推迟到 ENG-06）。

### 4.3 业务策略组与路由目标【确定，2026-11-10 负责人确认】

| 业务 | 规则目标 | 说明 |
| --- | --- | --- |
| Google | `Google` 组 | `fallback`，顺序：美国节点 → 狮城节点 → 日本节点 → 香港节点 |
| AI | `OpenAI`、`Claude`、`Cursor` 三个独立组 | `select`，成员固定为「自动选择 + 七个地区入口」，默认选中「自动选择」 |
| Apple | `DIRECT` | |
| 国内金融 | `DIRECT` | |
| BT | `DIRECT` | |

- AI 范围仅限 OpenAI、Claude、Cursor；不纳入 Gemini、Perplexity 等（负责人确认）。
- 三个 AI 组必须存在，且成员顺序固定：自动选择、香港节点、台湾节点、日本节点、
  韩国节点、狮城节点、美国节点、其他节点。
- 规则引用的策略组必须存在；引用不存在的组使构建失败（§5.2）。

---

## 5. 分流规则【确定，ENG-02 实现契约】

统一采用四层结构：

1. 特殊规则：最高优先级。
2. 业务规则。
3. 基础规则。
4. 兜底规则：最低优先级，`MATCH` 必须最后。

### 5.1 源文件结构

`configs/common/rules.yaml` 的顶层键为 `rules`，其值为四层映射，键名固定为
`special`、`business`、`base`、`fallback`。每层是条目列表，每条为：

```yaml
- priority: 100          # 同层唯一的整数，越小越靠前
  rule: DOMAIN-SUFFIX,example.com,PROXY
```

未知规则层、未知条目键、缺失层、层值不是列表、非整数或布尔型 priority、
同层重复 priority、空的 rule，均使构建失败。

### 5.2 编译与校验

1. 层顺序固定为 special → business → base → fallback，**优先于** priority；
   priority 只在同层内排序。
2. 输出为 Mihomo 扁平规则字符串列表；层名与 priority 不进入产物。
3. `MATCH` 只能出现在 `fallback` 层，必须**有且仅有一条**，且必须是最后一条。
4. 支持的规则类型：`DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD`、`GEOIP`、
   `IP-CIDR`、`IP-CIDR6`、`SRC-IP-CIDR`、`DST-PORT`、`SRC-PORT`、
   `PROCESS-NAME`、`PROCESS-PATH`、`NETWORK`、`RULE-SET`、`MATCH`。
   嵌套逻辑规则（AND/OR/NOT）不在本期范围。
5. 规则按逗号分段；段首尾不得有空白，不得有空段。非 `MATCH` 类型至少三段。
6. 目标只能是已存在的策略组，或内置策略 `DIRECT`、`REJECT`、`REJECT-DROP`、`PASS`；
   其他目标使构建失败，并报告层、条目序号与规则文本。
7. 运行期采用 Mihomo 的**首条匹配**语义：命中第一条后不再继续匹配，因此层顺序即最终
   优先级。冲突测试必须模拟首条匹配，而不是只比较列表顺序。

### 5.3 当前最小规则集

ENG-02 只落最小代表集，完整通用名单由 ENG-06 Provider 的 `geosite-cn` 覆盖：

- Google：`google.com`、`googleapis.com`、`gstatic.com`、`googleusercontent.com` → `Google`。
- AI：OpenAI（`openai.com`、`chatgpt.com`、`oaistatic.com`、`oaiusercontent.com`）、
  Claude（`anthropic.com`、`claude.ai`）、Cursor（`cursor.com`、`cursor.sh`）→ 各自组。
- Apple：`apple.com`、`icloud.com`、`mzstatic.com` → `DIRECT`。
- 国内金融：`icbc.com.cn`、`ccb.com.cn`、`abchina.com`、`boc.cn` → `DIRECT`。
- BT：`DOMAIN-KEYWORD,tracker` → `DIRECT`。
- 基础层（按 priority）：`RULE-SET,geosite-private,DIRECT`（90）、`GEOIP,LAN,DIRECT,no-resolve`（100）、`RULE-SET,geosite-cn,DIRECT`（110）、`GEOIP,CN,DIRECT`（120）；兜底 `MATCH,PROXY`。
- `geosite-private` 先于 `geosite-cn`，避免私有域名被国内集合误伤；业务规则仍内联，不能被 Provider 覆盖。

### 5.4 冲突测试要求

必须覆盖：special 的 `DOMAIN` 命中后压过 business 的 `DOMAIN-SUFFIX`；
未命中前序层时按 base、fallback 顺序命中；所有规则目标均存在；`MATCH` 唯一且最后。

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

### 7.1 构建期 DNS 校验【确定，ENG-03 实现契约】

`validate_dns(dns)` 是纯函数接缝；`build_platform` 在策略组展开前调用，任一校验失败
即构建失败（CLI 退出码 2）。校验项：

1. 必填键齐全：`enable`、`listen`、`ipv6`、`enhanced-mode`、`fake-ip-range`、
   `fake-ip-filter`、`default-nameserver`、`nameserver`、`proxy-server-nameserver`、
   `fallback`、`fallback-filter`。
2. `enable` 必须为 true，`ipv6` 必须为 false，`enhanced-mode` 必须为 `fake-ip`。
3. `listen` 必须为 `IPv4:端口`，端口在 1-65535 之间；主机不得是域名或 IPv6。
4. `fake-ip-range` 必须是 IPv4 网段，前缀长度在 /8-/30 之间。
5. `fake-ip-filter` 必须是非空列表，条目为非空字符串且不重复；产物固定为 §13.3 的 4 条。
6. 四个服务器列表（`default-nameserver`、`nameserver`、`proxy-server-nameserver`、
   `fallback`）必须非空、条目为非空字符串且不重复；`default-nameserver` 只允许 IPv4，
   其余列表不得包含 IPv6 字面量。
7. `nameserver` 与 `fallback` 不得存在交集。
8. 四类服务器均不得指向 `dns.listen` 自身（`0.0.0.0` 视为包含 `127.0.0.1` 与
   `localhost`），防止转发循环。
9. `fallback-filter` 必须是映射，`geoip` 为 true，`geoip-code` 为 `CN`。
10. 顶层 `ipv6` 必须为 false；`dns.listen` 端口不得与 `mixed-port` 或 `port` 相同。
11. Windows 的 `tun.dns-hijack` 必须包含 `any:53`。

错误信息以 `dns：` 前缀或对应键名开头。两平台共用同一份 `dns`；OpenClash 运行时的
DNS 监听与防火墙适配不在构建期模拟，设备兼容性列入 §14 待核验。

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

### 8.1 ENG-06 Provider 实现契约【确定，2026-11-11 负责人确认】

1. **白名单来源**：只允许 `MetaCubeX/meta-rules-dat`，分支 `meta`，许可证 GPL-3.0；负责人 2026-11-11 批准。新增来源、仓库或下载地址必须人工审批。
2. **只使用两个通用集合**：`geo/geosite/private.list` 与 `geo/geosite/cn.list`，`behavior: domain`。特殊业务规则继续内联在 `configs/common/rules.yaml`。
3. **锁定**：`providers/lock.yaml` 记录来源、固定 commit、上游路径、SHA-256、字节数和快照路径；`providers/snapshots/*.list` 是唯一构建输入。构建时逐项校验存在性、字节数和 SHA-256，不一致立即失败。
4. **内嵌**：构建期把已验证快照渲染为 `rule-providers.<name>.type: inline`，配置自包含，不在运行时下载。两份平台配置因此增大约 2.28 MB，这是已接受的取舍。
5. **规则引用**：`RULE-SET,<provider>,<target>` 必须恰好三段，Provider 必须存在于锁文件；未知 Provider 使构建失败。
6. **每周检查**：`.github/workflows/provider-check.yml` 每周一 03:00 UTC 运行 `update_providers.py --check --json`；发现变化时创建或更新 issue，不自动改 `main`。
7. **应用更新**：负责人本地运行 `python scripts/update_providers.py --apply --commit <40位上游 commit>`；脚本原子写入快照与锁文件，校验 payload，打印建分支/提交/PR 命令，不自动执行 git 或 PR。高风险更新必须经 PR 审查。
8. **第三方声明**：发布包和仓库包含 `THIRD_PARTY_NOTICES.md` 与 `providers/LICENSE-metacubex.txt`；负责人 2026-11-11 批准在发布包内嵌 GPL-3.0 数据并保留声明。
9. **版本保留**：GitHub Release 历史不自动删除；负责人至少保留最近五个已验证版本，当前生产版本不得删除。本期不实现自动清理。

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

### 9.1 ENG-05 CI 与安全检查实现契约【确定，2026-11-10 负责人确认】

CI 工作流 `.github/workflows/ci.yml`：

1. 触发：`pull_request` 与 `push` 到 `main`；运行环境 `windows-latest`，Python 3.12.3。
2. 权限：顶层 `permissions: contents: read`；不引用 Secrets，不使用 `pull_request_target`。
3. 第三方 Action 固定完整 40 位 Commit SHA；`actions/checkout` 必须设置 `persist-credentials: false`。
4. 步骤顺序：`pip install --require-hashes -r requirements.txt` → `pip check` → `check_dependencies.py` → `build.py --platform all` → `security_scan.py` → `ci_policy.py` → `ci_report.py --output ci-report.md` → Mihomo 下载/校验/`-t` 双平台。
5. 中文报告写入 `ci-report.md` 与 `GITHUB_STEP_SUMMARY`；报告不提交，已加入 `.gitignore`。
6. 依赖锁定：`requirements.txt` 每个依赖使用精确版本 + 至少一个 SHA-256；校验脚本拒绝未锁定、缺哈希、格式错误与重复项。
7. Mihomo：`security/mihomo.yaml` 固定版本、官方 URL、压缩包 SHA-256、可执行文件名与 SHA-256；CI 校验后运行 `-t`。Windows 基准为 v1.19.33。
8. GeoIP：CI 下载 `country.mmdb` 并固定内容 SHA-256；上游 `latest` 标签可变，哈希变化必须由负责人审查后更新。
9. 敏感信息：`security_scan.py` 扫描仓库文本文件，只报告路径、行号与类型，不回显命中内容；占位标记（如 `PLACEHOLDER`、`NOT-REAL`）不作为真实凭据。
10. CODEOWNERS：`@hs40` 审查 `.github/`、`scripts/`、`configs/common/`、`security/`、`docs/REQUIREMENTS.md`；高风险失败阻断发布，仅负责人可解除。`ci_policy.py` 只做静态检查；当前分支保护（§9.2）未启用 Require review from Code Owners，因此 CODEOWNERS 目前是归属声明与静态检查，不是合并门禁。负责人 2026-11-11 明确批准策略 A 下的这一 bypass；这是负责人授权，不是 Agent 自行豁免。
11. 限制：CI 不能替代 §14 的真实网络连通性与 DNS 泄漏测试。
12. ENG-06 工作流权限：`provider-check.yml` 顶层 `contents: read`、job 级 `issues: write`，只用于创建 Provider 更新 issue；`release.yml` 顶层 `contents: write`，只在 `v*` tag 触发，用于创建 GitHub Release。两者都不引用 Secrets，不使用 `pull_request_target`。
13. Provider Check 在 Windows runner 的 job 级设置 `PYTHONUTF8: "1"`，避免中文输出在 cp1252 控制台触发 `UnicodeEncodeError`；`tests/test_ci_policy.py` 对此做静态回归检查。

### 9.2 远端 main 分支保护（策略 A）【确定，2026-11-11 负责人确认】

main 分支保护规则：

1. 要求通过 Pull Request 合并；Required approvals = 0（单人仓库，负责人可自行合并自己的 PR）。
2. 必需状态检查：`test`；Require branches to be up to date before merging = true。
3. 管理员同样受保护规则约束（enforce admins）。
4. 禁止 force push、禁止删除分支。
5. 不启用 Require review from Code Owners：GitHub 不允许 PR 作者审批自己的 PR，单人仓库启用后会锁死合并。启用它需要增加第二审查人，或显式允许负责人 bypass。
6. **负责人批准记录（2026-11-11）**：负责人 @hs40 明确批准策略 A，并批准在单人仓库下不启用 Require review from Code Owners 的 bypass；该批准针对当前单人维护模式，增加第二审查人后应重新评估。Agent 未自行批准该例外。
7. 验证记录：临时 PR #1（head `2982220803297bf088b920457d562ad1a60bde94`）触发 `test` 成功（run 42956763427 / job 130313590289），PR 以 closed/unmerged 关闭，临时分支已删除。

### 9.3 本机 DNS 泄漏护栏（C + A）【确定，2026-11-12 负责人确认】

1. 背景：默认解析路径返回 fake-IP，但显式查询 `192.168.2.1:53` 会绕过 TUN 返回真实地址，构成 DNS 泄漏。
2. 决策 C：在 Windows 防火墙新增两条出站阻断规则，阻断本机到 `192.168.2.0/24` 的 UDP/TCP 53，保留 TUN DNS `198.18.0.2`。2026-11-12 进一步决策 A：放行受控解析器 `192.168.2.10:53`（OpenClash 验收需要查询其 fake-IP），仍阻断该网段其余地址；`.10` 是已确认的 iStoreOS 设备。
3. 规则契约：组 `Clash DNS Guard`；显示名 `Clash DNS Guard - Block LAN DNS (UDP)` / `(TCP)`；Outbound、Block、Profile Any、Enabled True；远程地址为 `192.168.2.0/24` 去掉 `192.168.2.10/32` 后的 8 条 CIDR：`192.168.2.0/29`、`192.168.2.8/31`、`192.168.2.11/32`、`192.168.2.12/30`、`192.168.2.16/28`、`192.168.2.32/27`、`192.168.2.64/26`、`192.168.2.128/25`；远程端口 53。Windows 可能把 CIDR 规范化为点分掩码；`--check` 要求解析后的地址集合精确等于上述 8 条，旧的 `/24` 全阻断判为不合格。
4. 边界：只增删上述两条规则；不改系统 DNS、hosts、路由、代理设置或任何入站规则；不进入 `dist/` 或 GitHub Release；需要管理员权限。仅在 Mihomo TUN 已接管、默认 DNS 为 `198.18.0.2` 时使用；TUN 关闭或 Mihomo 停止时应先移除规则，避免本机失去 DNS。
5. 实现：`scripts/dns_guard.py`、`dns-guard.cmd`；`--check` 只读，`--apply` 幂等，`--remove` 回滚；应用失败时清理本次已创建的规则。`dns-guard.cmd` 优先从 `.venv\pyvenv.cfg` 的 `home` 读取基础解释器，避免 `.venv\Scripts\python.exe` 启动器在管理员窗口中的完整性问题；`dns_guard.py` 只使用标准库。
6. 验收：`--check` 的 UDP/TCP 均为 OK；默认解析仍为 fake-IP；`192.168.2.10:53` 返回 fake-IP；`192.168.2.1:53` 超时；`223.5.5.5:53` 仍被 TUN 劫持；百度、gstatic、Google、YouTube 回归；`--remove` 后可恢复路由器 DNS。
7. 当前状态（2026-11-13）：A 决策的 8 条 CIDR 新规则已在管理员上下文应用；`dns_guard.py --check` 返回 `UDP: OK`、`TCP: OK`、`overall: OK`（exit 0），`192.168.2.10:53` 返回 fake-IP，`192.168.2.1:53` 超时，依赖 `.10:53` 的 OpenClash 验收已完成。`--remove` 回滚演练为 2026-11-12 旧 `/24` 规则记录，新规则的移除演练尚未重做。
8. 该高风险安全变更由负责人 2026-11-12 选择 C，随后选择 A；新地址集合已于 2026-11-13 应用并复核。后续修改仍按高风险变更审查；移除新规则前须确认不依赖 `.10:53` 的验收路径。

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

### 10.1 ENG-06 发布实现契约【确定，2026-11-11 负责人确认】

1. **版本来源**：仓库根 `VERSION` 是唯一版本来源，必须与发布版本完全一致（SemVer `X.Y.Z`）；不一致时 `release.py` 失败。
2. **发布产物**：`scripts/release.py --version X.Y.Z` 为每个平台生成 `config.yaml` 和 `<platform>-X.Y.Z.zip`；zip 包含 `config.yaml`、`THIRD_PARTY_NOTICES.md`、`LICENSE-metacubex.txt`、`CONFIG-DIFF.md`。发布目录还包含 `RELEASE-NOTES.md`、`CONFIG-DIFF.md` 与 `SHA256SUMS`。
3. **差异报告**：`CONFIG-DIFF.md` 记录两个平台的 SHA-256、顶层键、策略组/规则/Provider/节点数；若发布目录中存在更早的 SemVer 版本，则比较策略组、规则、Provider 与顶层键的增删。
4. **校验与资产清单（2026-11-11 修正）**：`release.py --verify <dir>` 校验 `SHA256SUMS` 只包含 Release 实际上传的两个平台 zip（不漏项、不多项）、每个 SHA-256、发布目录必需文件与无多余文件、配置可解析、`MATCH` 最后、Provider 存在、zip 成员与内嵌配置/差异报告一致。发布目录内的配置、说明和许可证不作为清单条目；它们由 zip 内同名副本核对，因此下载全部 Release 资产后 `sha256sum -c SHA256SUMS` 可通过。
5. **触发方式（负责人 2026-11-11 批准）**：`release.yml` 仅在推送 `v*` tag 时自动运行测试、构建、校验并 `gh release create`。这是对 Plan §10.1「main 合并后自动发布」的明确偏离：避免每次文档合并误发版，保持 VERSION 与 tag 显式对齐；负责人已批准该取舍。
6. **人工步骤**：负责人合并 PR 后，确认 `VERSION` 与发布内容，推送对应 tag；不自动修改设备。
7. **回滚**：`docs/ROLLBACK.md` 规定平台独立、先备份、SHA 校验、至少保留五个版本、当前生产版本不删除；回滚由负责人手动执行。
8. **已知限制（2026-11-11）**：Release 工作流在干净检出中构建，不会自动获取上一 GitHub Release 的配置作为基线，因此发布包内的 `CONFIG-DIFF.md` 在无本地旧版本目录时显示“未找到上一版本”。本地构建若 `dist/release` 已存在更早 SemVer 目录则会比较。该限制不影响 `SHA256SUMS`、zip 或配置正确性；后续版本如要修复，需单独评审发布流程变更。

---

## 11. 公共配置与平台配置的边界【确定，MVP 实现契约】

`configs/<platform>/platform.yaml` 是一段 **Mihomo 顶层配置片段**，顶层键直接对应
最终配置的顶层键。构建时做**顶层浅合并**，不做递归深合并，每个顶层键只有一个所有者。

| 归属 | 顶层键 | 说明 |
| --- | --- | --- |
| 公共独占 | `proxies`、`proxy-groups`、`rules`、`dns`、`rule-providers` | 由 `configs/common/` 与 Provider 锁文件生成；平台配置不得写入 |
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
6. `proxy-groups` 支持构建期指令 `include: all` 与 `include: region:<入口名>`，由 Builder
   展开为成员；该指令不进入产物。未知指令、无效引用、循环引用 → 构建失败（§4.2）。
7. `rule-providers` 由 `providers/lock.yaml` 与已验证快照生成，是公共独占键；构建必须存在锁文件，平台配置或公共 YAML 直接定义 `rule-providers` 都会失败（§8.1）。

---

## 12. MVP 阶段实现边界【确定】

必须实现：仓库目录、需求基线、公共配置、Windows 平台配置、OpenClash 平台配置、
Python 最小构建程序、YAML 基础校验、两份配置生成结果、基础自动化测试。

暂不实现：自动节点地区识别、自动策略组生成、完整四层规则系统、Provider 自动更新、
完整 DNS/Fake-IP 测试体系、Mihomo 多版本兼容测试、完整安全扫描体系、自动 Release、
自动设备部署、OpenClash 防火墙自动部署。

以上是 MVP 当阶段的边界。ENG-01 已实现节点地区识别与策略组生成（§4.2），
ENG-02 已实现四层规则编译（§5）与业务策略组（§4.3），ENG-03 已实现 DNS/Fake-IP
构建期校验（§7.1）。ENG-04 已实现双平台完整配置；Windows 本机按 v1.19.33 验证通过，
OpenClash 设备端按 alpha-gbc76c13 执行 `-t` 通过；NAS/HAOS/Proxmox 路径尚未完成验证。
ENG-05 已实现 CI 配置、依赖哈希锁定、敏感信息扫描、Mihomo 固定版本校验、中文测试报告
与 CODEOWNERS 静态策略检查；远端 main push CI 已于 2026-11-10 运行并通过，Actions 已升级到
checkout v7.0.1 / setup-python v7.1.0（node24）。2026-11-11 已启用 main 分支保护策略 A，
并通过临时 PR #1 实际验证 PR 触发 CI 与必需检查 `test`（§9.2）；CODEOWNERS 强制未启用。
ENG-06 已实现 Provider 锁定/内嵌、每周检查、更新脚本、发布包与配置差异报告、回滚文档，
以及 tag 触发的 Release 工作流（§8.1、§10.1）。PR #3 已合并到 main（`c3436d3`），PR CI
与 main CI（run 42964259372）均通过。Provider Check 已于 2026-11-11 在远端实际触发并通过
（run 42972389013）；首次运行因 Windows 控制台编码失败，已通过 PR #5（`d4a7a4a`）修复并
补回归测试。同日推送 `v0.1.0` annotated tag，Release run 42997351203 成功创建 GitHub
Release 并上传两个 zip 与 `SHA256SUMS`；资产下载校验与 Mihomo `-t` 通过。Provider Check
的 issue 创建路径也已用临时分支 run 42996296022 实际验证（issue #6，随后关闭）。`v0.1.0`
的 `SHA256SUMS` 覆盖完整发布目录、与 Release 仅上传两个 zip 不一致；该限制已由 PR #10
（`6d0555b`）修正为只覆盖两个 zip 资产，squash merge 为 `4cb9148`，并发布 `v0.1.1`
（Release run 43003842864）。`v0.1.1` 远端 3 个资产下载后独立哈希、zip 结构、解出配置
与 Mihomo `-t` 均通过；干净本地目录构建复现了远端 zip 哈希。平台部署已将内嵌 Provider
的构建产物写入 iStoreOS 并通过 `-t`；Release zip 本身未单独在设备上重测。远端
`CONFIG-DIFF.md` 因干净检出无上一版本基线而显示“未找到上一版本”，见 §10.1 第 8 条。
2026-11-12 按负责人要求增加 Tailscale 直连规则（`100.64.0.0/10`，特殊层），
构建与 Verge 全局脚本的规则数由 26 增至 27；该规则尚未在 TUN 全接管场景下实测。
随后为 dsh-pocket 增加 `argotunnel.com`、`trycloudflare.com`、`198.41.192.0/24` 与
`tailscale.com`、`tailscale.io`、`ts.net` 六条直连规则，当前规则数为 33。

2026-11-12 起另按负责人 Q13–Q32 实现个人网络部署平台（Windows Clash Verge +
iStoreOS OpenClash 的计划/部署/验证/回滚）；需求与边界见
`docs/PLATFORM-REQUIREMENTS.md`。平台代码与 357 项本地测试已完成；Windows 与 OpenClash 均已
真实部署并通过当前自动验收；节点地区比对、失败回滚实机演练与人工项仍未关闭；PR #17 已于
2026-11-13 squash 合并（`de4d5be`）；PR #18（`dns.fallback` 加 `#PROXY`）已合并为
`3cf7774` 并已重部署到 OpenClash 设备（run `20261113-195320-018656`，当前配置 SHA-256
`2d8dc2fee4c59bb46656288bfc174e25ea99d941c78b70c91407d5f609e37343`）。
代理认证按 Q32 只使用一次性环境变量；2026-11-13 验收读取设备 UCI 的一次性例外见
`docs/PLATFORM-ACCEPTANCE.md`。

---

## 13. MVP 草案参数【草案，2026-11-10 负责人同意作为起点，部署前必须核验】

### 13.1 Windows（Clash Verge Rev v2.5.10）

| 键 | 草案值 | 说明 |
| --- | --- | --- |
| `mixed-port` | `7897` | 负责人 2026-11-10 确认；与本机 Verge 实际生成值一致 |
| `allow-lan` | `false` | |
| `tun.enable` | `true` | |
| `tun.stack` | `gvisor` | 用户态栈，Windows 兼容性优先，【待核验】 |
| `tun.auto-route` | `true` | |
| `tun.auto-detect-interface` | `true` | |
| `tun.dns-hijack` | `["any:53"]` | |
| `tun.strict-route` | `false` | |

本机核验（2026-11-10）：Clash Verge Rev 2.5.10 实际生成的 `config.yaml` 使用
`mixed-port: 7897`、`ipv6: true`、`tun.enable: false`，会覆盖配置中的同名值。
负责人决定仓库保留 `mixed-port: 7897`，IPv4-only 与 TUN 由负责人在 Verge GUI
手动设置；本工程不写入用户真实 Verge 配置。

### 13.2 OpenClash（iStoreOS 旁路由）

| 键 | 草案值 | 说明 |
| --- | --- | --- |
| `port` | `7893` | HTTP 代理端口，NAS 显式代理依赖此值【确定】 |
| `allow-lan` | `true` | |
| `bind-address` | `"*"` | |
| LAN 访问限制 | 仅 `allow-lan` + `bind-address` | 负责人 2026-11-10 决定保持现状；`lan-allowed-ips` 内核支持但未启用 |

设备核验（2026-11-10）：iStoreOS 上 `/etc/openclash/core/clash_meta` 为
`Mihomo Meta alpha-gbc76c13 linux amd64 with go1.26.9 Mon Oct 12 03:44:17 UTC 2026`。
负责人 2026-11-10 确认：OpenClash 设计基准改为该设备实际版本（仅 OpenClash，Windows
仍为 v1.19.33）。同日负责人只读执行 `-t`：产物 4006 字节、SHA-256 `6d959695…`，
输出 `configuration file ... test is successful`、`TEST_EXIT=0`；未重启或修改 OpenClash。

### 13.3 DNS

以下取值是 ENG-03 的构建期基线，`validate_dns` 会强制校验；设备上的实际兼容性仍需按 §14 核验。

| 键 | 草案值 | 说明 |
| --- | --- | --- |
| `dns.enable` | `true` | |
| `dns.listen` | `0.0.0.0:1053` | 与 Windows TUN `dns-hijack` 的配合【待核验】；OpenClash 可能用自己的监听端口 |
| `dns.ipv6` | `false` | |
| `dns.enhanced-mode` | `fake-ip` | |
| `dns.fake-ip-range` | `198.18.0.1/16` | |
| `dns.fake-ip-filter` | `*.lan`、`*.local`、`+.msftconnecttest.com`、`+.msftncsi.com` | 只保留必要项，不猜测额外域名 |
| `dns.default-nameserver` | `223.5.5.5`、`119.29.29.29` | |
| `dns.nameserver` | `https://dns.alidns.com/dns-query`、`https://doh.pub/dns-query` | 国内 |
| `dns.proxy-server-nameserver` | `https://doh.pub/dns-query`、`https://dns.alidns.com/dns-query` | 节点域名独立解析路径 |
| `dns.fallback` | `https://1.1.1.1/dns-query#PROXY`、`https://dns.google/dns-query#PROXY` | 国外；必须经代理查询 |
| `dns.fallback-filter` | `{geoip: true, geoip-code: CN}` | |

> **2026-11-13 修复：** 境外 DoH 若直连，在中国大陆会被阻断；Mihomo 对非 CN 解析结果
> 走 `fallback` 时会出现 `context deadline exceeded`，导致 `DIRECT` 域名解析失败。
> `#PROXY` 后缀强制经代理查询，已由真实 Windows 环境验证。`validate_dns` 不剥离该后缀。

### 13.4 占位节点

MVP 的 `configs/common/proxies.yaml` 使用占位节点：`type: ss`、
`server: 192.0.2.x`（TEST-NET-1，永不指向真实主机）、`port: 443`、
`cipher: aes-128-gcm`、`password: PLACEHOLDER-NOT-REAL`、`udp: false`，
并在文件头注明「占位节点，禁止部署」。占位内容不得被描述为真实节点。

### 13.5 本机 Clash Verge 全局扩展【已实施，2026-11-11 负责人确认；2026-11-12 复验；部署辅助，非发布配置】

目标：把同一套 MVP 设置套用到 Verge 的所有订阅，订阅更新或切换后不必重建本地 profile。
该能力不进入 `dist/`、GitHub Release 或 OpenClash 配置，不改变 §11 的构建契约。

| 文件 | 作用 |
| --- | --- |
| `profiles/Merge.yaml` | 只写 `profile.store-selected: true` 与 `geosite-cn`、`geosite-private` 两个 inline Provider |
| `profiles/Script.js` | 删除订阅自带策略组/规则/DNS/多余 Provider，生成固定 13 组、33 条规则与 MVP DNS |
| `profiles.yaml` | 只切换 `current`，不改订阅 URL 或订阅文件 |
| `verge.yaml` | 只保留 `enable_tun_mode`、`enable_system_proxy`、`verge_mixed_port` 三项设置 |

固定组顺序（负责人 2026-11-11 确认，顺序不可调整）：
`PROXY`（select：自动选择、七个地区组、DIRECT）、`Google`（fallback：美国→狮城→日本→香港）、
`OpenAI`、`Claude`、`Cursor`（select：自动选择 + 七个地区组）、`自动选择`（url-test：全部可用节点）、
七个地区组（select）。地区识别复用 `scripts/regions.py`，空地区回退 `自动选择`。

规则共 33 条（特殊 8、业务 20、基础 4、兜底 1），最后一条唯一为 `MATCH,PROXY`。
特殊层含 `IP-CIDR,100.64.0.0/10,DIRECT,no-resolve`，覆盖 Tailscale CGNAT
（含节点 IP 与 MagicDNS 地址 100.100.100.100）；MagicDNS 域名解析仍由 Tailscale DNS 负责，
未纳入 Clash DNS；另含 dsh-pocket 的 `argotunnel.com`、`trycloudflare.com`、
`198.41.192.0/24` 直连规则，以及 `tailscale.com`、`tailscale.io`、`ts.net` 直连规则。
Script 强制 `mixed-port: 7897`，删除订阅的 `port` / `socks-port`，设置 `mode: rule`、
`ipv6: false`、`allow-lan: false`；保留 Verge 注入的 `tun`、`external-controller`、
`secret` 与 `profile`，不写这三个键。

订阅必须提供 inline `proxies`；遇到 `proxy-providers` 中止。预检先剔除
`reality-opts.short-id` 非 8/16 位十六进制的节点，再逐节点执行 `mihomo -t`；
全部不可用时中止。额外坏节点写入 Script 的 `MVP-EXCLUDED` 标记块，每次预检重写，
不建立永久黑名单。

应用前备份 `profiles/Merge.yaml`、`profiles/Script.js`、`profiles.yaml`、
`verge.yaml`、`config.yaml`、`clash-verge.yaml` 到 `.tmp_verge_apply_backup_<时间戳>`，
写入采用同目录临时文件 + 原子替换；重启后要求 `clash-verge.yaml` 的 mtime 前进并通过
`verify_config`，否则自动恢复六个备份文件。重启按镜像名结束 `clash-verge.exe` 与
`verge-mihomo.exe`，再执行计划任务 `Clash Verge (Admin)`；`schtasks /End` 不足以结束
sidecar。

本机验证（2026-11-11，FIB）：55 个节点，静态剔除 9 个，运行时剔除 0，可用 46；
运行时 46 proxies / 13 groups / 26 rules / 2 providers；7897 与 1053 监听；TUN 适配器
`Mihomo` Up、默认路由 198.18.0.2、fake-ip 198.18.0.7；百度 200、gstatic 204、
Google 204、YouTube 200，出口 178.83.206.223（ipinfo 显示 HK）。全局文件与备份哈希见
`docs/VERGE-GLOBAL.md` §6。旧本地 `mvpClash0001` 保留作回退。

重新部署（2026-11-12，FIB；历史记录，当时规则 27 条）：运行时 2,297,734 B、SHA-256 `620D83D5…`，
46 proxies / 13 groups / 27 rules / 2 providers；7897 与 1053 监听；TUN Up；
百度 200、gstatic 204、Google 200、YouTube 200、dns.google Status 0；出口 HK；
备份 `.tmp_verge_apply_backup_20261112-132035`。详见 `docs/VERGE-GLOBAL.md` §6.1。

限制：只验证 FIB 一个订阅；其他订阅、断网重连、重启后 TUN 自动恢复与 Verge 应用回滚演练未验证；
2026-11-12 发现显式查询 `192.168.2.1:53` 会绕过 TUN，负责人选择 C，护栏见 §9.3，
已应用，DNS 路径/站点回归、管理员 `check` 与 `--remove` 回滚演练均通过；`verge-sync.cmd` 需要管理员权限；DSH 低完整性 `.venv` 写 AppData 会被拒绝，
需改用系统 Python；订阅重命名后需重跑 `verge-sync.cmd` 更新排除键。详见 `docs/VERGE-GLOBAL.md`。

---

## 14. 待核验清单【待核验】

1. 设备上实际的 Mihomo 版本与兼容性。
   Windows 本机为 v1.19.33；OpenClash 设计基准为设备实际 alpha-gbc76c13（仅 OpenClash）。
   【已核验 2026-11-10：设备端 `-t` 通过，产物 4006 字节、SHA-256 `6d959695…`】
2. ~~Clash Verge Rev v2.5.10 是否会覆盖 `platform.yaml` 中的 `mixed-port` / `tun` 设置。~~
   【已核验 2026-11-10：会覆盖；负责人决定 mixed-port 取 7897，IPv6/TUN 手动设置】
3. OpenClash 是否自行注入 `redir-port` / `tproxy-port` 与 DNS 监听（如 7874）。
4. `dns.listen: 0.0.0.0:1053` 与 TUN `dns-hijack` 的实际配合方式。
5. ~~Mihomo v1.19.33 是否支持 `lan-allowed-ips`（决定 OpenClash LAN 限制的实现方式）。~~
   【已核验 2026-11-10：支持且 `-t` 通过；负责人决定保持 `allow-lan` + `bind-address`，不启用】
6. 真实网络连通性、DNS 泄漏与绕过代理路径（自动化测试不能替代）。
7. ~~Google 回退的「指定地区白名单」具体地区。~~【已确认 2026-11-10：狮城、日本、香港】
8. OpenClash 的 DNS 监听与 Fake-IP 已于 2026-11-13 在设备上验证（`127.0.0.1:7874`，fake-IP `198.18.0.4`）；ENG-03 仍只做构建期静态校验，防火墙适配的长期行为未验证。
9. GitHub 远端 main push CI 已于 2026-11-10 通过；2026-11-11 已启用 main 分支保护策略 A（PR + 必需检查 `test` + 0 审批），并通过临时 PR #1 实际验证 PR CI；CODEOWNERS 强制未启用（§9.2）。
10. ENG-06 内嵌 Provider 后，配置增大约 2.28 MB；Windows 本机 Mihomo v1.19.33 与平台部署到 iStoreOS 的构建产物均通过 `-t`；Release zip 本身未单独在设备上重测，NAS 端到端仍未验证。
11. ENG-06 的 PR #3 已合并（`c3436d3`），PR CI 与 main CI（run 42964259372）均通过；Provider Check 已于 2026-11-11 远端触发并通过（修复 run 42972389013；首次 run 42969347805 因 Windows 编码失败，修复见 §9.1 第 13 条）。`v0.1.0` Release run 42997351203 成功，两个 zip 与 `SHA256SUMS` 已上传并下载校验，Release 内配置在本机 Mihomo 上 `-t` 通过；issue 创建由临时分支 run 42996296022 实际验证（issue #6，随后 #6–#8 关闭）。`v0.1.0` 的 `SHA256SUMS` 覆盖完整发布目录 8 行，Release 只上传 2 个 zip 与校验文件，全量校验会缺少 6 个非资产条目；该限制已在 PR #10（`6d0555b`）修正，squash merge `4cb9148` 并发布 `v0.1.1`（Release run 43003842864）：清单只列两个 Release zip，发布目录的其余文件由结构校验与 zip 内副本核对。远端 `v0.1.1` 资产为 `openclash-0.1.1.zip` 511,688 B / `3016674d...` 与 `windows-0.1.1.zip` 511,738 B / `e55796c9...`；下载后独立校验、zip 结构、解出配置与 `-t` 均通过，干净本地目录构建复现相同 zip 哈希。`v0.1.0` 保持原样，不重写。远端 `CONFIG-DIFF.md` 仍无上一版本基线，见 §10.1 第 8 条；设备重测见第 10 项。
12. 发布版本保留最近五个由负责人手动维护；本期没有自动清理逻辑，也没有自动回滚。
13. GPL-3.0 再分发已由负责人 2026-11-11 批准，发布包必须始终携带 `THIRD_PARTY_NOTICES.md` 与 `LICENSE-metacubex.txt`。
14. 本机 Verge 全局扩展（§13.5）只用 FIB 一个订阅验证；其他订阅、断网重连、TUN 重启恢复与 Verge 应用回滚演练未验证；DNS 泄漏已复现（`192.168.2.1:53` 绕过 TUN），护栏见 §9.3；2026-11-13 已重新部署 46/13/33 并通过当前 verify，A 决策的 8 条 CIDR 已应用；旧 `mvpClash0001` 保留作回退。
15. Tailscale CGNAT 直连规则已进入构建源，但本机现有 Tailscale peer 使用 /32 直连路由，尚未在 TUN 全接管或新增 peer 场景复测；MagicDNS 未启用/未验证。
16. DNS 泄漏护栏（§9.3）：2026-11-13 已应用 A 决策的 8 条 CIDR 新规则，`dns_guard.py --check` 返回 UDP/TCP/overall OK（exit 0），`192.168.2.10:53` 返回 fake-IP，`192.168.2.1:53` 超时；`--remove` 回滚演练为 2026-11-12 旧 `/24` 规则记录，新规则的移除演练尚未重做。

---

## 15. 变更记录

| 日期 | 版本 | 变更 | 确认人 |
| --- | --- | --- | --- |
| 2026-11-09 | v1.0-draft | 从 Plan v1.0 提取需求基线 | — |
| 2026-11-10 | v1.0 | 确认七个地区入口名称；确认 MVP 草案参数与合并契约 | 项目负责人 |
| 2026-11-10 | v1.1 | 追认新增公共文件 `configs/common/general.yaml`；确认 `其他节点` 为未匹配地区的兜底节点池 | 项目负责人 |
| 2026-11-10 | v1.2 | 确认地区关键词表、匹配优先级、Google 回退顺序（狮城→日本→香港）与 `include` 生成契约 | 项目负责人 |
| 2026-11-10 | v1.3 | 确认四层规则源文件结构、编译校验契约、冲突测试要求；确认 AI 三组（OpenAI/Claude/Cursor）与五类业务路由目标 | 项目负责人 |
| 2026-11-10 | v1.4 | 确认 DNS 保持公共单所有者、Fake-IP Filter 4 条与 `validate_dns` 校验契约（§7.1） | 项目负责人 |
| 2026-11-10 | v1.5 | 确认 Windows `mixed-port` 取 7897；确认 Verge 覆盖 IPv6/TUN 由负责人手动设置；确认 OpenClash LAN 限制保持 `allow-lan` + `bind-address` | 项目负责人 |
| 2026-11-10 | v1.6 | 记录 iStoreOS 实际内核 alpha-gbc76c13（非 v1.19.33）；记录 HAOS/Proxmox 尚未部署；设备端验证与内核差异处理待负责人决定 | 项目负责人（事实记录） |
| 2026-11-10 | v1.7 | 确认 OpenClash 设计基准改为设备实际 alpha-gbc76c13（仅 OpenClash）；Windows 保持 v1.19.33 | 项目负责人 |
| 2026-11-10 | v1.8 | 记录 OpenClash 设备端 `-t` 通过（产物 4006 字节、SHA-256 `6d959695…`）；ENG-04 内核加载验收通过，NAS/HAOS/Proxmox 路径仍未验证 | 项目负责人（事实记录） |
| 2026-11-10 | v1.9 | 完成 ENG-05 CI/安全实现契约：依赖哈希、敏感扫描、Mihomo 固定校验、中文报告、CODEOWNERS；缓存从 ENG-05 推迟到 ENG-06；远端 CI 与分支保护未验证 | 项目负责人（事实记录） |
| 2026-11-10 | v1.10 | 记录远端 main push CI 通过；Actions 升级到 checkout v7.0.1 / setup-python v7.1.0（Node 24）；PR CI、分支保护与 CODEOWNERS 强制待验证 | 项目负责人（事实记录） |
| 2026-11-11 | v1.11 | 启用 main 分支保护策略 A（PR + 必需检查 `test` + 0 审批 + 禁止强推/删除）；临时 PR #1 验证 PR CI 与 `test` 成功；CODEOWNERS 强制未启用 | 项目负责人 |
| 2026-11-11 | v1.12 | 完成 ENG-06：Provider 锁定/内嵌、每周检查、更新脚本、发布包与差异报告、回滚文档、tag 触发 Release；负责人批准 tag 触发与 GPL-3.0 内嵌再分发 | 项目负责人 |
| 2026-11-11 | v1.13 | 记录 PR #3 合并（`c3436d3`）、main CI 通过、Provider Check 远端触发、Windows UTF-8 编码修复（PR #5，`d4a7a4a`）与 issue 创建未验证；Release 仍未运行 | 项目负责人（事实记录） |
| 2026-11-11 | v1.14 | 记录 `v0.1.0` Release（run 42997351203）、资产下载校验与 Mihomo `-t`；记录 issue 创建验证（#6–#8 关闭）及 `SHA256SUMS` 资产覆盖限制 | 项目负责人（事实记录） |
| 2026-11-11 | v1.15 | 按负责人要求修正发布清单：`SHA256SUMS` 只覆盖 Release 上传的两个平台 zip；`release.py --verify` 仍校验目录结构与 zip 内副本；生成 `v0.1.1` | 项目负责人 |
| 2026-11-11 | v1.16 | 记录 `v0.1.1` 远端 Release（run 43003842864）、资产下载校验、干净构建复现与配置 `-t`；记录 `CONFIG-DIFF.md` 在 CI 干净检出中无上一版本基线的已知限制 | 项目负责人（事实记录） |
| 2026-11-11 | v1.17 | 新增 §13.5：本机 Clash Verge 全局扩展（固定组顺序、26 条规则、坏节点预检/剔除、备份与自动回滚）；记录 FIB 本机验证与限制；该能力不进入 Release | 项目负责人 |
| 2026-11-12 | v1.18 | 新增 Tailscale CGNAT 特殊层直连规则（`100.64.0.0/10`），规则总数 26→27；记录 MagicDNS 未纳入 Clash DNS、TUN 场景未实测 | 项目负责人（需求） |
| 2026-11-12 | v1.19 | 新增 §9.3 本机 DNS 泄漏护栏（C）：两条 Windows 出站阻断规则，阻断到 `192.168.2.0/24` 的 53；代码与单测完成，DSH Low Integrity 尚未应用，验收未完成 | 项目负责人（需求） |
| 2026-11-12 | v1.20 | 应用 §9.3 两条规则并记录实测：路由器 DNS 超时、TUN/223.5.5.5 返回 fake-IP、站点回归通过；修复 Windows 点分掩码匹配与 `dns-guard.cmd` 基础解释器选择；管理员 `check` 复核与回滚演练待完成 | 项目负责人（需求） |
| 2026-11-12 | v1.21 | 管理员 `dns-guard.cmd check` 通过（UDP/TCP/overall 均 OK，Exit code 0）；§9.3 与 §14 第 16 项更新；`--remove` 回滚演练仍待执行 | 项目负责人（事实记录） |
| 2026-11-12 | v1.22 | 完成 §9.3 `--remove` 回滚演练：移除后规则为空、`192.168.2.1:53` 恢复真实解析；重新应用后阻断、fake-IP 与站点回归恢复；泄漏窗口约 26 秒 | 项目负责人（事实记录） |
| 2026-11-12 | v1.23 | 按负责人 A 决策更新 §9.3：DNS 护栏放行受控解析器 `192.168.2.10:53`，地址改为 8 条 CIDR；旧 `/24` 规则仍生效，新规则待管理员重新应用；新增个人网络部署平台状态与 33 条规则说明 | 项目负责人（需求） |
| 2026-11-12 | v1.24 | 记录平台 PR #17（run 43233835411）CI 通过、本地 329 项测试通过；真实 Windows/OpenClash 部署仍未执行 | 项目负责人（事实记录） |
| 2026-11-13 | v1.25 | 记录 Windows 真实部署完成、OpenClash 代理认证改为一次性 `CLASH_PROXY_AUTH`（Q32）、349 项本地测试通过；OpenClash 验收仍未完成 | 项目负责人（事实记录） |
| 2026-11-13 | v1.26 | 记录 Windows/OpenClash 双平台真实部署与当前自动验收通过、356 项本地测试通过、A 决策 DNS 护栏已应用；Q32 一次性 UCI 读取例外；节点地区比对、回滚实机与人工项仍未关闭 | 项目负责人（事实记录） |
| 2026-11-13 | v1.27 | §13.3 `dns.fallback` 增加 `#PROXY`，修复中国大陆直连境外 DoH 超时导致 `DIRECT` 域名解析失败；已应用到真实 Windows Verge 并实测 | 项目负责人（缺陷修复） |
| 2026-11-13 | v1.28 | PR #18 合并为 `3cf7774`；OpenClash 设备重部署 `#PROXY` 新配置（run `20261113-195320-018656`，设备 `mihomo -t` 与部署内 verify 均通过，357 项测试复跑通过）；双平台遗留人工项未关闭 | 项目负责人（事实记录） |
