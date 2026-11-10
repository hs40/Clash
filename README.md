# Clash 配置工程（hs40/Clash）

用一套公共配置，生成 **Windows（Clash Verge Rev）** 与 **OpenClash（iStoreOS 旁路由）**
两份完整的 Mihomo 配置：

```
configs/common/*.yaml  ─┐
configs/windows/*.yaml ─┼─> scripts/build.py ─> dist/windows/config.yaml
configs/openclash/*.yaml┘                   └─> dist/openclash/config.yaml
```

- 需求基线：[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
- MVP 验收报告：[docs/MVP-ACCEPTANCE.md](docs/MVP-ACCEPTANCE.md)
- 原始开发计划：[Clash 配置工程开发 Plan.md](Clash 配置工程开发 Plan.md)
- 兼容基准：Mihomo v1.19.33（设计基准，非已核实的设备运行版本）

## 源文件与构建产物

| 类别 | 路径 | 是否入库 | 说明 |
| --- | --- | --- | --- |
| 公共配置源 | `configs/common/` | 是 | 节点、策略组、DNS、规则、全局标量 |
| 平台配置源 | `configs/windows/`、`configs/openclash/` | 是 | 仅平台专属键 |
| 构建脚本 | `scripts/build.py` | 是 | 读取、合并、校验、输出 |
| 测试 | `tests/` | 是 | 构建结果与输出校验 |
| 构建产物 | `dist/` | 否（见 `.gitignore`） | 每次构建重新生成 |
| 文档 | `docs/` | 是 | 需求基线、验收报告 |

原则：**源文件入库，产物不入库**。产物必须能由源文件重复构建得到，
因此产物中不允许出现无法重建的内容（时间戳、随机值、真实订阅）。

合并契约（详见 REQUIREMENTS §11）：`platform.yaml` 是 Mihomo 顶层片段，构建时做
**顶层浅合并**，每个顶层键只有一个所有者；白名单之外的键、公共与平台重复定义的键、
同一文件内的重复键都会让构建失败，并报告文件名与键名。

策略组成员由构建期按地区识别生成（`include: all` / `include: region:<入口名>`），
不手写节点名单；规则见 REQUIREMENTS §4.2。

## 环境准备

需要 Python 3.12（本项目在 3.12.3 上验证）。Windows 上请使用真实的 Python 解释器，
不要使用 `WindowsApps` 的 `python.exe` 存根。

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

依赖锁定在 `requirements.txt`（当前只有 `PyYAML==6.0.3`）；哈希锁定与 CI 属 ENG-05。

## 构建

```powershell
.venv\Scripts\python.exe scripts\build.py --platform all
```

- `--platform`：`all`（默认用法）、`windows` 或 `openclash`。
- `--out`：输出根目录，默认 `dist/`；实际产物为 `<out>/windows/config.yaml`、
  `<out>/openclash/config.yaml`。
- `--root`：源文件根目录，默认仓库根目录；用于测试夹具或异地构建。

构建成功时退出码为 0；配置不满足合并契约时退出码为 2，错误信息包含文件名与键名，
例如：

```
构建失败：F:\...\configs\windows\platform.yaml：未登记的顶层键 'foo-bar'（允许：mixed-port, allow-lan, tun）
```

相同输入必须产生字节一致的输出：键顺序固定、无时间戳、UTF-8 无 BOM、LF 换行。

## 测试

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖（`tests/`）：

- 源文件存在性、非空与 YAML 合法性；
- 公共 / 平台配置的顶层键归属，以及平台配置不得写入公共键或运行时注入键；
- 合并契约错误路径：未登记键、公共与平台重复键、同文件重复键、缺失键、未知平台；
- 命令行：一份命令生成两份产物、两次构建字节一致、配置错误退出码 2；
- 变更传播：公共配置修改反映到两个平台，平台配置修改只影响对应平台；
- 地区识别：七个入口名称、关键词匹配、ASCII 整词边界、多地区命中优先级；
- 策略组生成：`include` 展开、空地区回退到「自动选择」、Google 回退顺序、
  增删改节点不改变组名、无效引用与循环引用使构建失败。

## 占位内容说明

MVP 阶段的 `configs/common/proxies.yaml` 使用 **TEST-NET-1（192.0.2.0/24）** 地址、
`PLACEHOLDER-NOT-REAL` 口令的占位节点。它们不是可用的代理节点，不得用于真实部署，
也不代表任何真实订阅、节点或凭据。DNS 与平台参数为 MVP 草案值，部署前必须按
REQUIREMENTS §14 在真实设备上核验。

## 当前状态

MVP-01 至 MVP-06、ENG-01 已完成并通过自动化测试，验收记录见
[docs/MVP-ACCEPTANCE.md](docs/MVP-ACCEPTANCE.md) 与
[docs/ENG-01-ACCEPTANCE.md](docs/ENG-01-ACCEPTANCE.md)。ENG-02 至 ENG-06 尚未开始。
