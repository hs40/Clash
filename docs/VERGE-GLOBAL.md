# Clash Verge 全局 MVP 复用（本机部署辅助）

状态：2026-11-11 已在本机 Clash Verge Rev 2.5.10 + FIB 订阅上验证。
该能力是**本机部署辅助**，不进入 dist/、GitHub Release 或 OpenClash 配置；
仓库的正式构建契约仍以 [REQUIREMENTS.md](REQUIREMENTS.md) §11 为准。

## 1. 目标与边界

目标：把仓库的 MVP 设置套用到 Clash Verge 的**所有订阅**，订阅更新或切换后不必
重新生成本地 profile。

- 适用于订阅自身提供 inline proxies 的情况；遇到 proxy-providers 会中止，不猜测
  远程节点清单。
- 只写 Verge AppData 下的全局 profiles/Merge.yaml、profiles/Script.js、
  profiles.yaml 与 verge.yaml；FIB 订阅文件、订阅 URL、系统 DNS、hosts、路由和
  防火墙均不改。
- 不写入真实凭据；生成文件中只有仓库的占位节点与 Provider 数据。
- 坏节点采用**运行时过滤 + 预检剔除**，不建立永久黑名单；节点修复后会自动恢复。
- 旧本地 profile mvpClash0001 保留为回退，不自动删除。

## 2. 架构与数据流

    subscription (inline proxies)
      -> Verge app settings (mixed-port / TUN ...)
      -> global Merge.yaml (profile.store-selected + 2 inline providers)
      -> global Script.js (filter, 13 groups, 27 rules, MVP DNS)
      -> Verge runtime clash-verge.yaml

### 2.1 全局 Merge.yaml

只包含：

- profile.store-selected: true
- rule-providers：geosite-cn、geosite-private，均为仓库锁定的 inline 数据

不写 proxies、proxy-groups、rules 或订阅专属 Provider。

### 2.2 全局 Script.js

main(config, profileName) 对当前订阅执行：

- 删除订阅自带的 proxy-groups、rules、dns 与多余 rule-providers；
- 只保留 geosite-cn、geosite-private；
- 过滤 reality-opts.short-id 不是 8/16 位十六进制的节点；
- 强制 mixed-port: 7897，删除订阅的 port / socks-port，设置
  mode: rule、ipv6: false、allow-lan: false；
- 保留 Verge 注入的 tun、external-controller、secret 与 profile；
- 生成固定 13 个策略组、27 条规则和仓库 DNS。

不写 tun、external-controller、secret；这些键由 Verge 管理。

## 3. 固定策略组顺序

负责人 2026-11-11 固定，顺序不可调整：

| 序号 | 组名 | 类型 | 成员 |
| --- | --- | --- | --- |
| 1 | PROXY | select | 自动选择、香港节点、台湾节点、日本节点、韩国节点、狮城节点、美国节点、其他节点、DIRECT |
| 2 | Google | fallback | 美国节点 -> 狮城节点 -> 日本节点 -> 香港节点 |
| 3 | OpenAI | select | 自动选择、七个地区组 |
| 4 | Claude | select | 自动选择、七个地区组 |
| 5 | Cursor | select | 自动选择、七个地区组 |
| 6 | 自动选择 | url-test | 全部可用节点 |
| 7-13 | 香港/台湾/日本/韩国/狮城/美国/其他节点 | select | 按 scripts/regions.py 识别 |

自动选择使用 https://www.gstatic.com/generate_204，interval: 300，
tolerance: 50。地区关键词与构建器共用同一个 scripts/regions.py；空地区回退到
自动选择。

规则共 27 条：特殊 2 条、业务 20 条、基础 4 条、兜底 1 条，最后一条唯一为
MATCH,PROXY。

## 4. 节点预检与剔除

预检分两步：

1. 静态过滤：reality-opts.short-id 存在且不是 8/16 位十六进制的节点；
2. 逐节点执行 mihomo -t，发现静态规则覆盖不到的问题。

任一步失败都会把节点从可用集合剔除；全部节点不可用时中止迁移。额外坏节点写入
Script 的标记块：

    /* MVP-EXCLUDED-BEGIN */
    var MVP_EXCLUDED = { "FIB": ["节点名"] };
    /* MVP-EXCLUDED-END */

该块每次预检重写，只保留当前仍坏的节点；不保存完整原始节点清单，也不建立永久黑名单。
节点修复后会自然回到策略组。

## 5. 备份、应用与回滚

### 5.1 备份内容

scripts/verge_apply.py 在任何写入前备份以下文件到时间戳目录：

- profiles/Merge.yaml
- profiles/Script.js
- profiles.yaml
- verge.yaml
- config.yaml
- clash-verge.yaml

同目录生成 manifest.yaml，记录每个文件的 SHA-256 与字节数。备份目录位于工作区
.tmp_verge_apply_backup_<时间戳>，已被 .gitignore 的 .tmp_* 覆盖，不提交。

### 5.2 应用

双击仓库根目录的 verge-sync.cmd，或在管理员终端执行。脚本会：

1. 预检当前（或指定 UID）的订阅；
2. 生成全局 Merge/Script；
3. 备份；
4. 原子写入两个全局文件并切换 current；
5. 保留 enable_tun_mode、enable_system_proxy、verge_mixed_port 三项设置；
6. 结束 Verge UI 与核心，再用计划任务启动 Verge；
7. 等待 clash-verge.yaml 重新生成并校验；失败自动恢复六个备份文件并重启。

    REM 管理员权限；默认当前 profile
    verge-sync.cmd

    REM 指定订阅 UID
    verge-sync.cmd RUU8zmQ6FdJF

只生成、不写 AppData（dry-run）：

    $env:PYTHONPATH=(Resolve-Path '.venv\Lib\site-packages').Path
    & 'D:\Programs\Python\python.exe' scripts\verge_apply.py --dry-run

说明：在 DSH 会话中，.venv\Scripts\python.exe 以低完整性级别运行，写
%APPDATA% 会报 PermissionError: [Errno 13] Permission denied。此时改用上述
系统 Python 命令；在资源管理器“以管理员身份运行” verge-sync.cmd 时，子进程继承
管理员令牌，通常不需要该替代命令。不要把 AppData 路径写死到仓库。

### 5.3 回滚

    $env:PYTHONPATH=(Resolve-Path '.venv\Lib\site-packages').Path
    & 'D:\Programs\Python\python.exe' scripts\verge_apply.py --rollback .tmp_verge_apply_backup_<时间戳> --restart

回滚恢复备份中的六个文件并重启。不要删除最近一次备份，直到确认当前配置可正常使用。

### 5.4 重启注意事项

schtasks /End 只结束计划任务的直接进程，不会结束 Verge sidecar/core；实测单纯
/Run 也不会重新生成 clash-verge.yaml。脚本因此按镜像名结束
clash-verge.exe 与 verge-mihomo.exe，再执行
schtasks /Run /TN "Clash Verge (Admin)"。这会短暂断网，属于预期行为。

## 6. 2026-11-11 本机验证记录

验证对象：本机 Clash Verge Rev 2.5.10，FIB 订阅，Mihomo v1.19.33。

| 项目 | 结果 |
| --- | --- |
| 订阅节点 | 55 个；静态剔除 9 个 14 位 REALITY short-id，运行时额外剔除 0 个，可用 46 个 |
| 运行时配置 | clash-verge.yaml 2,297,692 B；46 proxies / 13 groups / 26 rules / 2 providers |
| 策略组 | 顺序与固定表一致；PROXY 9 项；Google fallback 4 项；AI 组各 8 项；地区组 4/9/5/1/8/3/16 |
| 端口 | 7897 与 1053 监听正常；无 port / socks-port |
| TUN | Mihomo 适配器 Up；默认路由 198.18.0.2；www.google.com 解析为 fake-ip 198.18.0.7 |
| 网络 | 百度 200、gstatic 204、Google 204、YouTube 200；出口 178.83.206.223（ipinfo: HK） |
| 全局文件 | Merge.yaml SHA-256 fc731147...；Script.js SHA-256 3a9e5332... |
| FIB 原文件 | 未修改；SHA-256 f35dd65a... |
| 备份 | .tmp_verge_apply_backup_20261111-2247b，6/6 文件哈希与大小匹配 |

上表是 2026-11-11 的运行记录（当时源规则 26 条）。2026-11-12 增加 Tailscale
`100.64.0.0/10` 直连规则后，源规则为 27 条；重新部署后运行时也应为 27 条，
尚未重新验证。

验证时 enable_tun_mode: true、enable_system_proxy: false、verge_mixed_port: 7897。
网络测试使用 Python OpenSSL 绕过系统代理，避免本机 PowerShell/schannel 的 TLS 问题干扰。

## 7. 测试接缝

| 接缝 | 文件 | 覆盖 |
| --- | --- | --- |
| G1/G2 | tests/test_verge_global.py | Merge 只含 store-selected 与两个 Provider；Script 生成 13 组/27 规则/DNS/端口；坏节点过滤；空地区回退；Node 执行真实脚本 |
| P1/P2 | tests/test_verge_preflight.py | short-id 静态过滤；逐节点预检；proxy-providers 拒绝；本机 Mihomo 可用时执行真实 -t |
| A1/A2 | tests/test_verge_apply.py | 备份/恢复字节；原子 LF 写入；校验接受/拒绝；失败自动回滚；dry-run 不写 |

运行：

    .venv\Scripts\python.exe -m unittest discover -s tests -v

这些测试只使用临时目录，不读写真实 Verge AppData；真实 Mihomo 测试在二进制不存在时
自动跳过。Node 执行测试在 node 不可用时跳过。

## 8. 限制与未验证项

- 只验证了 FIB 一个订阅；其他订阅的 inline 节点格式、脚本执行与组生成尚未实测。
- 未做 DNS 泄漏、断网重连、重启后 TUN 自动恢复、回滚演练。
- 未删除旧本地 mvpClash0001；它仍是回退路径。
- 重命名订阅后，MVP_EXCLUDED 的 profileName 键不会自动迁移；需重新运行 verge-sync.cmd（静态 short-id 过滤仍生效）。
- 未验证所有订阅都能通过 mihomo -t；预检只针对当前目标订阅。
- verge-sync.cmd 依赖 Windows 计划任务 Clash Verge (Admin) 与管理员权限；
  未安装系统服务，启动时可能弹出 Sidecar 选择。
- 本工具不是 CI 的一部分，也不进入 Release；CI 只运行不依赖 AppData 的单元测试。

## 9. 相关文件

- scripts/verge_global.py：生成 Merge/Script
- scripts/verge_preflight.py：静态 + 运行时节点预检
- scripts/verge_apply.py：备份、应用、重启、校验、回滚
- verge-sync.cmd：双击入口
- tests/test_verge_global.py、tests/test_verge_preflight.py、tests/test_verge_apply.py
