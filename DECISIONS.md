# DECISIONS.md

## 使用用户歌词作为首选来源

- 索引：歌词来源, 用户歌词, ASR, 备选
- 日期：2026-07-31
- 状态：adopted
- 决策：用户提供歌词时直接使用用户歌词并跳过 ASR；只有歌词为空且启用回退时才执行 ASR。
- 原因：歌曲 ASR 容易产生漏字、错字和分段误差，用户原始歌词更适合作为改写和音节校验的来源。
- 放弃方案：不把 ASR 设为唯一歌词入口，也不在用户已提供歌词时强制调用 ASR。
- 影响：CLI 保留可选 lyrics 输入，流水线写入 lyric_source，并在阶段报告中明确记录 ASR skipped 或执行状态。

## RVC 模型和索引仓库本地化

- 索引：RVC, 模型, 索引, models/rvc
- 日期：2026-07-31
- 状态：adopted
- 决策：RVC 配置同时保存 .pth 模型和 .index 检索索引，示例路径统一指向仓库 models/rvc/。
- 原因：避免依赖桌面路径，并确保 RVC 推理同时获得音色权重和检索索引。
- 放弃方案：不在运行时依赖个人机器路径或默认索引自动发现。
- 影响：PipelineConfig 校验两个路径，rvc_infer 在真实执行前检查文件存在并安装到 RVC runtime 的模型目录。

## 固定五阶段流水线协议

- 索引：阶段, 协议, separation, ASR, LLM, ACE-Step, RVC
- 日期：2026-08-01
- 状态：adopted
- 决策：流水线固定为 separation、asr、lyric_rewrite、ace_step_lyric_edit、rvc_voice_conversion 五个可执行阶段，并为每阶段声明输入、输出、必需字段和命令占位符。
- 原因：明确阶段边界后才能独立接入真实命令、落盘中间产物并定位失败点。
- 放弃方案：不把 ASR、歌词改写、生成和变声合并为一个不可观测的大命令。
- 影响：协议写入 protocol.json，阶段请求和 stage.json 写入各自目录，失败时按阶段停止并保留日志。

## 分离 wrapper、backend 和 engine 命令

- 索引：wrapper, backend, engine, 外部命令, 环境变量
- 日期：2026-08-01
- 状态：adopted
- 决策：统一使用 wrapper 命令调用阶段协议入口，wrapper 再调用 backend，backend 再调用用户配置的真实 engine 命令；对应命令和 FEIBI_* 环境变量分层传递。
- 原因：协议层、适配层和真实工具参数变化频繁，分层可以替换实现并保留统一阶段上下文。
- 放弃方案：不在 pipeline.py 中直接拼接具体 ASR、ACE-Step 或 RVC 工具命令。
- 影响：PipelineConfig 同时支持 *_COMMAND、*_BACKEND_COMMAND 和 *_ENGINE_COMMAND；真实执行会记录 resolved command、stdout 和 stderr。

## 固定格式文档由 Harness 生成

- 索引：Harness, Markdown, JSON, 文档同步, round-trip
- 日期：2026-08-01
- 状态：adopted
- 决策：四份项目文档必须先维护结构化 JSON，再使用 harness_context.py 生成 Markdown；读取、索引和最新记录查询也通过脚本完成。
- 原因：避免 Markdown 章节、字段、标点和状态格式漂移，并让 check.py 能稳定验证。
- 放弃方案：不直接手工编辑固定格式 Markdown，也不把 FEATURES.md 和 DECISIONS.md 当作无结构文本读取。
- 影响：每轮会话结束前必须生成文档、执行 Markdown→JSON 回读和 check.py；FEATURES 与 DECISIONS 支持关键词搜索和 latest 查询。

## 当前优先接实链路而非新增测试

- 索引：优先级, 真实链路, 测试, 验证
- 日期：2026-08-01
- 状态：adopted
- 决策：当前阶段先完成真实外部命令和配置接线；不主动增加无关测试，但必须运行现有单元、集成和 dry-run 验证。
- 原因：核心风险在外部工具和配置能否真正协作，先接实链路比扩大测试数量更重要。
- 放弃方案：不在真实命令未配置前把主要工作转为新增测试覆盖率。
- 影响：功能状态只能依据现有验证证据标记；真实端到端仍保持 in_progress，不能写成 passing。
