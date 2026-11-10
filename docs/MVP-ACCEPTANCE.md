# MVP 验收报告（MVP-01 至 MVP-06）

- 日期：2026-11-10
- 分支：`main`（本地仓库，未推送远端）
- 环境：Windows，Python 3.12.3（`D:\Programs\Python`），PyYAML 6.0.3，git 2.55.0
- 需求基线：[REQUIREMENTS.md](REQUIREMENTS.md) v1.0
- 结论：**MVP 全部验收项通过**，未发现阻塞进入第二阶段的问题。

---

## 1. 总览

| 任务 | 状态 | 提交 |
| --- | --- | --- |
| MVP-01 仓库检查与初始化 | 已完成 | `0a6ab49` |
| MVP-02 固化需求基线 | 已完成 | `17230b8` |
| MVP-03 公共配置接口 | 已完成 | `6f41c2c` |
| MVP-04 双平台配置接口 | 已完成 | `328f4c4` |
| MVP-05 最小 Python Builder | 已完成 | `b5d9c0d` |
| MVP-06 基础自动化测试 | 已完成 | 本报告所在提交 |

全部自动化测试：**19 项通过，0 失败**。

---

## 2. MVP-01：仓库检查与初始化

1. **任务编号：** MVP-01
2. **完成情况：** 已完成。
3. **修改文件：** 新增 `.gitignore`、`.gitattributes`、`README.md`；保留未改动的
   `Clash 配置工程开发 Plan.md`。
4. **实现内容：** 仓库原先只有 Plan 文档、不是 Git 仓库。执行 `git init -b main`，
   配置 origin 为 `https://github.com/hs40/Clash.git`（远端为空仓库），建立
   `configs/`、`scripts/`、`tests/`、`docs/`、`dist/` 结构；`.gitignore` 排除
   `dist/`、`.venv/`、`__pycache__/` 等产物；`.gitattributes` 统一 LF，保证
   Windows 与 CI 构建结果一致。
5. **测试命令：** `git status --short`、目录列举、`git log --oneline`。
6. **测试结果：** 通过；未覆盖或删除任何已有有效文件。
7. **需求偏差：** 无。
8. **遗留问题：** 无。
9. **下一步建议：** 无。

## 3. MVP-02：固化需求基线

1. **任务编号：** MVP-02
2. **完成情况：** 已完成。
3. **修改文件：** 新增 `docs/REQUIREMENTS.md`（v1.0）。
4. **实现内容：** 从 Plan v1.0 提取需求基线，共 15 节：平台与网络环境、节点与策略组
   （含负责人确认的七个地区入口）、四层规则、五个关键业务、DNS、Provider、自动化与
   安全、发布与回滚、公共/平台配置边界与键归属表、MVP 边界、MVP 草案参数、待核验清单、
   变更记录。已确认事项标【确定】，未在设备上验证的标【待核验】，未把草案写成事实。
5. **测试命令：** 人工逐节核对 Plan 原文；后续测试断言引用其中的键归属表。
6. **测试结果：** 通过。
7. **需求偏差：** 无。
8. **遗留问题：** §14 的 7 项待核验事项只能在真实设备上完成，MVP 不覆盖。
9. **下一步建议：** 进入 ENG 阶段前保持 §14 清单开启，不做「已验证」表述。

## 4. MVP-03：公共配置接口

1. **任务编号：** MVP-03
2. **完成情况：** 已完成。
3. **修改文件：** 新增 `configs/common/general.yaml`、`proxies.yaml`、
   `proxy-groups.yaml`、`dns.yaml`、`rules.yaml`、`requirements.txt`；
   新增 `tests/test_build.py` 的源文件校验部分。
4. **实现内容：**
   - `general.yaml`：`mode: rule`、`log-level: info`、`ipv6: false`。
   - `proxies.yaml`：7 个占位节点，TEST-NET-1（`192.0.2.11`–`.17`）、
     `ss`、`aes-128-gcm`、`PLACEHOLDER-NOT-REAL`、`udp: false`。
   - `proxy-groups.yaml`：`PROXY`（select）、`自动选择`（url-test，300 秒、
     容差 50）、七个地区 select 组，名称与负责人确认一致。
   - `dns.yaml`：fake-ip、国内外分流、`proxy-server-nameserver` 独立解析路径。
   - `rules.yaml`：四层骨架 7 条规则，`MATCH,PROXY` 位于最后。
5. **测试命令：** `.venv\Scripts\python.exe -m unittest discover -s tests -v`
6. **测试结果：** 通过（源文件存在性、非空、YAML 合法、顶层键集合）。
7. **需求偏差：** 新增 Plan §3.3 未列出的第 5 个公共文件 `general.yaml`。
   原因：§11 键归属表把 `mode`、`log-level`、`ipv6` 划给公共配置，
   若放进任一份 `platform.yaml` 会造成平台独占键泄漏到另一平台。已在本报告与
   REQUIREMENTS 中记录，等待负责人追认；替代方案是把三个标量分别复制进两个平台文件。
8. **遗留问题：** `其他节点` 组当前包含占位节点 `占位-其他-01`（不匹配任何地区关键词）；
   该组语义尚未由负责人确认（见第 8 节）。
9. **下一步建议：** 负责人确认 `general.yaml` 与 `其他节点` 组语义后再进入 ENG-01。

## 5. MVP-04：双平台配置接口

1. **任务编号：** MVP-04
2. **完成情况：** 已完成。
3. **修改文件：** 新增 `configs/windows/platform.yaml`、
   `configs/openclash/platform.yaml`；新增平台配置测试。
4. **实现内容：**
   - Windows：`mixed-port: 7890`、`allow-lan: false`、
     `tun`（enable、gvisor、auto-route、auto-detect-interface、`dns-hijack: [any:53]`、
     `strict-route: false`）。
   - OpenClash：`port: 7893`（HTTP，非 mixed-port）、`allow-lan: true`、
     `bind-address: "*"`；不写 `redir-port`/`tproxy-port`/iptables/
     `external-controller`/`secret`。
5. **测试命令：** 同上。
6. **测试结果：** 通过（平台键归属、不得写入公共独占键、不得写入运行时注入键）。
7. **需求偏差：** Plan §MVP-04 把「IPv4-only」「局域网直连」「DNS 接管」列在平台
   职责下，实际 `ipv6`、`GEOIP,LAN`、`dns` 位于公共配置——这符合已确认的 §11
   键归属表；平台差异化的 DNS 接入（如 OpenClash 自行注入 7874）留待 ENG-03 核验。
8. **遗留问题：** Verge 是否覆盖 `mixed-port`/`tun`、OpenClash 是否注入端口与 DNS，
   均属 §14 待核验项。
9. **下一步建议：** 在真实设备上按 §14 逐项核验后再宣称平台参数可用。

## 6. MVP-05：最小 Python Builder

1. **任务编号：** MVP-05
2. **完成情况：** 已完成。
3. **修改文件：** 新增 `scripts/build.py`；新增合并与传播测试。
4. **实现内容：**
   - 按固定顺序加载 5 个公共文件，再加载 `configs/<platform>/platform.yaml`，
     顶层浅合并；每个顶层键只有一个所有者。
   - 白名单校验：公共键 ∈ {mode, log-level, ipv6, proxies, proxy-groups, dns, rules}；
     Windows ∈ {mixed-port, allow-lan, tun}；OpenClash ∈ {port, allow-lan, bind-address}。
   - 拒绝：未登记键、公共/平台重复键、同一文件内重复键（自定义 Loader，
     PyYAML 默认会静默覆盖）、缺少必需键、未知平台。错误信息包含文件名与键名。
   - 输出键顺序固定（`KEY_ORDER`），`safe_dump(width=4096, allow_unicode=True)`，
     UTF-8 无 BOM、LF；相同输入字节一致。
   - 产物：`dist/<platform>/config.yaml`（按 Plan §MVP-05）。
   - CLI：`--platform all|windows|openclash`、`--out`、`--root`；配置错误退出码 2。
5. **测试命令：** `.venv\Scripts\python.exe scripts\build.py --platform all`
   及完整 unittest。
6. **测试结果：** 通过；生成 `dist/windows/config.yaml`（2878 字节）、
   `dist/openclash/config.yaml`（2757 字节），均可被 PyYAML 解析。
7. **需求偏差：** 新增 `--root` 参数（Plan 与 Q9 接缝只约定 `--platform`/`--out`），
   用于在临时目录注入错误夹具、端到端验证「构建失败返回非零退出码」。属测试可观测性
   需要，未引入新行为。
8. **遗留问题：** 输出为 Mihomo 配置文本，尚未用真实 mihomo 二进制做语法/加载校验
   （MVP 边界外，ENG 阶段引入固定版本与 SHA-256）。
9. **下一步建议：** ENG-05 引入 mihomo 校验与依赖哈希锁定。

## 7. MVP-06：基础自动化测试

1. **任务编号：** MVP-06
2. **完成情况：** 已完成。
3. **修改文件：** 扩充 `tests/test_build.py`（19 项）；更新 `README.md`
   （构建与测试方法）；新增本报告。
4. **实现内容：** 测试按公开接缝组织：S1 命令行（`scripts/build.py`），
   S2 `build_platform(platform, root)`。不 mock PyYAML，不测私有函数。
5. **测试命令：**

   ```powershell
   .venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

6. **测试结果：** `Ran 19 tests ... OK`，覆盖：
   - 源文件存在/非空、YAML 合法、顶层键集合（5 项）；
   - 平台键归属、不得写入公共键与运行时注入键（3 项）；
   - 合并结果与键顺序、OpenClash 不含 Windows 键、dump 确定性（3 项）；
   - 契约错误：未登记键、公共/平台冲突、同文件重复键、缺失键、未知平台（5 项）；
   - 变更传播：公共改动影响两平台、平台改动只影响自身（2 项）；
   - CLI：双产物生成、两次构建字节一致、配置错误退出码 2、非法参数失败（4 项）。
7. **需求偏差：** 无。
8. **遗留问题：** 测试不覆盖真实网络连通性、DNS 泄漏与设备加载（Plan §9 第 11 条已声明
   自动化测试不能替代）。
9. **下一步建议：** ENG 阶段在 CI 中运行同一套命令，并补充 mihomo 加载校验。

---

## 8. MVP 完成标准核对（Plan §3.5）

| 标准 | 结果 | 证据 |
| --- | --- | --- |
| 仓库结构建立完成 | 通过 | `configs/`、`scripts/`、`tests/`、`docs/`、`dist/` |
| 需求基线文档完成 | 通过 | `docs/REQUIREMENTS.md` v1.0 |
| 公共配置文件完成 | 通过 | 5 个公共 YAML，测试断言顶层键 |
| Windows 平台配置接口完成 | 通过 | `configs/windows/platform.yaml` |
| OpenClash 平台配置接口完成 | 通过 | `configs/openclash/platform.yaml` |
| Python Builder 可以运行 | 通过 | `--platform all` 退出码 0 |
| 两份完整 YAML 可以生成 | 通过 | `dist/windows/config.yaml`、`dist/openclash/config.yaml` |
| YAML 基础校验通过 | 通过 | 测试逐文件解析 |
| 自动化测试通过 | 通过 | 19/19 |
| 没有提交真实凭据 | 通过 | 全仓库检索仅 `PLACEHOLDER-NOT-REAL` |
| README 包含构建和测试方法 | 通过 | README「构建」「测试」节 |

## 9. 需求偏差与待确认事项

1. **`general.yaml`（新增公共文件）**：为使 `mode`/`log-level`/`ipv6` 只被
   公共配置拥有，新增第 5 个公共文件。需负责人追认，或改为复制进两个平台文件。
2. **`其他节点` 组语义**：当前放入占位节点 `占位-其他-01`（不匹配任何地区关键词）。
   可选方案：保持「未匹配地区的兜底节点池」、改指向 `DIRECT`、或由 ENG-01 的地区
   识别规则决定。MVP 未擅自扩展，等待负责人确认。
3. **`--root` 参数**：为端到端测试错误退出码新增，默认值即仓库根目录，不影响正常使用。
4. **本仓库未推送远端**：未获授权且本地无远端凭据；全部提交仅在本地 `main`。
5. **Git 身份**为 `Clash Builder <builder@hs40.local>`（仓库本地配置），可由负责人更换。

## 10. 下一步建议

1. 负责人确认第 8 节两项（`general.yaml`、`其他节点`）。
2. 启动 ENG-01（节点与策略组）前，先在真实设备完成 REQUIREMENTS §14 的核验，
   避免在未验证的草案参数上继续叠加实现。
3. ENG 阶段继续遵守「一模块一测试一报告」，不重写已通过的 MVP 功能。
