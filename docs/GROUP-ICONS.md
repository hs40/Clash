# 策略组图标（GROUP-ICONS）

**状态：** 2026-11-14 实现完成；负责人已确认改用 Qure PNG 图标集并确认 13 个图标映射。
**需求条款：** [REQUIREMENTS.md](REQUIREMENTS.md) §4.4。
**图标源文件：** [assets/icons/README.md](../assets/icons/README.md)。

## 1. 目标

在不改变策略组名称、成员与分流行为的前提下，让 Clash Verge / Mihomo 的策略组界面
可一眼区分「地区入口」与「业务组」。图标只影响展示，不参与任何规则匹配。

## 2. 机制

1. 图标是仓库内的 **PNG** 源文件，位于 `assets/icons/<名字>.png`
   （2026-11-14 负责人确认改用 PNG，不再使用 SVG）。
2. `configs/common/proxy-groups.yaml` 的每个组用 `icon: <名字>` 引用。
3. 构建期 `scripts/icons.py::load_icon` 读取文件、校验后内联为
   `data:image/png;base64,…`：
   - 构建产物 `dist/<platform>/config.yaml` 的 `icon` 字段；
   - Verge 全局脚本 `profiles/Script.js` 的 `MVP_GROUP_ICONS` 常量。
4. 产物不引用外网 URL，离线可用、可复现；升级图标只需替换 PNG 后重新构建。
5. 体积影响：13 枚彩色 PNG 合计 134 318 字节，base64 后约 179 KB；两份产物从
   约 2.30 MB 增至约 2.46 MB。

## 3. 校验（构建期，违反即失败）

| 检查 | 行为 |
| --- | --- |
| 名称合法 | 必须匹配 `^[a-z0-9][a-z0-9-]*$` |
| 文件存在 | 缺失时抛 `ConfigError`：`策略组 '<组名>' 的图标无效：…` |
| 大小上限 | 单个 PNG ≤ 16 KiB |
| 内容类型 | 必须以 PNG 签名 `\x89PNG\r\n\x1a\n` 开头 |
| 组类型 | 测速型组必须有 http(s) `url`；`select` 组不得有 `url` |

对应测试：`tests/test_groups.py` 的 `test_non_png_icon_is_rejected`、
`test_oversized_icon_is_rejected`、`test_missing_icon_file_is_rejected`、
`test_invalid_icon_name_is_rejected`、`test_icons_are_png_sources_on_disk`。

## 4. 图标清单与许可

图标取自 <https://github.com/blackmatrix7/ios_rule_script/tree/master/icon/qure/color>
（上游 <https://github.com/Koolson/Qure>，144×144 彩色 PNG）。

| 策略组 | 文件 | 上游文件 | 图形 | 许可 |
| --- | --- | --- | --- | --- |
| PROXY | `proxy.png` | `Proxy.png` | 双层箭头 | Qure（见下方声明） |
| Google | `google.png` | `Google.png` | Google 彩色字标 | Qure 备份，商标归 Google |
| OpenAI | `openai.png` | `Bot.png` | 机器人 | Qure |
| Claude | `claude.png` | `Magic.png` | 魔术棒 | Qure |
| Cursor | `cursor.png` | `Lab.png` | 烧瓶 | Qure |
| 自动选择 | `auto.png` | `Auto.png` | 闪电 | Qure |
| 香港节点 | `hk.png` | `HK.png` | HK 字样 | Qure |
| 台湾节点 | `tw.png` | `TW.png` | TW 字样 | Qure |
| 日本节点 | `jp.png` | `JP.png` | JP 字样 | Qure |
| 韩国节点 | `kr.png` | `KR.png` | KR 字样 | Qure |
| 狮城节点 | `sg.png` | `SG.png` | SG 字样 | Qure |
| 美国节点 | `us.png` | `US.png` | US 字样 | Qure |
| 其他节点 | `other.png` | `Area.png` | 地球+指针 | Qure |

**许可与来源声明**：Qure 项目**没有开源许可证**，其 README 声明图标/LOGO 版权归原作者
及商标所属方所有，仅用于资源共享与学习参考、**禁止商用**、转载请注明出处；
blackmatrix7 的 `icon/qure` 是上游的**单向备份**。本项目为个人非商业自用，
仅在仓库内保存副本并内联进自建配置；权利人若认为不当，可通过 Issue 要求删除。
负责人已于 2026-11-14 接受该前提。

**映射确认（2026-11-14 负责人确认）**：Qure 中没有 OpenAI / Claude / Cursor 品牌图标，
三组改用三个**可区分的中性图形**——OpenAI → `Bot`、Claude → `Magic`、Cursor → `Lab`，
不冒充任何品牌标志。地区组用字母缩写徽标（`HK`/`TW`/`JP`/`KR`/`SG`/`US`），
功能组（PROXY/自动选择/其他节点）用中性图形。

## 5. 来源可核验性

- 13 个文件下载自 `raw.githubusercontent.com`，与上游 git blob 的 SHA-1 逐一比对一致；
  字节数与 SHA-256 前缀登记在 [assets/icons/README.md](../assets/icons/README.md)。
- 复核方式：`Get-FileHash assets/icons/*.png -Algorithm SHA256`。

## 6. 验收方式

- 单元测试：`tests/test_groups.py`（13 组全部带 PNG data URI，且解码后以 PNG 签名开头、
  ≤ 16 KiB；仓库内不再有 `.svg`；缺文件/非法名/非 PNG/超限被拒）、
  `tests/test_verge_global.py`（Script 内嵌 13 个图标且组顺序不变）。
- 构建检查：`py scripts/build.py --platform all` 后用 Mihomo `-t` 校验产物。
- 界面检查：部署后在 Clash Verge 策略组页面确认图标显示（需单独授权部署后执行）。
- 已知限制：图标渲染尺寸由客户端固定为 32×32；不验证各客户端的缓存行为。

## 7. 新增或替换图标的步骤

1. 把 PNG 放进 `assets/icons/`，文件名即 `icon` 取值（小写字母、数字、连字符）。
2. 在 `assets/icons/README.md` 与本文档 §4 登记图形、来源、许可。
3. 如新增策略组，在 `configs/common/proxy-groups.yaml` 写 `icon: <名字>`。
4. 跑 `py -m unittest discover -s tests` 与 `py scripts/build.py --platform all`。
5. 图标属于对外可见变更：替换前先给负责人确认预览，再提交 PR。
