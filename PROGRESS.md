# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `3b65bec`（跑通真实菲比演唱链路）
- 测试状态：项目独立 Python 3.11 venv 中 14 项 pytest 通过；真实 98.2 秒音频完成时间轴对齐、动态 LUFS 人声匹配、RVC 和原始伴奏混音验证
- Lint：默认真实入口按原人声 LUFS 动态计算增益；本次实际从 -20.7 LUFS 匹配到 -12.5 LUFS，应用 +8.2 dB

### 已完成
- [x] 已用 Demucs CUDA 对用户 MP3 和 ACE-Step 输出完成真实人声/伴奏分离
- [x] 已支持用户歌词优先并用本地规则生成通过校验的菲比歌词
- [x] 已用 ACE-Step 1.5 turbo 生成原唱活动窗口，并用 RVC 菲比模型转换生成歌声
- [x] 已将 RVC 歌声按自动检测的原唱起点延迟并混回原始伴奏，前奏约 0-16.44 秒无人声
- [x] 已将原固定 2 dB 改为原人声 LUFS 100% 动态匹配，本次应用 +8.2 dB

### 进行中
- [ ] 继续完善默认时间轴路径的安装配置，并补充 CloudMist API Key 后验证云端 LLM 分支

### 已知问题
- 没有 CloudMist/OpenAI API Key，本次歌词改写使用 local_rule_fallback，F12 仍未验收；
- CTranslate2 CUDA 缺 cublas64_12.dll，本次 faster-whisper 使用 CPU int8；
- ACE-Step 和 RVC 依赖分别要求 Python 3.11 与 Python 3.10，必须保持独立 venv；
- 动态响度匹配依赖 ffmpeg ebur128，部署环境必须提供 ffmpeg；CloudMist 云端 LLM 仍需 API Key。

### 下一步
1. 补齐默认时间轴方案的一键环境安装和模型准备说明；
2. 补齐 config.example.json 的独立 venv engine 命令和基础模型路径；
3. 获得 LLM API Key 后验证 CloudMist 分支并替换 local_rule_fallback；
4. 试听最终音频并根据实际听感调整 ACE cover strength、RVC index rate 和人声混音比例。
