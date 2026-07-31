# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `728cff2`（feat: flesh out feibi pipeline skeleton）
- 测试状态：Passed: python -m compileall feibi_singer scripts tests; pytest -q 6 passed; CLI dry-run wrote stage artifacts successfully
- Lint：Python compileall passed

### 已完成
- [x] The Feibi lyric rule layer, external stage adapters, and dry-run pipeline are implemented
- [x] harness_context.py now supports JSON/Markdown round-trip conversion and index queries for the four document types
- [x] ARCHITECTURE.md, PROGRESS.md, FEATURES.md, and DECISIONS.md have been regenerated from UTF-8 JSON
- [x] Markdown md-to-json round-trip results match the source JSON
- [x] Unit tests, integration tests, and Python compile checks all passed

### 进行中
- [ ] Connecting the real ASR, LLM, ACE-Step 1.5, and RVC execution chain

### 已知问题
- The real audio chain is not connected yet; only dry-run has been validated；
- RVC still needs the user-provided Feibi model files and index file。

### 下一步
1. Add ASR as the fallback lyric source；
2. Connect lyric rewriting with the LLM and song generation with ACE-Step 1.5；
3. Connect the RVC voice conversion execution path and model validation。
