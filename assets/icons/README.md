# 策略组图标（assets/icons）

Mihomo / Clash Verge 支持在 `proxy-groups` 上用 `icon` 字段显示图标（32×32，圆角）。
本目录保存图标的 **PNG 源文件**；构建时由 `scripts/icons.py` 内联为
`data:image/png;base64,…`，因此产物不依赖网络、可复现、可离线部署。

**2026-11-14 负责人确认：改用 PNG（Qure 图标集），不再使用 SVG。**
**2026-11-14 负责人确认：六个地区组使用国家/地区旗帜图标（替换原字母徽标）。**

## 图标集来源

- 取用仓库：<https://github.com/blackmatrix7/ios_rule_script/tree/master/icon/qure>
  的 **`color/`（彩色）** 子目录。
- 上游作者：<https://github.com/Koolson/Qure>（README 声明「转载请注明出处」）。
- 备份说明（取自 blackmatrix7 的 `icon/README.md`）：该目录是上游图标集的**单向备份**，
  目的是避免原作者删图导致链接失效；备份不审核内容合法性。
- 文件为上游 `IconSet/Color` 的 144×144 PNG，本项目未做任何重绘或改色。

## 版权与免责声明

1. Qure 项目**没有开源许可证**；其 README 声明：图标与 LOGO 的版权归原作者及商标所属的
   个人/组织，**仅用于资源共享与学习参考，不得商用或牟利**，转载请注明出处。
2. 本项目为**个人非商业自用配置工程**，仅在仓库内保存图标副本并内联进自建配置，
   不对图标主张任何权利，也不再分发为独立图标产品。
3. 若权利人认为本仓库的图标副本不当，请通过 Issue 告知，将立即删除。
4. 图标只影响展示，**不参与任何分流、规则匹配或安全决策**。

## 文件与用途

文件名即 `proxy-groups.yaml` 中 `icon:` 的取值。上游文件名与用途的对应关系：

| 文件 | 用于策略组 | 上游文件 | 字节 | SHA-256（前 16 位） |
| --- | --- | --- | --- | --- |
| `proxy.png` | PROXY | `Proxy.png` | 12999 | `56f5e40b72a4279c…` |
| `google.png` | Google | `Google.png` | 6646 | `c815cd27d60bff0a…` |
| `openai.png` | OpenAI | `Bot.png` | 8739 | `1afccc81c40414ef…` |
| `claude.png` | Claude | `Magic.png` | 11147 | `583391e7473f9137…` |
| `cursor.png` | Cursor | `Lab.png` | 8851 | `a1b60d44cd429530…` |
| `auto.png` | 自动选择 | `Auto.png` | 7081 | `ca2161622dcc61e6…` |
| `hk.png` | 香港节点 | `Hong_Kong.png` | 11854 | `eacee82c61b21e7a…` |
| `tw.png` | 台湾节点 | `Taiwan.png` | 11037 | `80da8b480bc7e85f…` |
| `jp.png` | 日本节点 | `Japan.png` | 8754 | `59e351aab014850c…` |
| `kr.png` | 韩国节点 | `Korea.png` | 10961 | `2612736989c0932b…` |
| `sg.png` | 狮城节点 | `Singapore.png` | 9416 | `192249f402998130…` |
| `us.png` | 美国节点 | `United_States.png` | 12522 | `63d7c028ea386260…` |
| `other.png` | 其他节点 | `Area.png` | 14450 | `b22c0411bc69bcfd…` |

**关于地区组**：六个地区组使用 Qure 的**国家/地区旗帜**图标（`Hong_Kong`/`Taiwan`/`Japan`/
`Korea`/`Singapore`/`United_States`），2026-11-14 负责人指示「六地区→使用国家旗帜」；
原字母徽标 `HK`/`TW`/`JP`/`KR`/`SG`/`US` 已弃用。旗帜图形不涉及额外授权，版权同属 Qure 声明。

**关于 AI 三组**：Qure 图标集中没有 OpenAI / Claude / Cursor 的品牌图标，因此改用三个
**可区分的中性图形**（2026-11-14 负责人确认）：OpenAI → `Bot`、Claude → `Magic`、
Cursor → `Lab`。它们不冒充任何品牌标志。

完整 SHA-256 可用 `Get-FileHash assets/icons/<名字>.png -Algorithm SHA256` 复核；
下载副本与上游 git blob 的 SHA-1 已逐一比对一致（见 `docs/GROUP-ICONS.md` §4）。

## 约束

- 文件名即 `proxy-groups.yaml` 中 `icon:` 的取值，只允许小写字母、数字与连字符。
- 只接受 PNG 签名（`\x89PNG\r\n\x1a\n`）开头的二进制，单个文件不超过 16 KiB
  （构建期校验，超限或格式不符即失败）。
- 图标只影响展示，不参与分流；替换图标不得改变策略组名称与成员
  （`docs/REQUIREMENTS.md` §4.1、§4.4）。
- 新增图标必须同时登记来源与许可，并在 `docs/REQUIREMENTS.md` §4.4 的清单中登记。
