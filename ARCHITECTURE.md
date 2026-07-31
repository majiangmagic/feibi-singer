# ARCHITECTURE.md

## 模块说明
系统采用“编排器 + 可替换适配器”架构。

## 数据流
`input audio -> separation -> transcription -> lyric rewrite -> ACE-Step lyric edit -> RVC voice conversion -> output audio`

## 设计约束
- `models.py` 定义数据模型。
- `feibi_rules.py` 负责音节和菲比规则。
- `adapters.py` 负责外部工具调用边界。
- `pipeline.py` 是唯一的流程编排入口。
- LLM 输出必须经过本地规则校验。

## 外部能力
真实运行需要用户提供 ASR、分离工具、ACE-Step 1.5、RVC 和菲比模型路径。
