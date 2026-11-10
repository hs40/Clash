# ENG-02 验收报告：四层分流规则与业务策略组

- 日期：2026-11-10
- 分支：`main`（本地仓库，未推送远端）
- 环境：Windows，Python 3.12.3，PyYAML 6.0.3，git 2.55.0
- 需求基线：[REQUIREMENTS.md](REQUIREMENTS.md) v1.3
- 结论：**ENG-02 全部可自动化验收项通过**；Mihomo 运行时加载仍属待核验项，
  本阶段以静态规则语义与首条匹配模拟验证，未声称已在设备上运行。

---

## 1. 总览

| 任务 | 状态 | 提交 |
| --- | --- | --- |
| ENG-02 四层分流规则与业务策略组 | 已完成 | 本报告所在提交 |

全部自动化测试：**63 项通过，0 失败**（ENG-01 为 41 项，本阶段新增 22 项）。

---

## 2. ENG-02 任务报告

1. **任务编号：** ENG-02
2. **完成情况：** 已完成。
3. **修改文件：**
   - 修改 `scripts/build.py`：新增 `RULE_LAYERS`、`RULE_TYPES`、`_sorted_entries`、
     `_rule_target`、`compile_rules`，并在 `build_platform` 中接入规则编译；
   - 修改 `configs/common/rules.yaml`：改为四层映射，补齐业务最小规则集；
   - 修改 `configs/common/proxy-groups.yaml`：新增 `OpenAI`、`Claude`、`Cursor` 三组；
   - 新增 `tests/test_rules.py`（21 项）；
   - 修改 `tests/test_groups.py`（新增 AI 组成员测试，共 17 项）；
   - 修改 `docs/REQUIREMENTS.md`（v1.3，新增 §4.3、重写 §5）与 `README.md`；
   - 新增本报告 `docs/ENG-02-ACCEPTANCE.md`。
4. **实现内容：**
   - 规则源为单文件四层映射：`special`、`business`、`base`、`fallback`，每条
     `{priority, rule}`；层顺序固定，priority 只在层内排序。
   - 校验：未知层、缺失层、条目非映射、未登记键、priority 非整数或布尔、同层重复
     priority、rule 为空、规则类型不在白名单、逗号分段有空段或首尾空白、
     目标策略不存在、`MATCH` 出现在非 fallback 层、`MATCH` 不是最后一条或不止一条，
     均使构建失败（退出码 2）。
   - 输出为扁平规则字符串，层名与 priority 不进入产物。
   - 新增三个 AI 策略组，类型 `select`，成员固定为「自动选择 + 七个地区入口」；
     Google 规则改指 `Google` 组；Apple、国内金融、BT 指向 `DIRECT`。
5. **测试命令：**
   ``.venv\Scripts\python.exe -m unittest discover -s tests -v``
6. **测试结果：** `Ran 63 tests in 3.823s`，`OK`；`--platform all` 退出码 0，
   两次构建产物逐字节一致（`fc /b` 返回 0）。
7. **需求偏差：** 见第 5 节。
8. **遗留问题：** 见第 6 节。
9. **下一步建议：** 进入 ENG-03（DNS 与 Fake-IP）；先提交设计与测试接缝，待负责人确认后实现。

---

## 3. 验收项核对

### 3.1 规则顺序稳定

产物 `rules` 共 24 条，顺序为：special（1）→ business（20）→ base（2）→ fallback（1）。
层内按 priority 升序，business 的 100/110/…/700 顺序在产物中保持稳定。
`tests/test_rules.py` 覆盖层顺序与乱序 priority 的排序。**通过。**

### 3.2 冲突可解释

`ConflictTest` 构造 special `DOMAIN,api.example.com,DIRECT` 与 business
`DOMAIN-SUFFIX,example.com,PROXY`，用首条匹配模拟验证：
`api.example.com` → `DIRECT`（special 胜出），`www.example.com` → `PROXY`，
未命中域名 → `MATCH,PROXY`。结果与四层优先级一致。**通过。**

### 3.3 不引用不存在的策略组

`compile_rules` 对每条规则的目标做白名单校验（已存在策略组 ∪
`DIRECT/REJECT/REJECT-DROP/PASS`）；产物级测试再次遍历全部规则确认目标存在。
未知目标、错误段数、未知类型均有失败路径测试。**通过。**

### 3.4 静态分析结果与 Mihomo 实际行为一致

本阶段未获得可执行的 Mihomo v1.19.33 二进制，**没有做运行时加载验证**，
因此不能声称与真实内核行为完全一致。已做的是：

- 语法与类型限制在 Mihomo 文档化的规则类型内；
- 以「首条匹配、命中即停」的语义模拟冲突；
- 产物可被 PyYAML 完整解析，键序与结构稳定。

该项为**部分通过（静态语义一致，运行时待核验）**，列入第 6 节遗留问题。

---

## 4. 产物核对

| 产物 | 字节 | SHA-256（前 16 位） | 策略组数 | 各组人数 | 规则数 |
| --- | --- | --- | --- | --- | --- |
| `dist/windows/config.yaml` | 4127 | `aef1eecacc3355d7` | 13 | 9,7,1,1,1,1,1,1,1,4,8,8,8 | 24 |
| `dist/openclash/config.yaml` | 4006 | `6d959695f66279a8` | 13 | 9,7,1,1,1,1,1,1,1,4,8,8,8 | 24 |

组顺序：`PROXY`、`自动选择`、香港节点、台湾节点、日本节点、韩国节点、狮城节点、
美国节点、其他节点、`Google`、`OpenAI`、`Claude`、`Cursor`。
两份产物仅平台键不同，策略组、规则与节点完全一致。

---

## 5. 需求偏差与负责人决策

| 项 | 处理 | 依据 |
| --- | --- | --- |
| 规则源采用单文件四层映射，而非多个规则文件 | 按负责人确认的源结构实现 | 负责人 2026-11-10 决策 |
| AI 只建 OpenAI / Claude / Cursor 三组，不含 Gemini / Perplexity | 严格按确认范围 | 负责人 2026-11-10 决策 |
| 五类业务先落最小代表规则，完整名单延后 | 避免在无 Provider 输入时伪造大名单 | 负责人 2026-11-10 决策；Plan ENG-02/ENG-06 边界 |
| Google 规则由 `PROXY` 改指 `Google` 组 | 补齐 ENG-01 遗留的路由目标 | Plan ENG-02 |
| 未做 Mihomo 运行时加载 | 无固定版本二进制；不伪造测试结果 | §14 待核验范围 |

---

## 6. 遗留问题

1. 未做 Mihomo v1.19.33 实际加载与规则命中验证；需在取得固定版本二进制后补做，
   并核对 `DOMAIN-KEYWORD`、`GEOIP,LAN` 等规则的实际支持情况。
2. 业务域名清单为最小代表集，未覆盖全部 Google / AI / Apple / 金融 / BT 域名；
   完整名单与 `RULE-SET` 化属 ENG-06 Provider 范围。
3. BT 目前只有 `DOMAIN-KEYWORD,tracker` 一条直连规则，不构成完整的 BT 分流策略；
   后续需在真实使用场景中核验，不预先猜测站点清单。
4. 三个 AI 组默认「自动选择」，未设置独立的健康检查参数；如需调优，在真实设备核验后进行。
5. `GEOIP,LAN` 依赖 Mihomo 内置 LAN 地理库行为，尚未在目标内核上验证。
