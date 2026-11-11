# 第三方数据声明

本项目发布的 Clash/Mihomo 配置内嵌了以下第三方数据，特此声明。

## MetaCubeX/meta-rules-dat

- 项目：https://github.com/MetaCubeX/meta-rules-dat
- 用途：仅使用 `geosite private` 与 `geosite cn` 两个 domain 规则集。
- 锁定版本：`458e716abd80ff8c6aee2b7d15c4f94b20e9d279`（`meta` 分支）。
- 原始文件：
  - `geo/geosite/private.list`
  - `geo/geosite/cn.list`
- 许可证：GNU General Public License v3.0（GPL-3.0）。
- 许可证全文：`providers/LICENSE-metacubex.txt`；发布包中随附该文件。
- 修改说明：构建时把上述列表去除注释和空行后内嵌为 Mihomo inline rule-provider；
  未改变条目内容，也未把第三方数据用于本项目自身的许可证声明之外。

上述数据仍受其原始许可证约束；本项目的其他代码与配置不因引用该数据而改变许可证。
