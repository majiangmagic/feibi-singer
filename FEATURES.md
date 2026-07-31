# FEATURES.md

## 功能清单规则

- 每次只激活一个功能项；
- 功能状态通常包括：`not_started`、`in_progress`、`blocked` 和 `passing`。同一时间只能有一个功能处于 `in_progress` 状态。功能只有在验证命令通过并留下证据后，才能标记为 `passing`。
- 功能状态应根据验证结果更新，不能仅凭主观判断标记完成。

## F01：菲比演唱 dry-run 流水线

- 索引：流水线, 歌词改写, dry-run, ACE-Step, RVC
- 日期：2026-07-31
- 优先级：1
- 所属区域：`pipeline`
- 用户可见行为：用户提供歌曲和可选歌词后，可以运行 dry-run，获得符合菲比规则的改写歌词、规则校验、四个外部阶段计划和最终报告。。
- 状态：`passing`
- 验证步骤：
  1. 运行规则单元测试；
  2. 运行流水线集成测试；
  3. 通过 scripts/feibi_pipeline.py 执行 CLI dry-run；
  4. 检查生成的歌词、校验文件、阶段计划和报告。
- 验证证据：2026-07-31 ???tests/test_rules.py 4 passed?tests/test_pipeline.py 1 passed?CLI dry-run ???? 4 ??????rewritten_lyrics.txt?validation.json ? report.json?。
- 备注：真实模型推理仍依赖用户配置外部工具和模型文件；当前完成定义覆盖可重复验证的 dry-run 流程。。

## F02：统一重生成 Harness Markdown 上下文文档

- 索引：Harness, Markdown, ARCHITECTURE, PROGRESS, FEATURES, DECISIONS
- 日期：2026-07-31
- 优先级：2
- 所属区域：`documentation`
- 用户可见行为：项目维护者可以使用 harness_context.py 从 JSON 生成全部固定格式上下文文档，并能回读、搜索和查询最新记录。。
- 状态：`passing`
- 验证步骤：
  1. 从规范 JSON 生成两份 ARCHITECTURE.md、PROGRESS.md、FEATURES.md 和 DECISIONS.md；
  2. 对每份生成结果执行 md-to-json 回读；
  3. 比较回读 JSON 与源 JSON；
  4. 验证 FEATURES.md 和 DECISIONS.md 的 search 与 latest 查询。
- 验证证据：2026-07-31 验证：5 份目标 Markdown 均由 harness_context.py 从 UTF-8 JSON 生成；全部 md-to-json 回读与源 JSON 完全一致；FEATURES/DECISIONS 的 search 与 latest 查询通过；git diff --check 通过。。
- 备注：AGENT.md 保留用户手工确认版本；.pytest_cache/README.md 不属于项目维护文档。。

## F03：菲比规则层

- 索引：歌词规则, 多语言, 音节计数, 歌词改写, Feibi
- 日期：2026-07-31
- 优先级：1
- 所属区域：`lyrics`
- 用户可见行为：当用户提供音乐与可选歌词时，系统可以在保持音节数量不变的前提下，根据菲比规则对歌词进行改写，并保持接近原始旋律的唱除感。。
- 状态：`passing`
- 验证步骤：
  1. 运行 tests/test_rules.py；
  2. 验证多语言音节计数和菲比规则改写；
  3. 确认 validate_line 能拦截不符合规则的歌词。
- 验证证据：2026-07-31 tests/test_rules.py 4 passed; Feibi lyric rule tests cover multilingual syllable counting and rewrite validation.。
- 备注：目前规则层只负责歌词改写与验证，还未接入 ASR、LLM、ACE-Step 1.5 和 RVC。。
