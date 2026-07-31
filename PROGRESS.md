# PROGRESS.md

## 项目进度

### 当前状态
- 最新 commit: `5553e6f`（接实音频流水线接口）
- 测试状态：已通过 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q，10 项测试通过；compileall、文档 round-trip、Harness 索引查询和 check.py 均已通过
- Lint：代码已完成五阶段协议、wrapper/backend/engine 接线和真实桥接脚本；FEATURES 已按独立验收能力从 6 项补齐为 20 项

### 已完成
- [x] 已实现 separation、asr、lyric_rewrite、ace_step_lyric_edit、rvc_voice_conversion 五阶段协议
- [x] 已实现用户歌词优先和 ASR 备用分支，用户提供歌词时 ASR 明确 skipped
- [x] 已实现 dry-run 阶段计划、输入清单、协议、歌词改写、校验、阶段报告和总报告产物
- [x] 已接入 wrapper/backend/engine 三层命令协议、阶段环境变量上下文、真实桥接脚本，并将 RVC 模型和索引配置统一到仓库 models/rvc/ 路径
- [x] 已通过 Harness 从 JSON 重新生成四份中文文档，将功能清单补齐为 20 项，并完成 Markdown→JSON round-trip、索引查询和 check.py 验证

### 进行中
- [ ] 继续补齐真实环境中的分离、ASR、LLM、ACE-Step 和 RVC engine 命令及凭据

### 已知问题
- 真实端到端仍需要可用的音频分离工具、ASR 模型、LLM API Key、ACE-Step engine/API、RVC runtime 和模型文件；
- config.example.json 当前提供的是仓库脚本模板，真实 engine 命令和凭据仍需用户配置；
- Python 3.13 环境的 pytest 自动加载了不兼容的第三方 hydra 插件，验证时需要设置 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1；
- 真实运行尚未用一份实际音频完成从分离到 RVC 的端到端验证。

### 下一步
1. 补齐 separation_backend_command 及 ASR、ACE-Step、RVC engine 命令模板；
2. 配置真实环境中的分离、ASR、LLM、ACE-Step 和 RVC 依赖及凭据；
3. 在真实依赖齐备后按单元测试、集成测试、端到端流程顺序验证。
