# iPhone / QuantumultX 配置使用说明

> 适用平台：iPhone 上的 QuantumultX（iOS App）。**非 Mihomo 内核**，配置是分节 INI，
> 闭源 App 无 CLI、**无 `mihomo -t` 离线校验**。质量模型是 `scripts/build_quanx.py`
> 内的 `validate_quantx()` 结构校验，详见 `docs/REQUIREMENTS.md` §13.6。

## 1. 手机导入

1. 在 iPhone QuantumultX 中通过「配置 → 下载配置」导入下面固定地址：

   ```text
   https://raw.githubusercontent.com/hs40/Clash/main/quantumultx/QuanX.conf
   ```

2. 该文件是仓库内**固定路径产物**（`quantumultx/QuanX.conf`），由
   `configs/quantumultx/platform.conf` + `scripts/build_quanx.py` 机械生成。
   CI 用 `python scripts/build_quanx.py --check` 守卫「重新构建结果 == 入库文件」逐字节一致。
   它是「源文件入库、产物不入库」原则的唯一破例：**不走 GitHub Release**，`dist/` 仍被 gitignore。

## 2. 证书与订阅必须自行补（重要）

按 Q3/Q5 与安全边界，配置**不含**任何真实凭据：

- `[mitm]` 不含证书与口令两行（`p12` / `passphrase`），只保留 `hostname` 跳过列表；
- `[server_remote]` / `[server_local]` 为空段，不含 `?clash=` 订阅 URL；
- `security_scan.py` 已把 `.conf` 纳入扫描，`validate_quantx()` 亦全域拒凭据。

导入**不含证书两行**的配置是否清除手机上已安装的 MITM 证书，未离线验证【待核验】。
负责人已确认采用下面顺序（m18564）：

1. 先导入本配置；
2. 从旧配置复制证书与口令两行，手工粘贴到新 `[mitm]` 段；
   （或在 App 内重新生成并信任证书）；
3. **重启代理**。30 条 `[rewrite_remote]` 重写必须先补证书两行、重启后才生效（Q6=B）。

节点订阅同样由手机端 QuantumultX 自行导入；本工程不代填、不代改用户设备。

## 3. 配置结构（12 组 / 21 条内联规则）

| 段 | 内容 |
| --- | --- |
| `[general]` | `server_check_url`(http)、`server_check_timeout=3000`、`excluded_routes`、`dns_exclusion_list`、`udp_drop_list = 443, STUN, QUIC` 全部原样保留手机现状 |
| `[dns]` | `no-ipv6` + `no-system` + UDP DNS + 4 条域名 `server` + `alias`，不改 DoH |
| `[policy]` | 12 组：`节点选择` / `自动选择` / 7 地区组（香港、台湾、日本、韩国、狮城、美国、其他节点）/ `全球加速` / `苹果服务` / `兜底分流` |
| `[filter_local]` | 21 条（special 8 + Apple 3 + 金融 4 + base 4 近似 + BT 1 + `final, 兜底分流`） |
| `[filter_remote]` | 9 条（已删 Spotify音乐 / 国际媒体 / 哔哩哔哩 3 条 `enabled=false` 悬空规则） |
| `[rewrite_remote]` | 30 条公开 URL，原样照搬 |
| `[task_local]` / `[http_backend]` | 原样照搬 |
| `[mitm]` | `skip_validating_cert` / `force_sni_domain_name` / `hostname` 跳过列表 + 证书说明注释 |

7 地区组的 `server-tag-regex` 由 `scripts/regions.py` 的关键词表**机械生成**（先命中优先），
与 `classify_node()` 交叉验证；不手写地区正则。自动组统一 `check-interval=1200`、`tolerance=50`。

**策略组图标（2026-11-15 负责人「按原代码添加图标」+「归位+补齐」）**：`[policy]` 12 组每行
末尾都带 `img-url=`，9 个原有组逐行照抄现用 `QuanX.conf`（Koolson/Qure 的 `Apple/Auto` +
Orz-3/mini 的 `Global/Final/HK/TW/JP/SG/US`），新增/归位三组为：`韩国节点` = Orz-3 `KR.png`、
`其他节点` = Qure `World_Map.png`（原配置把韩国旗错挂在「其他节点」，现归位）、`节点选择` = Qure `Proxy.png`。
12 个 URL 已实测返回有效 PNG（200 / `image/png`）；单一数据源为 `build_quanx.POLICY_ICONS`，
`validate_quantx()` 逐组校验「有且仅有一个约定图标」，缺图标/错图标即构建失败。图标只影响展示，
不参与分流；远程 URL 沿用 Q15「上游不锁 SHA-256」约定，不再引入 `assets/` 依赖。

## 4. 已知降级与【待核验】（不得写成已验证）

- **无核心分流回退**：QuanX 的 `available` 只接受节点、不可嵌套策略组，故**不建**
  Google/OpenAI/Claude/Cursor。AI 流量由远程 `Ai-All-In-One` 列表打向 `美国节点`；
  Google 由「全球加速」列表承接。iPhone 上**没有**「美国优先自动回退」。
- **国内直连近似**：`GEOIP,LAN` / `RULE-SET,geosite-*` 在 QuanX 侧以 `ip-cidr` 私网段
  + `geoip, cn, direct` + 现有「国内网站」(VirgilClyne `ASN.China.list`) 订阅近似；
  未引入 blackmatrix7 `China.list`，零新增依赖。
- **上游不锁哈希**：`[filter_remote]` / `[rewrite_remote]` 引用 QuanX 原生上游公开 URL，
  **不锁 SHA-256**（与本项目 Mihomo 侧 Provider 锁定机制不同），上游随时可变，本工程只校验结构。
- **保留字改名**：`PROXY` 改为 `节点选择`，避开 QuanX 内置保留字 `proxy`/`direct`/`reject`；
  是否会在真机静默直连【待核验】。
- **正则兼容性**：生成的 `server-tag-regex` 含 `(?i)`、先行/后行断言，QuanX 使用的
  ICU/NSRegularExpression 是否全部支持【待核验】。
- **证书与重写**：导入是否清除已装证书、QuanX 对不存在 `force-policy` 名的行为、
  30 条重写补证书后是否全部生效，均【待核验】。
- **副作用**：`udp_drop_list = 443, STUN, QUIC` 会丢弃 443/QUIC/STUN 的 UDP，
  可能影响 QUIC/游戏语音【待核验】；这是手机现状，按 Q24 原样保留。
- 自动化测试**不替代**真机连通性、DNS 分流与节点枚举验证。
- **图标显示**：12 组 `img-url=` 已实测服务端返回 200 / `image/png`，但手机端能否实际加载显示【待核验】；图标只展示、不参与分流。

## 5. 本地重建与校验

```powershell
.venv\Scripts\python.exe scripts\build_quanx.py --out quantumultx
.venv\Scripts\python.exe scripts\build_quanx.py --check
.venv\Scripts\python.exe scripts\ci_report.py --output ci-report.md
```

- `--out DIR`：写 `DIR/QuanX.conf`（默认目标 `quantumultx/QuanX.conf`）。
- `--root DIR`：从指定根目录读模板（测试夹具用）。
- `--check`：重新构建并与入库产物逐字节比较，不一致退出 1。**不参与** `build.py --platform all`。

## 6. 边界

不修改用户真实设备；不提交真实凭据；不伪造节点、订阅或测试结果；
高风险安全策略、核心分流规则与正式发布变更仍须项目负责人审查。
