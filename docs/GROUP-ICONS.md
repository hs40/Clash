# 策略组图标（GROUP-ICONS）

**状态：** 2026-11-14 实现完成，等待负责人对 13 个图标逐个确认后提交 PR。
**需求条款：** [REQUIREMENTS.md](REQUIREMENTS.md) §4.4。
**图标源文件：** [assets/icons/README.md](../assets/icons/README.md)。

## 1. 目标

在不改变策略组名称、成员与分流行为的前提下，让 Clash Verge / Mihomo 的策略组界面
可一眼区分「地区入口」与「业务组」。图标只影响展示，不参与任何规则匹配。

## 2. 机制

1. 图标是仓库内的 SVG 源文件，位于 `assets/icons/<名字>.svg`。
2. `configs/common/proxy-groups.yaml` 的每个组用 `icon: <名字>` 引用。
3. 构建期 `scripts/icons.py::load_icon` 读取文件、校验后内联为
   `data:image/svg+xml;base64,…`：
   - 构建产物 `dist/<platform>/config.yaml` 的 `icon` 字段；
   - Verge 全局脚本 `profiles/Script.js` 的 `MVP_GROUP_ICONS` 常量。
4. 产物不引用外网 URL，离线可用、可复现；升级图标只需替换 SVG 后重新构建。

## 3. 校验（构建期，违反即失败）

| 检查 | 行为 |
| --- | --- |
| 名称合法 | 必须匹配 `^[a-z0-9][a-z0-9-]*$` |
| 文件存在 | 缺失时抛 `ConfigError`：`策略组 '<组名>' 的图标无效：…` |
| 大小上限 | 单个 SVG ≤ 16 KiB |
| 内容类型 | UTF-8 文本且以 `<svg` 开头 |
| 组类型 | 测速型组必须有 http(s) `url`；`select` 组不得有 `url` |

## 4. 图标清单与许可

| 策略组 | 文件 | 图形 | 来源 | 许可 |
| --- | --- | --- | --- | --- |
| PROXY | `proxy.svg` | 路由 | Material Symbols `alt_route` | Apache-2.0 |
| Google | `google.svg` | Google 标志 | simple-icons | CC0-1.0 |
| OpenAI | `openai.svg` | OpenAI 标志 | simple-icons 13.0.0 | CC0-1.0 |
| Claude | `claude.svg` | Anthropic 标志 | simple-icons | CC0-1.0 |
| Cursor | `cursor.svg` | Cursor 标志 | simple-icons | CC0-1.0 |
| 自动选择 | `auto.svg` | 闪电 | Material Symbols `bolt` | Apache-2.0 |
| 香港节点 | `hk.svg` | 香港区旗 | flag-icons 4x3 | MIT |
| 台湾节点 | `tw.svg` | 中华民国旗 | flag-icons 4x3 | MIT |
| 日本节点 | `jp.svg` | 日本国旗 | flag-icons 4x3 | MIT |
| 韩国节点 | `kr.svg` | 韩国国旗 | flag-icons 4x3 | MIT |
| 狮城节点 | `sg.svg` | 新加坡国旗 | flag-icons 4x3 | MIT |
| 美国节点 | `us.svg` | 美国国旗 | flag-icons 4x3 | MIT |
| 其他节点 | `other.svg` | 地球 | Material Symbols `public` | Apache-2.0 |

风格约定（2026-11-14 负责人确认）：地区组用国旗，功能组用中性图形，
Google/OpenAI/Claude/Cursor 用品牌标志。

配色（2026-11-14 负责人确认方案 B）：上游单色图标是纯黑，暗色主题下不可见，
因此源文件写入时在 `<svg>` 根元素加 `fill`——Google `#4285F4`、OpenAI `#10A37F`、
Claude `#D97757`；Cursor 无官方主色，与功能组（PROXY/自动选择/其他节点）统一用中性灰
`#6E7681`；六个国旗保留上游原色。

## 5. 验收方式

- 单元测试：`tests/test_groups.py`（13 组全部带 data URI；缺文件/非法名被拒）、
  `tests/test_verge_global.py`（Script 内嵌 13 个图标且组顺序不变）。
- 构建检查：`py scripts/build.py --platform all` 后用 Mihomo `-t` 校验产物。
- 界面检查：部署后在 Clash Verge 策略组页面确认图标显示（需负责人确认预览图后执行）。
- 已知限制：图标渲染尺寸由客户端固定为 32×32；不验证各客户端的缓存行为。

## 6. 新增或替换图标的步骤

1. 把 SVG 放进 `assets/icons/`，文件名即 `icon` 取值。
2. 在 `assets/icons/README.md` 与本文档 §4 登记图形、来源、许可。
3. 如新增策略组，在 `configs/common/proxy-groups.yaml` 写 `icon: <名字>`。
4. 跑 `py -m unittest discover -s tests` 与 `py scripts/build.py --platform all`。
5. 图标属于对外可见变更：替换前先给负责人确认预览，再提交 PR。
