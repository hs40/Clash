# 回滚手册（Windows / OpenClash）

**适用范围：** 本工程发布的 Mihomo/Meta 配置（ENG-06）。回滚由负责人手动执行；
本工程不自动修改真实设备，也不提供跨平台一键回滚。

## 1. 原则

1. Windows 与 OpenClash **独立回滚**，不能用一个平台的包覆盖另一个平台。
2. 回滚前先备份当前可用配置，并记录其 SHA-256。
3. 只使用带 `SHA256SUMS` 的发布包；校验失败立即停止。
4. 先恢复配置，再重启/重载内核，最后做连通性与 DNS 验证。
5. 保留最近 5 个已验证版本；**当前正式使用版本不得因数量限制被删除**。
6. 高风险变更（DNS、分流规则、安全策略、正式发布）须负责人审查后执行。

## 2. 发布包结构

每个版本目录（例如 `0.1.0/`）包含：

- `windows/config.yaml`、`windows-0.1.0.zip`
- `openclash/config.yaml`、`openclash-0.1.0.zip`
- `SHA256SUMS`、`RELEASE-NOTES.md`
- `THIRD_PARTY_NOTICES.md`、`LICENSE-metacubex.txt`

zip 内只有 `config.yaml`、第三方声明和许可证，不含订阅、凭据或本机路径。

`SHA256SUMS` 只覆盖 Release 实际上传的两个平台 zip；发布目录内的 `config.yaml`、
说明文件与许可证是构建内部文件，由 zip 内同名副本核对。下载全部 Release 资产后，
`sha256sum -c SHA256SUMS` 应通过。

## 3. 回滚前准备

1. 确认要回滚的平台和目标版本（上一版或最近一个已验证版本）。
2. 从 GitHub Release 下载对应平台的 zip 和 `SHA256SUMS`；不要使用来源不明的包。
3. 备份当前配置：
   - Windows：在 Clash Verge 中导出/复制当前 profile，保存到仓库外的备份目录。
   - OpenClash：通过 LuCI 或 SSH 只读复制当前配置到仓库外；不要覆盖正在使用的文件。
4. 记录当前版本、备份文件路径和 SHA-256。

## 4. 校验发布包

Windows PowerShell：

```powershell
Get-FileHash -Algorithm SHA256 .\windows-0.1.0.zip
Get-Content .\SHA256SUMS
```

OpenClash（BusyBox）：

```sh
sha256sum windows-0.1.1.zip
# 若系统没有 sha256sum：
openssl dgst -sha256 windows-0.1.1.zip
```

哈希必须与 `SHA256SUMS` 中对应平台的 zip 行完全一致。不要在哈希不一致时继续；
`SHA256SUMS` 不列出发布目录中的非资产文件，这是刻意设计，不是缺失。

## 5. Windows 回滚

1. 关闭 Clash Verge 的“系统代理/TUN”或退出内核（按当前使用方式）。
2. 在 Clash Verge 的配置页导入上一版本的 `config.yaml`，或替换当前 profile 文件；
   不要直接改 Verge 生成的运行配置。
3. 保持负责人现有的运行时设置：Verge 会覆盖 `mixed-port`、IPv6、TUN 等值；
   本工程不写入用户真实 Verge 配置。
4. 启动/重载内核，确认配置加载成功（Verge 日志或 `verge-mihomo -t`）。
5. 验证：
   - 系统代理/TUN 是否按预期接管；
   - 访问国内站点与 Google/AI 业务是否走预期策略；
   - DNS 是否仍为 Fake-IP、无异常泄漏；
   - IPv6 是否保持关闭。
6. 若失败，重新导入第 3 步的备份并重复验证。

## 6. OpenClash 回滚

1. 通过 LuCI 备份当前 OpenClash 配置到仓库外；记录路径与 SHA-256。
2. 解压上一版本 `openclash-0.1.0.zip`，只取 `config.yaml`。
3. 在 OpenClash 配置管理中导入/替换配置；不要手工写入
   `redir-port`、`tproxy-port`、iptables、`external-controller`、`secret`
   等运行时注入键。
4. 应用配置并重启 OpenClash（或按设备现有流程重载）。
5. 验证：
   - 内核日志无配置错误；
   - `192.168.2.10:7893` 的 HTTP 代理可用（仅 LAN）；
   - NAS 显式代理路径可用（ENG-04 §3.4：192.168.2.2 经 192.168.2.10:7893 返回 204、出口非 CN，网关 192.168.2.1 未改）；
   - Fake-IP/DNS 分流正常，未暴露到 WAN；
   - 未启用 IPv6。
6. 若失败，恢复第 1 步备份并重启，确认恢复原状。

## 7. 版本保留

1. 每个平台保留最近 5 个已验证版本。
2. 删除旧版本前，先确认它不是当前正式使用版本，也不在回滚窗口内。
3. 当前正式使用版本的发布包、`SHA256SUMS` 和 Release Notes 必须保留。
4. 不建设 GitHub 以外的灾难恢复备份系统；设备本地备份只用于本次回滚。

## 8. 回滚记录模板

```text
日期：
平台：Windows / OpenClash
从版本：           到版本：
发布包 SHA-256：
备份路径与 SHA-256：
执行人：
结果：成功 / 失败
验证：内核加载 / 代理 / DNS / IPv6 / LAN
备注：
```

## 9. 禁止事项

- 不把 Windows 配置直接用于 OpenClash，或反向覆盖。
- 不在未校验 SHA-256 的情况下部署。
- 不把订阅、节点密码、Token 或真实凭据写入发布包、仓库或回滚记录。
- 不通过自动化脚本直接修改用户真实设备；回滚始终由负责人确认后手动执行。
