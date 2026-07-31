# 菲比演唱器

## 项目说明
本项目是一个可插拔的音乐改写与歌声转换流水线。输入歌曲，分离人声和伴奏，识别多语言歌词，按照菲比规则改写，再调用 ACE-Step 1.5 和 RVC 。

## 技术栈
- Python 3.11+
- pytest 用于测试
- 外部工具：Demucs/UVR、Whisper/faster-whisper、ACE-Step 1.5、RVC

## 目录
- `feibi_singer/`：核心代码
- `scripts/`：命令行入口
- `tests/`：测试
- `config.example.json`：配置示例
- `ARCHITECTURE.md`：架构
- `FEATURES.md`：功能清单
- `PROGRESS.md`：进度
- `DECISIONS.md`：决策

## 常用命令
```powershell
pytest -q
python scripts\feibi_pipeline.py --input .\song.wav --lyrics .\lyrics.txt --output-dir .\runs\demo --dry-run
```

## 开发约束
- 每次只实现一个功能点
- dry-run 不得伪装已生成音频
- 音节数必须由本地规则校验
- 不提交用户音频、模型权重、密钥或生成物

## 完成定义
必须依次通过：单元测试、集成测试、端到端流程验证。
