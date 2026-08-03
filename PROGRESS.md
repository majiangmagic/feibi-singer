# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `working-tree`（add preview vocal gain slider）
- 测试状态：39 pytest tests passing; real preview generation and ACE-Step Gradio UI construction passed; Harness check passed
- Lint：Python compile and git diff checks passed

### 已完成
- [x] The Feibi validator recognizes exactly the six user-defined lyric grammars.
- [x] The automatic lyric generator now cycles through every grammar feasible for each source-line syllable count.
- [x] Repetition groups marked with plus distribute extra syllables across Fei, Bi, and Jiu instead of padding only Jiu.
- [x] The segment workbench now exposes a -6 to +12 dB preview vocal gain slider for ACE/RVC plus-original-melody audition.

### 进行中
- [ ] The preview vocal gain slider is fully verified and ready to commit.

### 已知问题
- Preview vocal gain changes ACE/RVC audition files only; final merge retains integrated-LUFS matching.；
- The four-syllable fixed phrase Fei-Ba-Fen-Qian is only feasible for four-syllable source lines.；
- One-syllable source lines cannot satisfy any approved grammar and remain validation failures.。

### 下一步
1. Commit the preview gain feature and restart the local UI so the new slider is visible.。
