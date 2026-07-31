# FEATURES.md

## 功能清单规则

- 每次只激活一个功能项；
- 功能状态通常包括：`not_started`、`in_progress`、`blocked` 和 `passing`。同一时间只能有一个功能处于 `in_progress` 状态。功能只有在验证命令通过并留下证据后，才能标记为 `passing`。
- 功能状态应根据验证结果更新，不能仅凭主观判断标记完成。

## F01：菲比 dry-run 流水线

- 索引：流水线, 歌词改写, dry-run, ACE-Step, RVC
- 日期：2026-07-31
- 优先级：1
- 所属区域：`流水线`
- 用户可见行为：用户提供歌曲并可选提供歌词后，可以执行 dry-run，得到符合菲比规则的改写歌词、验证结果、四个外部阶段计划以及最终报告；当没有歌词时，ASR 只作为备选输入。。
- 状态：`passing`
- 验证步骤：
  1. 运行规则单元测试；
  2. 运行流水线集成测试；
  3. 通过 scripts/feibi_pipeline.py 执行 CLI dry-run；
  4. 检查生成的歌词、验证文件、阶段计划和报告。
- 验证证据：2026-07-31 python -m compileall feibi_singer scripts tests；pytest -q 通过 6 项测试；CLI dry-run 写出了 input_manifest.json、rewritten_lyrics.json、validation.json、stages/*/stage.json 和 report.json。。
- 备注：真实模型推理仍依赖用户配置的外部工具和模型文件；当前定义覆盖的是可重复的 dry-run 流程。。

## F02：统一的 Harness Markdown 重新生成

- 索引：Harness, Markdown, ARCHITECTURE, PROGRESS, FEATURES, DECISIONS
- 日期：2026-07-31
- 优先级：2
- 所属区域：`文档`
- 用户可见行为：维护者可以使用 harness_context.py 从 JSON 生成所有固定格式上下文文档，并且可以做 round-trip、搜索和最新记录查询。。
- 状态：`passing`
- 验证步骤：
  1. 从策略 JSON 生成 ARCHITECTURE.md、PROGRESS.md、FEATURES.md 和 DECISIONS.md；
  2. 对每个生成的文件执行 md-to-json round-trip；
  3. 将 round-tripped 的 JSON 与源 JSON 对比；
  4. 验证 FEATURES.md 和 DECISIONS.md 的搜索与 latest 查询。
- 验证证据：2026-07-31 已验证：所有目标 Markdown 文件都由 UTF-8 JSON 通过 harness_context.py 生成；md-to-json round-trip 与源 JSON 一致；FEATURES/DECISIONS 的 search 和 latest 查询通过；git diff --check 通过。。
- 备注：AGENT.md 保持用户确认版本；.pytest_cache/README.md 不属于项目维护文档。。

## F03：菲比规则层

- 索引：歌词规则, 多语言, 音节计数, 歌词改写, 菲比
- 日期：2026-07-31
- 优先级：1
- 所属区域：`歌词`
- 用户可见行为：当用户提供音乐和可选歌词时，系统可以在保持音节数不变并尽量贴近原旋律感受的前提下，按菲比规则改写歌词。。
- 状态：`passing`
- 验证步骤：
  1. 运行 tests/test_rules.py；
  2. 验证多语言音节计数和菲比改写行为；
  3. 确认 validate_line 会阻止不符合规则的歌词。
- 验证证据：2026-07-31 tests/test_rules.py 通过 4 项测试；菲比歌词规则测试覆盖了多语言音节计数和改写验证。。
- 备注：当前规则层只处理歌词改写和验证，还没有接入 ASR、LLM、ACE-Step 1.5 或 RVC。。

## F04：端到端菲比流水线骨架

- 索引：流水线, ASR, LLM, ACE-Step, RVC
- 日期：2026-07-31
- 优先级：1
- 所属区域：`流水线`
- 用户可见行为：用户输入歌曲后，系统可以按固定顺序组织分离、ASR、歌词改写、ACE-Step 生成和 RVC 转换的产物，作为未来真实模型集成的骨架。。
- 状态：`passing`
- 验证步骤：
  1. 运行新的流水线骨架单元测试；
  2. 在 dry-run 中检查生成的阶段计划和产物目录；
  3. 确认输入清单、歌词改写输出和阶段计划文件都会被写出。
- 验证证据：2026-07-31 流水线骨架测试通过；dry-run 会写出按阶段组织的 artifact、report 和歌词验证文件。。
- 备注：这个骨架已经把“分离→ASR 备选→歌词改写→ACE-Step→RVC”的顺序固定下来，但真正音频推理仍待外部工具接入。。
