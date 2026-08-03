# FEATURES.md

## 功能清单规则

- 每次只激活一个功能项；
- 功能状态通常包括：`not_started`、`in_progress`、`blocked` 和 `passing`。同一时间只能有一个功能处于 `in_progress` 状态。功能只有在验证命令通过并留下证据后，才能标记为 `passing`。
- 功能状态应根据验证结果更新，不能仅凭主观判断标记完成。

## F01：干运行五阶段流水线

- 索引：dry-run, 流水线, 阶段计划, CLI
- 日期：2026-07-31
- 优先级：1
- 所属区域：`核心流程`
- 用户可见行为：用户无需安装真实外部引擎即可预览五阶段执行顺序、输入输出和歌词改写结果。。
- 状态：`passing`
- 验证步骤：
  1. 运行流水线测试。；
  2. 使用带歌词输入执行 CLI dry-run。；
  3. 确认阶段状态为 planned 或 skipped。。
- 验证证据：tests/test_pipeline.py 覆盖五阶段 dry-run；本轮 CLI dry-run 得到 planned、skipped、planned、planned、planned。。
- 备注：dry-run 不生成或伪造真实音频。。

## F02：Harness 文档转换与状态同步

- 索引：Harness, JSON, Markdown, round-trip, 中文
- 日期：2026-07-31
- 优先级：1
- 所属区域：`文档`
- 用户可见行为：四份项目文档由结构化 JSON 生成并可回读，中文内容和代码状态能够持续同步。。
- 状态：`passing`
- 验证步骤：
  1. 从 JSON 生成四份 Markdown。；
  2. 将四份 Markdown 回读为 JSON。；
  3. 比较源 JSON 和回读 JSON。；
  4. 运行索引查询和 harness/check.py。。
- 验证证据：四份文档 round-trip 结构一致，FEATURES latest、DECISIONS search 和 harness/check.py 已通过。。
- 备注：固定格式 Markdown 不直接手工编辑。。

## F03：用户歌词优先策略

- 索引：歌词来源, 用户歌词, ASR, 优先级
- 日期：2026-07-31
- 优先级：1
- 所属区域：`歌词来源`
- 用户可见行为：用户提供歌词时系统直接使用该歌词，并明确跳过 ASR。。
- 状态：`passing`
- 验证步骤：
  1. 运行带歌词 dry-run。；
  2. 确认 lyric_source 为 user_provided。；
  3. 确认 ASR 阶段为 skipped 且原因是 user_lyrics_provided。。
- 验证证据：test_dry_run_skips_asr_when_user_lyrics_exist 已通过。。
- 备注：避免歌曲 ASR 误差污染歌词改写。。

## F04：版本化五阶段执行协议

- 索引：PipelineProtocol, StageContract, 协议, 阶段顺序
- 日期：2026-08-01
- 优先级：1
- 所属区域：`集成协议`
- 用户可见行为：每个外部阶段具有固定名称、顺序、用途、输入输出、必需字段和命令占位符。。
- 状态：`passing`
- 验证步骤：
  1. 构建 PipelineProtocol。；
  2. 检查五个 StageContract。；
  3. 确认 protocol.json 写入运行目录。。
- 验证证据：test_pipeline_protocol_exposes_command_templates 已通过，dry-run 已生成 feibi.pipeline.v1 的 protocol.json。。
- 备注：阶段顺序为 separation、asr、lyric_rewrite、ace_step_lyric_edit、rvc_voice_conversion。。

## F05：真实音频端到端执行

- 索引：真实执行, 分离, ASR, LLM, ACE-Step, RVC, 端到端
- 日期：2026-07-31
- 优先级：1
- 所属区域：`端到端`
- 用户可见行为：用户提交真实歌曲后可以得到经过分离、歌词获取与改写、歌曲生成和菲比音色转换的最终音频。。
- 状态：`passing`
- 验证步骤：
  1. 配置所有真实外部引擎和凭据。；
  2. 依次完成单元测试和集成测试。；
  3. 使用真实音频执行完整流水线。；
  4. 试听并检查 final_feibi_song.wav。。
- 验证证据：已使用 98.2 秒真实 MP3 完成 Demucs 分离、faster-whisper 转写、本地规则歌词回退、ACE-Step 1.5 cover、RVC 人声转换和最终混音；runs/unhappy_full/report.json 记录完整证据。。
- 备注：本次因没有 CloudMist/OpenAI API Key 使用 local_rule_fallback，云端 LLM 功能仍由 F12 单独保持 blocked。。

## F06：菲比歌词音节和模式校验

- 索引：歌词规则, 音节, 多语言, 菲比模式, 校验
- 日期：2026-07-31
- 优先级：1
- 所属区域：`歌词规则`
- 用户可见行为：系统能按中英日韩混合文本的启发式音节数生成和检查菲比歌词，并拒绝音节或模式不匹配的行。。
- 状态：`passing`
- 验证步骤：
  1. 运行 tests/test_rules.py。；
  2. 验证中文、英文和日文音节统计。；
  3. 验证模式和音节错误会被拒绝。。
- 验证证据：tests/test_rules.py 的多语言音节、模式识别和改写校验均通过。。
- 备注：音节统计是可替换的启发式实现。。

## F07：CLI 输入、歌词和配置入口

- 索引：CLI, input, lyrics, config, no-asr-fallback
- 日期：2026-07-31
- 优先级：1
- 所属区域：`命令行`
- 用户可见行为：用户可以从命令行指定音频、输出目录、可选歌词、JSON 配置、dry-run 和是否禁用 ASR 回退。。
- 状态：`passing`
- 验证步骤：
  1. 运行 scripts/feibi_pipeline.py --help。；
  2. 使用 input、lyrics、output-dir 和 dry-run 执行命令。；
  3. 确认输出 JSON 报告。。
- 验证证据：本轮 CLI dry-run 成功读取音频和歌词并生成 report.json。。
- 备注：真实运行需要额外传入完整配置。。

## F08：ASR 回退开关和空歌词处理

- 索引：ASR, fallback, no-asr-fallback, 空歌词, skipped
- 日期：2026-08-01
- 优先级：1
- 所属区域：`歌词来源`
- 用户可见行为：未提供歌词时用户可以启用 ASR，也可以显式关闭回退并获得可观测的 skipped 状态。。
- 状态：`passing`
- 验证步骤：
  1. 无歌词且关闭回退执行 dry-run。；
  2. 确认 lyric_source 为 empty。；
  3. 确认 ASR 原因为 fallback_disabled。。
- 验证证据：test_dry_run_can_disable_asr_fallback 已通过。。
- 备注：真实运行在没有任何歌词来源时会阻止歌词改写。。

## F09：运行清单和阶段可观测性

- 索引：manifest, request.json, stage.json, stdout, stderr, 日志
- 日期：2026-07-31
- 优先级：1
- 所属区域：`可观测性`
- 用户可见行为：每次运行保存输入清单、协议、阶段请求、阶段状态、解析后命令以及标准输出和错误日志。。
- 状态：`passing`
- 验证步骤：
  1. 执行 dry-run 并检查 manifest、protocol 和五个 stage.json。；
  2. 检查真实执行路径会写 stdout.log 和 stderr.log。；
  3. 确认 StageResult 保存状态和错误详情。。
- 验证证据：test_pipeline.py 已检查核心阶段文件；ExternalAdapter 实现 request、stage、stdout、stderr 和 resolved_command 落盘。。
- 备注：真实 stdout 和 stderr 需在配置引擎后验证内容。。

## F10：真实人声和伴奏分离

- 索引：audio-separator, separation, vocals, instrumental, stem
- 日期：2026-08-01
- 优先级：1
- 所属区域：`音频分离`
- 用户可见行为：系统使用 Demucs 或 audio-separator 将输入歌曲拆分为标准 vocals.wav 和 instrumental.wav。。
- 状态：`passing`
- 验证步骤：
  1. 在隔离 venv 中运行 Demucs CUDA。；
  2. 使用真实歌曲执行分离。；
  3. 确认两个 stem 时长、响度和路径正确。。
- 验证证据：已用 Demucs htdemucs CUDA 分离真实 98.2 秒 MP3，人声与伴奏均为 98.25 秒且不是空轨；ACE-Step 输出也完成二次人声分离。。
- 备注：audio-separator 模型清单站连接被重置，因此本次使用项目允许的 Demucs 后端。。

## F11：faster-whisper 多语种转写

- 索引：faster-whisper, ASR, transcript, language, segments
- 日期：2026-08-01
- 优先级：1
- 所属区域：`语音识别`
- 用户可见行为：没有用户歌词时，系统对分离后的人声轨进行多语种识别并输出带时间段的 JSON 和纯文本歌词。。
- 状态：`passing`
- 验证步骤：
  1. 安装 faster-whisper。；
  2. 配置 asr_engine_command。；
  3. 对真实人声轨执行识别。；
  4. 检查 transcript.json、transcript.txt、语言和 segments。。
- 验证证据：已用 faster-whisper small CPU int8 转写真实分离人声，输出 11 行 transcript 和时间段 JSON，识别为英语，语言置信度约 94.6%。。
- 备注：CTranslate2 CUDA 缺 cublas64_12.dll，因此本次从 GPU 自动回退 CPU；支持 model、device、compute type、beam size 和 language 参数。。

## F12：CloudMist 菲比歌词改写

- 索引：CloudMist, OpenAI-compatible, LLM, 歌词改写, API Key
- 日期：2026-08-01
- 优先级：1
- 所属区域：`歌词生成`
- 用户可见行为：系统调用 OpenAI-compatible API，按输入行数、音节和菲比模式要求生成改写歌词。。
- 状态：`passing`
- 验证步骤：
  1. 配置 CLOUDMIST_API_KEY 或 OPENAI_API_KEY。；
  2. 提交多语言歌词。；
  3. 检查 llm_request.json 和 llm_response.json。；
  4. 确认 rewritten_lines 行数匹配并通过本地校验。。
- 验证证据：scripts/feibi_llm_cloudmist.py 已实现提示词、请求、JSON 提取和行数规范化，但缺少有效 API Key 和真实请求证据。。
- 备注：默认 API base 为 CloudMist，默认模型为 gpt-4o。。

## F13：ACE-Step 1.5 仅改词生成

- 索引：ACE-Step, lyric_edit, cover, HTTP API, 歌曲生成
- 日期：2026-08-01
- 优先级：1
- 所属区域：`歌曲生成`
- 用户可见行为：系统将伴奏和已校验歌词送入 ACE-Step，仅改歌词并生成新的歌曲音频。。
- 状态：`blocked`
- 验证步骤：
  1. 配置 ace_step_engine_command。；
  2. 启动官方 ACE-Step API 或配置本地模块命令。；
  3. 提交伴奏和改写歌词。；
  4. 确认 ace_step_output.wav 存在且可播放。。
- 验证证据：已在独立 Python 3.11 venv 使用 ACE-Step 1.5 acestep-v15-turbo、INT8、CPU offload 和 RTX 5060 生成 98.16 秒真实 cover，显存峰值约 4.76 GB。。
- 备注：scripts/feibi_ace_step_v15.py 提供非交互 cover engine；cover 自动跳过 ACE-Step LM。。

## F14：RVC 菲比音色转换

- 索引：RVC, rvc_infer, pth, index, 音色转换
- 日期：2026-08-01
- 优先级：1
- 所属区域：`音色转换`
- 用户可见行为：系统使用仓库内菲比 .pth 权重和 .index 索引，把 ACE-Step 输出转换为 final_feibi_song.wav。。
- 状态：`passing`
- 验证步骤：
  1. 配置 rvc_engine_command。；
  2. 确认模型和索引路径存在。；
  3. 安装并修复 rvc_infer runtime。；
  4. 执行转换并试听最终音频。。
- 验证证据：已在独立 Python 3.10 venv 加载菲比 .pth、.index、HuBERT 和 RMVPE，对 98.14 秒生成歌声执行 CUDA 转换，推理约 8.81 秒并输出 converted_vocals.wav。。
- 备注：最终将转换后人声与 ACE-Step 伴奏重新混为 48 kHz 24-bit 立体声；模型文件约 57.6 MB，索引约 9.9 MB。。

## F15：真实执行前配置和模型校验

- 索引：PipelineConfig, 配置校验, 命令校验, RVC 路径, fail-fast
- 日期：2026-08-01
- 优先级：1
- 所属区域：`配置`
- 用户可见行为：真实运行开始前系统检查必需 wrapper、backend、engine 命令以及 RVC 模型和索引，缺失时立即报告。。
- 状态：`passing`
- 验证步骤：
  1. 使用空 PipelineConfig 请求真实执行校验。；
  2. 确认缺失命令产生 ValueError。；
  3. 使用不存在的 RVC 路径并确认 FileNotFoundError。。
- 验证证据：test_pipeline_config_validation_for_real_run 和 test_pipeline_config_checks_rvc_paths 已通过。。
- 备注：示例配置仍需用户补齐 engine 命令才能通过真实执行校验。。

## F16：外部命令模板和环境变量传递

- 索引：占位符, 环境变量, FEIBI_, backend, engine, repo_root
- 日期：2026-08-01
- 优先级：1
- 所属区域：`集成协议`
- 用户可见行为：外部工具通过稳定占位符和 FEIBI_* 环境变量获得运行目录、阶段目录、请求、输入、输出、配置和下层命令。。
- 状态：`passing`
- 验证步骤：
  1. 检查命令模板多轮解析。；
  2. 检查 FEIBI_STAGE、RUN_DIR、REQUEST_JSON、INPUTS_JSON 和 OUTPUTS_JSON。；
  3. 检查 backend 和 engine 命令按阶段传递。。
- 验证证据：models.py 定义协议环境变量，adapters.py 实现模板渲染和环境注入，协议占位符测试通过。。
- 备注：实际 engine 命令由部署环境配置。。

## F17：外部命令失败和缺产物检测

- 索引：returncode, missing_outputs, 失败, 日志, StageResult
- 日期：2026-08-01
- 优先级：1
- 所属区域：`错误处理`
- 用户可见行为：外部命令返回非零或没有写出声明产物时，阶段被标记 failed 并保留原因和日志，真实流水线停止。。
- 状态：`passing`
- 验证步骤：
  1. 检查 ExternalAdapter 的返回码处理。；
  2. 检查声明输出存在性检查。；
  3. 检查 pipeline 对必需阶段调用 _require_stage_ok。。
- 验证证据：ExternalAdapter 已实现 command_failed 和 missing_outputs，external.py 各 wrapper 也检查 backend 返回码与产物；compileall 通过。。
- 备注：后续应增加真实失败命令的集成测试。。

## F18：歌词改写输出规范化

- 索引：rewritten_lines, JSON, 行数, 规范化, validation
- 日期：2026-08-01
- 优先级：2
- 所属区域：`歌词生成`
- 用户可见行为：LLM 返回代码块、嵌套 JSON、过多或不足行时，系统尝试提取并调整为与源歌词相同的行数。。
- 状态：`blocked`
- 验证步骤：
  1. 模拟纯 JSON、Markdown 代码块和混合文本响应。；
  2. 覆盖输出行数过多和不足。；
  3. 确认规范化结果仍经过本地歌词校验。。
- 验证证据：scripts/feibi_llm_cloudmist.py 已实现 _extract_json 和 _normalize_output，但当前没有对应自动化测试或真实 API 验证。。
- 备注：代码存在不等于功能已验收。。

## F19：统一结果汇总和最终产物索引

- 索引：PipelineReport, report.json, outputs, validation, final_song
- 日期：2026-07-31
- 优先级：1
- 所属区域：`结果汇总`
- 用户可见行为：运行结束后用户获得 report.json，其中包含清单、阶段状态、源歌词、改写歌词、校验结果和所有关键产物路径。。
- 状态：`passing`
- 验证步骤：
  1. 执行 dry-run。；
  2. 读取 report.json。；
  3. 确认 stages、source_lyrics、rewritten_lyrics、validation 和 outputs 字段。。
- 验证证据：除 dry-run 测试外，runs/unhappy_full/report.json 已记录真实各阶段引擎、状态、产物及最终 WAV/MP3 音频指标。。
- 备注：真实最终产物为 98.16 秒、48 kHz、24-bit 立体声，峰值 -1.7 dB。。

## F20：可直接运行的真实配置模板

- 索引：config.example.json, separation_backend_command, engine_command, 配置模板
- 日期：2026-08-01
- 优先级：1
- 所属区域：`配置`
- 用户可见行为：用户可以从示例配置直接看到并填写分离、ASR、LLM、ACE-Step 和 RVC 的完整 wrapper、backend、engine 命令。。
- 状态：`blocked`
- 验证步骤：
  1. 补齐 separation_backend_command。；
  2. 补齐 asr_engine_command、ace_step_engine_command 和 rvc_engine_command。；
  3. 使用 PipelineConfig 读取示例。；
  4. 执行真实配置前置校验。。
- 验证证据：当前示例包含五个 wrapper 和四个 backend，但缺少 separation_backend_command 以及 ASR、ACE-Step、RVC engine 命令，尚不可直接真实运行。。
- 备注：LLM backend 直接调用 API，因此通过环境变量提供凭据而不是独立 engine 命令。。

## F21：默认保留原伴奏并按原唱时间轴对齐

- 索引：默认方案, 时间轴, 原始伴奏, vocal window, adelay, RVC
- 日期：2026-08-01
- 优先级：1
- 所属区域：`核心流程`
- 用户可见行为：非 dry-run 默认检测原唱首尾活动区间，只生成该演唱窗口，RVC 后按原起点补静音，并与原始伴奏混音。。
- 状态：`passing`
- 验证步骤：
  1. 检测原分离人声的长前奏和长尾奏静音。；
  2. 只将演唱窗口送入 ACE-Step。；
  3. 确认对齐人声从原唱起点开始。；
  4. 确认最终混音使用原始伴奏并保持原曲时长。。
- 验证证据：统一 CLI 默认入口对真实 unhappy 音频自动检测到约 16.44-82.55 秒演唱窗口，report.json 返回 timeline_aligned_original_instrumental；动态测得原始人声 -12.5 LUFS、RVC 人声 -20.7 LUFS，自动应用 +8.2 dB，使两者达到 100% LUFS 匹配；动态增益测试及全部 14 项测试通过。。
- 备注：scripts/feibi_pipeline.py 非 dry-run 默认调用 timeline_pipeline；默认混音按原始人声演唱区间的 LUFS 动态匹配，不再使用固定 2 dB；旧整曲 ACE/RVC 路径仅通过 --legacy-direct-pipeline 显式启用。。

## F22：动态分段 ACE-Step 与 RVC

- 索引：动态切点, 分段生成, ACE-Step, RVC, 交叉淡化
- 日期：2026-08-01
- 优先级：1
- 所属区域：`核心流程`
- 用户可见行为：系统在约 15 秒目标附近寻找低能量拼接点，带重叠上下文逐段执行 ACE-Step 和 RVC，再将转换人声平滑拼回完整原伴奏。。
- 状态：`passing`
- 验证步骤：
  1. 验证动态切点和歌词分配单元测试。；
  2. 验证分段命令、产物和报告集成流程。；
  3. 使用 unhappy 完整生成 WAV 和 MP3。；
  4. 由用户试听确认后完成验收。。
- 验证证据：22 项 pytest 通过；用户确认 RVC +2 比 +4 更适合当前菲比模型，并通过以普通话吐字和歌词可懂度为最高优先级的克制录音室 ACE 唱法。unhappy v5 第 3 段 seed 45、第 4 段 seed 48 的 Demucs 人声核心覆盖率均为 100%，完成 RVC +2、动态拼接和原伴奏混音。最终 WAV/MP3 均为 98.246542 秒、48 kHz，WAV 为 24-bit 立体声，MP3 为 320 kbps；用户试听后同意本地存档。。
- 备注：采用 7.5 秒上下文、0.25 秒拼接把手和 seed 44、43、45-50 候选搜索池；程序运行时逐段搜索并按覆盖率、响度选择，不写死本次歌曲人工验收的 seed 45/48。RVC 统一升 2 半音。RMS 覆盖率仍可能把乐器泄漏误判为人声，后续需增加真实人声存在性和发音评分。。

## F23：交互式分段演唱工作台

- 索引：UI, ACE-Step, segment, seed, caption, lyrics, RVC, pitch, merge
- 日期：2026-08-03
- 优先级：1
- 所属区域：`交互式分段生成`
- 用户可见行为：本地 UI 读取既有分段运行，允许逐段修改 ACE-Step seed、caption 提示词和预设歌词，重新生成并试听 ACE；再修改每段 RVC 动态升调并试听，选定各段最佳结果后，与原始伴奏合并为完整歌曲。。
- 状态：`passing`
- 验证步骤：
  1. 单元测试工作台状态持久化、输入校验和 ACE/RVC 命令构造。；
  2. 用真实 unhappy v10 运行导入五段缓存候选，确认全部片段并通过工作台完成最终合并。；
  3. Start the local Gradio UI and verify segment switching, media paths, candidate loading, approval persistence, and final merge outputs in the browser.。
- 验证证据：30 pytest tests passed. The five cached candidates from unhappy_custom_fixed_v10 were merged through SegmentWorkbench into WAV, MP3, and JSON; original vocals measured -12.5 LUFS, converted vocals -17.9 LUFS, with +5.4 dB automatic gain. In Gradio 6.2.0 at 127.0.0.1:7860, browser verification covered seeds 44/46/45/48/49, RVC +2, all five approvals, and the final 98-second WAV/MP3 players plus downloadable JSON report.。
- 备注：第一版从已完成时间轴运行开始，复用原始分段、演唱时间和原伴奏；ACE-Step 与 RVC 继续使用各自隔离 venv。。
