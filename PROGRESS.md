# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `2666437`（增加动态分段歌声转换）
- 测试状态：项目独立 Python 3.11 venv 中 19 项 pytest 通过；unhappy v4 动态分段、候选筛选、RVC +4、拼接和完整混音端到端完成
- Lint：5 段逐秒 RMS 覆盖率为 100%/92.3%/100%/85.7%/100%；最终 WAV/MP3 均为 98.246542 秒且无异常长静音

### 已完成
- [x] 已用 Demucs CUDA 对用户 MP3 和 ACE-Step 输出完成真实人声/伴奏分离
- [x] 已支持用户歌词优先并用本地规则生成通过校验的菲比歌词
- [x] 已用 ACE-Step 1.5 turbo 生成原唱活动窗口，并用 RVC 菲比模型转换生成歌声
- [x] 已将 RVC 歌声按自动检测的原唱起点延迟并混回原始伴奏，前奏约 0-16.44 秒无人声
- [x] 已用 7.5 秒上下文、0.25 秒拼接把手和逐秒 RMS 门槛完成 5 段生成，统一使用 RVC +4 并动态应用 +6.7 dB 人声增益

### 进行中
- [ ] 等待用户试听 runs/unhappy_context_plus4_v4/final_feibi_song.wav 后决定是否验收 F22

### 已知问题
- 没有 CloudMist/OpenAI API Key，本次歌词改写使用 local_rule_fallback，F12 仍未验收；
- CTranslate2 CUDA 缺 cublas64_12.dll，本次 faster-whisper 使用 CPU int8；
- ACE-Step 和 RVC 依赖分别要求 Python 3.11 与 Python 3.10，必须保持独立 venv；
- 动态响度和逐秒覆盖率检查依赖 ffmpeg，部署环境必须提供 ffmpeg；CloudMist 云端 LLM 仍需 API Key；
- ACE-Step 固定 seed 仍可能出现候选波动，因此当前最多尝试 seed 44、43、45-50。

### 下一步
1. 用户试听 v4 完整 WAV 或 MP3；
2. 重点检查 30 秒后歌词覆盖、40 秒后音质和四个动态切点连续性；
3. 根据试听结论决定是否调整候选门槛或上下文边界；
4. 试听通过后标记 F22 passing 并本地提交；
5. 明确允许后才推送。
