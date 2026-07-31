# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `c34bf32`（feat: add feibi lyric rule layer）
- 测试状态：单元测试 4/4 通过，CLI dry-run 通过
- Lint：Python compileall 通过

### 已完成
- [x] 菲比歌词规则层、外部阶段适配器和 dry-run 流水线已实现
- [x] harness_context.py 已支持四类文档的 JSON/Markdown 双向转换及索引查询
- [x] ARCHITECTURE.md、PROGRESS.md、FEATURES.md 和 DECISIONS.md 已从 UTF-8 JSON 重新生成
- [x] 目标 Markdown 的 md-to-json 回读结果已与源 JSON 一致
- [x] 单元测试、集成测试、Python 编译检查和 CLI dry-run 端到端验证均已通过

### 进行中
- [ ] 补齐真实 ASR、ACE-Step 1.5 和 RVC 的端到端联调

### 已知问题
- 真实音频链路尚未接入，目前只验证了 dry-run；
- RVC 还需要接入用户提供的菲比模型文件。

### 下一步
1. 接入多语言 ASR 和歌词分离模块；
2. 接入 ACE-Step 1.5 仅改歌词模式与 RVC 音色转换。
