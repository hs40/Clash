# 策略组图标（assets/icons）

Mihomo / Clash Verge 支持在 `proxy-groups` 上用 `icon` 字段显示图标（32×32，圆角）。
本目录保存图标的 **SVG 源文件**；构建时由 `scripts/icons.py` 内联为
`data:image/svg+xml;base64,…`，因此产物不依赖网络、可复现、可离线部署。

## 文件与用途

| 文件 | 用于策略组 | 图形 | 来源 / 许可 |
| --- | --- | --- | --- |
| `hk.svg` | 香港节点 | 香港区旗 | [flag-icons](https://github.com/lipis/flag-icons)（MIT） |
| `tw.svg` | 台湾节点 | 中华民国旗 | flag-icons（MIT） |
| `jp.svg` | 日本节点 | 日本国旗 | flag-icons（MIT） |
| `kr.svg` | 韩国节点 | 韩国国旗 | flag-icons（MIT） |
| `sg.svg` | 狮城节点 | 新加坡国旗 | flag-icons（MIT） |
| `us.svg` | 美国节点 | 美国国旗 | flag-icons（MIT） |
| `other.svg` | 其他节点 | 地球（public） | [Material Symbols](https://github.com/google/material-design-icons)（Apache-2.0） |
| `auto.svg` | 自动选择 | 闪电（bolt） | Material Symbols（Apache-2.0） |
| `proxy.svg` | PROXY | 路由（alt_route） | Material Symbols（Apache-2.0） |
| `google.svg` | Google | Google 标志 | [simple-icons](https://github.com/simple-icons/simple-icons)（CC0-1.0） |
| `openai.svg` | OpenAI | OpenAI 标志 | simple-icons v13.0.0（CC0-1.0） |
| `claude.svg` | Claude | Anthropic 标志 | simple-icons（CC0-1.0） |
| `cursor.svg` | Cursor | Cursor 标志 | simple-icons（CC0-1.0） |

## 配色（2026-11-14 负责人确认方案 B）

单色图标在上游是纯黑，暗色主题下不可见，因此写入时给 `<svg>` 根元素加 `fill`：

| 图标 | fill | 说明 |
| --- | --- | --- |
| `google.svg` | `#4285F4` | Google 品牌蓝 |
| `openai.svg` | `#10A37F` | OpenAI 品牌绿 |
| `claude.svg` | `#D97757` | Anthropic 品牌橙 |
| `cursor.svg` | `#6E7681` | Cursor 无官方主色，用中性灰 |
| `proxy.svg`、`auto.svg`、`other.svg` | `#6E7681` | 功能组统一中性灰 |
| 六个国旗 | 上游原色 | flag-icons 自带配色 |

中性灰 `#6E7681` 在 Verge 暗色与亮色主题下均可见；替换颜色属于对外可见变更，需先给负责人确认预览。

## 约束

- 文件名即 `proxy-groups.yaml` 中 `icon:` 的取值，只允许小写字母、数字与连字符。
- 只接受 `<svg` 开头的文本，单个文件不超过 16 KiB（构建期校验，超限即失败）。
- 图标只影响展示，不参与分流；替换图标不得改变策略组名称与成员（`docs/REQUIREMENTS.md` §4.1、§4.4）。
- 新增图标必须同时登记来源与许可，并在 `docs/REQUIREMENTS.md` §4.4 的清单中登记。
