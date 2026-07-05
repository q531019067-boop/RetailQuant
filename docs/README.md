# RetailQuant 文档索引

> 创建人：   unknown
> 创建时间：  unknown
> 最后修改人： Lyuan741
> 最后修改时间：2026-07-05 22:18

---

本目录按用途分层：`docs/` 根目录保留**全局参考**；领域专题、研究测试、历史快照、外部工具分别放入子文件夹。

## 阅读顺序（新人 / AI）

1. [`大纲.md`](大纲.md) — 项目定位、多轨能力、目录树
2. [`代码索引.md`](代码索引.md) — 概念 → 文件 / 函数速查
3. [`STRATEGIES.md`](STRATEGIES.md) — 12 个策略行为说明
4. 按需：[`ui.md`](ui.md)（改前端）/ [`domain/`](domain/)（改多因子或数据池）/ [`CHANGELOG.md`](CHANGELOG.md)（最近变更）/ [`中英对照表.md`](中英对照表.md)（新增英文标识符时）

---

## 根目录 — 全局文档

| 文档 | 说明 |
|------|------|
| [`大纲.md`](大纲.md) | 项目架构总纲（AI 索引用） |
| [`代码索引.md`](代码索引.md) | 概念 → 代码映射 |
| [`STRATEGIES.md`](STRATEGIES.md) | 12 策略权威说明 |
| [`CHANGELOG.md`](CHANGELOG.md) | 变更日志 |
| [`ui.md`](ui.md) | Web 看板交互规格（`templates/index.html`） |
| [`中英对照表.md`](中英对照表.md) | 中文术语 ↔ 英文标识符 |

---

## [`domain/`](domain/) — 领域专题

| 文档 | 说明 |
|------|------|
| [`多因子选股回测系统.md`](domain/多因子选股回测系统.md) | MultiFactor 8 因子设计、API、在研究链路中的位置 |
| [`multi_factor_report.md`](domain/multi_factor_report.md) | MultiFactor 回测结果与参数敏感性 |
| [`数据池.md`](domain/数据池.md) | 标的池 / 数据源池 / Parquet 缓存设计与优化方案 |

---

## [`research/`](research/) — 研究链路

| 文档 | 说明 |
|------|------|
| [`策略回测链路测试文档.md`](research/策略回测链路测试文档.md) | 选池 → 拉数 → 多策略评分 → 组合模拟 E2E 测试记录 |

---

## [`archive/`](archive/) — 历史快照（只读参考，勿作当前真相）

| 文档 | 说明 | 快照日期 |
|------|------|----------|
| [`code-walkthrough-2026-06-22.md`](archive/code-walkthrough-2026-06-22.md) | 全量代码导读 | 2026-06-22 |
| [`opt-2026-06-22.md`](archive/opt-2026-06-22.md) | 优化建议清单（P0~P3） | 2026-06-22 |
| [`架构分析报告.md`](archive/架构分析报告.md) | sim-trading 分支架构审计 | 2026-06-22 |
| [`TODOLIST.md`](archive/TODOLIST.md) | 2026-06-18 前端 mock 数据点追踪（已归档） | 2026-06-18 |

---

## [`external/`](external/) — 外部工具

| 文档 | 说明 |
|------|------|
| [`qlib_usage.md`](external/qlib_usage.md) | 微软 Qlib 安装与 A 股数据（与 rQuant Parquet 体系并行，非主路径） |

---

## 仓库内其他文档

| 路径 | 说明 |
|------|------|
| [`../README.md`](../README.md) | 对外简介与启动方式 |
| [`../rquant/research/montecarlo/README.md`](../rquant/research/montecarlo/README.md) | 蒙特卡洛 quick reference |
| [`../rquant/research/montecarlo/DESIGN.md`](../rquant/research/montecarlo/DESIGN.md) | 蒙特卡洛设计文档 |
| [`../rbacktest/README.md`](../rbacktest/README.md) | rbacktest 独立子系统 |
