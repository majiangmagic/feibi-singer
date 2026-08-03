# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `working-tree`（fix generated candidate preview selection）
- 测试状态：39 pytest tests passing; feibi_unhappy_sesame4 UI smoke passed; Harness check passing
- Lint：Python compile and git diff checks passed

### 已完成
- [x] The automatic lyric generator now cycles through every grammar feasible for each source-line syllable count.
- [x] Repetition groups marked with plus distribute extra syllables across Fei, Bi, and Jiu instead of padding only Jiu.
- [x] The segment workbench now exposes a -6 to +12 dB preview vocal gain slider for ACE/RVC plus-original-melody audition.
- [x] The default ACE caption now uses strict source-melody preservation and explicit clear Mandarin pronunciation guidance for four Feibi syllables.
- [x] Fixed the segment UI so generating a new ACE candidate does not trigger a selection callback that overwrites its fresh audio with an older candidate.

### 进行中
- [ ] The candidate preview selection fix is committed; final Harness validation and UI restart remain.

### 已知问题
- Preview vocal gain changes ACE/RVC audition files only; final merge retains integrated-LUFS matching.；
- The four-syllable fixed phrase Fei-Ba-Fen-Qian is only feasible for four-syllable source lines.；
- One-syllable source lines cannot satisfy any approved grammar and remain validation failures.。

### 下一步
1. Run Harness validation and restart the local UI.。
