# ARCHITECTURE.md

## 模块说明
本目录用于管理 Harness 上下文文件。

使用方法：
AI 只生成 JSON；
使用 python harness_context.py --type <类型> --direction json-to-md --input <输入 JSON> --output <输出 Markdown> 将 JSON 生成固定格式的 Markdown；
使用 --direction md-to-json 将 Markdown 转回 JSON；
使用 --direction search --keyword <索引关键词> 查询 DECISIONS.md 或 FEATURES.md；
使用 --direction latest --limit 5 查询 DECISIONS.md 或 FEATURES.md 中按日期排序的最新记录。
脚本采用面向对象结构，由 DocumentHandler 及各文档处理器负责固定格式转换，由 DocumentRegistry 统一管理文档类型，由 IndexService 提供索引查询和最新记录查询。

## 目录结构
- `harness_context.py`：面向对象工程化的通用 JSON 和 Markdown 双向转换脚本，包含文档处理、注册、索引、文件存储、转换服务和命令行入口；
- `architecture.example.json`：ARCHITECTURE.md 的 JSON 示例；
- `progress.example.json`：PROGRESS.md 的 JSON 示例；
- `decisions.example.json`：DECISIONS.md 的 JSON 示例；
- `features.example.json`：FEATURES.md 的 JSON 示例；
- `ARCHITECTURE.md`：本目录结构、使用方法和设计约束说明；

## 设计约束
- AI 只生成 JSON，不直接生成固定格式的 Markdown；
- Markdown 必须通过 harness_context.py 从 JSON 生成；
- DECISIONS.md 和 FEATURES.md 的索引使用 JSON 中的 keywords 数组；
- DECISIONS.md 和 FEATURES.md 的日期使用 YYYY-MM-DD 格式；
- DocumentHandler 子类负责各类文档的固定格式处理，DocumentRegistry 统一注册和选择文档类型；
- 所有生成后的 Markdown 都必须执行 md-to-json 回读，并与源 JSON 做结构化比较；
