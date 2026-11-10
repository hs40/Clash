# Clash 配置工程（hs40/Clash）

用一套公共配置，生成 **Windows（Clash Verge Rev）** 与 **OpenClash（iStoreOS 旁路由）**
两份完整的 Mihomo 配置：

```
configs/common/*.yaml  ─┐
configs/windows/*.yaml ─┼─> scripts/build.py ─> dist/windows/config.yaml
configs/openclash/*.yaml┘                   └─> dist/openclash/config.yaml
```

- 需求基线：[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
- 原始开发计划：[Clash 配置工程开发 Plan.md](Clash 配置工程开发 Plan.md)
- 兼容基准：Mihomo v1.19.33（设计基准，非已核实的设备运行版本）

## 源文件与构建产物

| 类别 | 路径 | 是否入库 | 说明 |
| --- | --- | --- | --- |
| 公共配置源 | `configs/common/` | 是 | 节点、策略组、DNS、规则 |
| 平台配置源 | `configs/windows/`、`configs/openclash/` | 是 | 仅平台专属键 |
| 构建脚本 | `scripts/build.py` | 是 | 读取、合并、校验、输出 |
| 测试 | `tests/` | 是 | 构建结果与输出校验 |
| 构建产物 | `dist/` | 否（见 `.gitignore`） | 每次构建重新生成 |
| 文档 | `docs/` | 是 | 需求基线、验收报告 |

原则：**源文件入库，产物不入库**。产物必须能由源文件重复构建得到，
因此产物中不允许出现无法重建的内容（时间戳、随机值、真实订阅）。

## 占位内容说明

MVP 阶段的 `configs/common/proxies.yaml` 使用 **TEST-NET-1（192.0.2.0/24）** 地址、
`PLACEHOLDER-NOT-REAL` 口令的占位节点。它们不是可用的代理节点，不得用于真实部署，
也不代表任何真实订阅、节点或凭据。

## 当前状态

- 已完成：MVP-01 仓库初始化、MVP-02 需求基线
- 进行中：MVP-03 公共配置接口、MVP-04 双平台配置接口、MVP-05 Builder、MVP-06 自动化测试

构建与测试命令在 MVP-05 / MVP-06 落地后补充到本节。
