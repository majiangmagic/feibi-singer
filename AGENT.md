# 菲比演唱器

## 项目说明
本项目是一个可插拔的音乐改写与歌声转换流水线。输入歌曲，分离人声和伴奏，识别多语言歌词，按照菲比规则改写，再调用 ACE-Step 1.5 和 RVC 。

## 技术栈
- Python 3.11+
- pytest 用于测试
- 外部工具：Demucs/UVR、Whisper/faster-whisper、ACE-Step 1.5、RVC

## 常用命令
```powershell
pytest -q
python scripts\feibi_pipeline.py --input .\song.wav --lyrics .\lyrics.txt --output-dir .\runs\demo --dry-run
```

## 开发约束
- 所有编辑md文件的方式都是通过`\harness\harness_context.py`脚本去编辑json转换成md文件或者反过来使用脚本把md转换成json格式读取内容、且对于`FEATURES.md`、`DECISIONS.md`请使用索引搜索或者最新5条、绝对禁止直接读取md文件只允许脚本读取和生成到指定位置。
- 本项目架构说明见项目根目录下 `ARCHITECTURE.md`，子模块的架构设计说明见相关子模块目录的`ARCHITECTURE.md`
- 判断需要时可以读 `DECISIONS.md` 了解历史做过的重要决策和决策的原因，但不要每次都读取；
- 每次只做一个功能点，如果一次会话涉及多个功能点，无法一次会话完成，则应先将它们记录到 `FEATURES.md`，再按照优先级选取第一个功能点完成；尤其禁止在实现功能 A 时顺便重构功能 B。
- 开发一个功能点过程中，有任何一步完成就去更新`PROGRESS.md`，实时状态更新和规划下一步。
- 每次开发必须严格遵守 [Git 检查点约束]

## Git 检查点约束
- 所有工作从最近一次稳定提交开始；
- 每完成一个功能并通过验证后，立刻提交一次，判定完成的方式严格遵守[完成定义]。

## 完成定义
- 功能完成 = 端到端验证通过，不是“代码写完了”；
- 必须运行的验证层级：
  1. 单元测试通过；
  2. 集成测试通过；
  3. 端到端流程验证通过；
- 在第 1 层没通过时，不许进入第 2 层；
- 在第 2 层没通过时，不许进入第 3 层。

## 每次会话开始时
1. 读 `PROGRESS.md` 了解当前状态；
2. 在当前状态没有下一步工作，或者本次对话提出的内容涵盖了新的功能点，或者`PROGRESS.md`当前状态的内容没有做完就被提交了新任务时打开 `FEATURES.md` 功能清单，分析是否需要添加功能点、或者需要选取一项功能点开始工作；
3. 回到 `PROGRESS.md` 分析是否需要更新其内容后，从最新的“下一步”部分开始工作。

## 每次会话结束前
1. 按需更新 `PROGRESS.md`、`FEATURES.md`、`DECISIONS.md`，以及本次修改涉及的 `ARCHITECTURE.md`、 `PROGRESS.md`更新时已完成、进行中、已知问题、下一步的条目最多5条酌情删除；
2. 运行`\harness\check.py`脚本，并根据check脚本的指示解决问题，然后再次运行`\harness\check.py`脚本，直到通过。
3. 提交所有已完成且通过验证的工作。