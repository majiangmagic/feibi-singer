# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `c09b044`（docs: rebuild project architecture from updated agent rules）
- 测试状态：单元测试 3/3、集成测试 1/1、CLI dry-run 端到端验证均通过
- Lint：未配置独立 Lint；Python compileall 检查通过

### 已完成
- [x] 菲比歌词规则、外部阶段适配器和 dry-run 流水线已实现
- [x] harness_context.py 已支持四类文档的 JSON/Markdown 双向转换及索引查询
- [x] 两份 ARCHITECTURE.md、PROGRESS.md、FEATURES.md 和 DECISIONS.md 已从规范 UTF-8 JSON 重新生成
- [x] 5 份目标 Markdown 的 md-to-json 回读结果均与源 JSON 完全一致
- [x] FEATURES.md 和 DECISIONS.md 的 search 与 latest 查询已通过
- [x] 单元测试、集成测试、Python 编译检查和 CLI dry-run 端到端验证均已通过
- [x] AGENT.md 保持用户手工确认版本，准备与本次完整工作一并提交

### 进行中

### 已知问题
- 真实分离、ASR、ACE-Step 和 RVC 模型链路尚未在本仓库环境执行，当前端到端证据为 dry-run；
- 项目尚未配置独立 Lint 工具，目前使用 Python compileall 作为基础语法检查。

### 下一步
1. 配置真实分离工具和 ASR 命令，验证输入歌曲到素材准备与歌词识别的实际链路；
2. 配置 ACE-Step 1.5 和 RVC 模型路径，按单功能点继续完成真实音频端到端验证。
