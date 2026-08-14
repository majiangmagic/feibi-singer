# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `working-tree`（set RVC default pitch to +6 semitones）
- 测试状态：40 pytest tests passing with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1; default RVC pitch regression covered
- Lint：Python compilation and Harness validation passed

### 已完成
- [x] The automatic lyric generator now cycles through every grammar feasible for each source-line syllable count.
- [x] Repetition groups marked with plus distribute extra syllables across Fei, Bi, and Jiu instead of padding only Jiu.
- [x] The segment workbench now exposes a -6 to +12 dB preview vocal gain slider for ACE/RVC plus-original-melody audition.
- [x] Full-song generation now runs in a background worker with persistent pipeline.log/pipeline_status.json and polling-based completion/failure updates.
- [x] The default RVC pitch is now +6 semitones while per-segment/manual overrides remain available.

### 进行中
- [ ] Restart the local UI when a fresh process is needed so it loads the new +6 default.

### 已知问题
- Preview vocal gain changes ACE/RVC audition files only; final merge retains integrated-LUFS matching.；
- The four-syllable fixed phrase Fei-Ba-Fen-Qian is only feasible for four-syllable source lines.；
- One-syllable source lines cannot satisfy any approved grammar and remain validation failures.。

### 下一步
1. Commit the validated default RVC +6 change.；
2. Restart the local UI when a fresh process is needed so it loads the new +6 default.。
