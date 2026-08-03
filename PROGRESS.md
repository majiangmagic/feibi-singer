# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `working-tree`（repair multi-song segment workbench）
- 测试状态：34 pytest tests passing; UI config and Harness checks passing
- Lint：Python compile checks passed in project and ACE venvs

### 已完成
- [x] The segment workbench supports ACE and RVC candidates with original-melody previews.
- [x] The UI supports multiple run projects and a from-scratch generation command.
- [x] Feibi lyric validation strictly follows the six user-defined grammars.

### 进行中
- [ ] Restart the local UI and verify first-segment loading and project switching end to end.

### 已知问题
- Real model generation remains dependent on the installed ACE-Step and RVC environments.；
- The first segment uses boundary-safe preview handling when the source starts at zero.。

### 下一步
1. Run browser verification against the local Gradio server.。
