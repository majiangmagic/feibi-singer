# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `working-tree`（add ACE-Step flow-edit lyric replacement）
- 测试状态：34 pytest tests passing; UI config, HTTP smoke test, and Harness checks passing
- Lint：Python compile checks passed in project and ACE venvs

### 已完成
- [x] The from-scratch UI accepts original lyrics as multiline text and passes them through --lyrics-text.
- [x] Timeline segments preserve aligned original and rewritten lyric lines for ACE-Step 1.5 cover flow-edit.
- [x] New and existing workbench runs use cover strength 1.0 plus flow-edit when original segment lyrics are available.

### 进行中
- [ ] The feature is complete; the next real ACE generation will provide listening-based validation of melody preservation.

### 已知问题
- ACE-Step does not expose an independent only_lyrics task; lyric replacement uses the supported cover plus flow-edit overlay.；
- Older cached runs without original_lyrics.txt remain compatible but cannot enable flow-edit automatically.。

### 下一步
1. Use the UI to create a new song run with direct original-lyrics text and audition flow-edit candidates.。
