# dsh-pocket 移动端布局补丁

本文记录本机 DSH Desktop 的 dsh-pocket 插件兼容性问题的根因、本地补丁、
可重复工具与验收结果。该补丁只修改本机插件文件，不属于 Clash 配置，
不进入 `dist/` 或 Release，也不改变任何网络、DNS、防火墙或设备设置。

## 1. 现象与根因

DSH Desktop 0.2.2-rc.1 在窄视口（<768 CSS px）下会在
`[data-mobile-nav="frame"]` 的第一个子元素位置插入
`div[data-sidebar-mask]` 遮罩。dsh-pocket 2.12.0 仍用
`:first-child` / `:nth-child(2)` 定位侧边栏与正文列，于是：

- 遮罩被当成侧边栏；
- 真正的侧边栏被当成正文列；
- 正文列宽度变为 0，登录后页面能打开但会话区域白屏。

这不是代理、TUN 或 WebSocket 故障：局域网入口和
`/api/remote.mux` 在修复前即可建立连接；问题在客户端 DOM 选择器。

上游 issue #208、#209 仍为 OPEN，相关 PR #200 尚未发布。本仓库不等待
上游发布，使用可重复的本地补丁。

## 2. 补丁内容

补丁文件 `scripts/dsh_pocket_patch.py` 对 dsh-pocket 客户端 bundle 做
以下精确替换：

| 用途 | 旧选择器 | 新选择器 |
| --- | --- | --- |
| 抽屉元素 | `[data-mobile-nav="frame"] > :first-child` | `[data-mobile-nav="frame"] > [class*="_sidebarCol"]` |
| 切换按钮 | `[data-mobile-nav="toggle"]` | `[data-mobile-nav="toggle"], [data-sidebar-opener]` |
| 正文列 CSS | `[data-mobile-nav="frame"] > :nth-child(2)` | `[data-mobile-nav="frame"] > [class*="_centerCol"]` |
| 抽屉 CSS | `[data-mobile-nav="frame"] > :first-child` | `[data-mobile-nav="frame"] > [class*="_sidebarCol"]` |
| 展开态 CSS | `... > :first-child` | `... > [class*="_sidebarCol"]` |

同时新增隐藏规则：

```css
[data-mobile-nav="frame"] > [data-sidebar-mask] {
  display: none !important;
}
```

工具会校验每个旧标记必须恰好出现一次；如果 bundle 结构已变化，拒绝修改
并返回退出码 2，不会猜着改。若检测到早期补丁留下的错误选择器
`[data-sidebar-opener"]`（多一个引号，会导致 `closest()` 语法错误），
会先修复该标记。

## 3. 当前文件状态（2026-11-12）

- 实际文件：
  `C:/Users/Administrator/.dsh/profiles/desktop/node_modules/dsh-pocket/client/client.js`
- 大小：141,329 字节
- SHA-256：`4A21452B19FC4DA5D1D19ED75DEE8C40B2C7C42467BDC5BA52E4F6E15E05FE8E`
- 文件类型：普通文件；补丁时已断开 pnpm 硬链接，后续插件升级会覆盖，
  需要重新打补丁。
- 目标目录当前没有 `client.js.pre-dsh-pocket-patch.bak`：本次修复是直接写入
  已损坏的补丁文件，工具只在 `--apply` 一个未打补丁的文件时创建该备份。
- 仓库内的原始参考备份：`.tmp_dsh_pocket_client.js.bak`，140,981 字节，
  SHA-256 `DBB2B609F2611A96C7BE30F18D52683992B652AB1601D10E2292341A8DB25FBC`。
  该文件在 `.gitignore` 的 `.tmp_*` 范围内，不提交。
- pnpm store 中对应文件仍为原始 140,981 字节，未被补丁污染。

当前检查：

```powershell
.venv\Scripts\python.exe scripts\dsh_pocket_patch.py --check
# dsh-pocket client: patched
# exit 0
```

JS 语法检查（本机 PATH 中没有 node，使用 DSH 自带 Node）：

```powershell
& 'C:/Users/Administrator/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe' --check 'C:/Users/Administrator/.dsh/profiles/desktop/node_modules/dsh-pocket/client/client.js'
# exit 0
```

## 4. 工具用法

```powershell
# 默认动作：只检查，不写文件
.venv\Scripts\python.exe scripts\dsh_pocket_patch.py --check

# 打补丁；--node-check 需要 node 在 PATH 中，当前本机请用上面的自带 node
.venv\Scripts\python.exe scripts\dsh_pocket_patch.py --apply

# 自定义目标文件或备份路径
.venv\Scripts\python.exe scripts\dsh_pocket_patch.py --file <client.js> --backup <bak> --apply

# 从备份恢复
.venv\Scripts\python.exe scripts\dsh_pocket_patch.py --restore
```

退出码：

- 0：已打补丁（或 apply/restore 成功）；
- 1：未打补丁，或检测到需要修复的旧标记；
- 2：目标布局不受支持、读取/写入失败、参数错误。

## 5. 验收记录

- `--check`：patched，退出码 0。
- Node `--check`：退出码 0（使用 DSH 自带 Node）。
- 局域网入口 `http://192.168.2.8:3081/`：HTTP 200，登录页正常返回。
- Tailscale 入口 `http://100.66.234.80:3081/`：HTTP 200，登录页正常返回。
- 带 PIN 的认证会话与 `/api/remote.mux` 数据面未在本次验收中重新测试；
  不把未完成的项写成通过。测试未使用、未索取任何 PIN 或 token。

## 6. 升级与恢复流程

1. 升级 dsh-pocket 后先运行 `--check`。
2. 若输出 `not patched` 或退出码 1，运行 `--apply`。
3. 关闭 dsh-pocket 页面后重新打开；若仍是旧界面，重启 DSH Desktop，
   让客户端 bundle 重新加载。
4. 若页面异常，若目标目录存在工具备份则运行 `--restore`；否则用
   `--backup F:/WorkBuddy AI/Clash/.tmp_dsh_pocket_client.js.bak --restore`
   恢复原始文件，再重启 DSH。
5. 上游发布包含修复的版本后，优先升级上游并删除本地补丁；不要长期
   维护分叉。

## 7. 限制

- 补丁依赖当前 dsh-pocket 的类名与 DOM 结构；上游改版会使标记校验失败，
  工具会安全拒绝而不是猜测。
- 插件升级会覆盖 `node_modules` 中的文件，补丁不会自动迁移。
- 本仓库不包含 dsh-pocket 源码，也不修改 npm 包发布内容。
- 未做自动化浏览器回归；验收是文件级与入口 HTTP 级；修复后的页面级复测待负责人完成。
- 该补丁与 Clash 配置、DNS 护栏、Verge/OpenClash 部署无关。
