# ARCHITECTURE.md

## 模块说明
Feibi Singer is a pluggable local audio pipeline. It accepts a song file and optional lyrics, prefers user-provided lyrics, and falls back to ASR only when lyrics are missing. The pipeline prepares audio, obtains or reads lyrics, rewrites lyrics, generates a new song with ACE-Step 1.5, and converts the vocals with the supplied RVC Feibi voice. The current implementation emphasizes clear stage boundaries, rule validation, and dry-run verification; real models are connected through external adapters and user configuration.

## 目录结构
- `feibi_singer/models.py`：Defines the PipelineConfig, StageResult, and PipelineReport data structures；
- `feibi_singer/feibi_rules.py`：Implements heuristic multilingual syllable counting, Feibi pattern generation, and lyric rule checks；
- `feibi_singer/adapters.py`：Wraps the external boundaries for separation, ASR, ACE-Step, and RVC; dry-run mode only produces stage plans；
- `feibi_singer/pipeline.py`：The single orchestration entry point for stage order, artifact persistence, and final reporting；
- `scripts/feibi_pipeline.py`：Command-line entry point that reads input audio, lyrics, and JSON configuration, then starts the pipeline；
- `tests/test_rules.py`：Unit tests for Feibi rules and multilingual syllable counting；
- `tests/test_pipeline.py`：Integration tests for the dry-run pipeline；
- `config.example.json`：Configuration template for external commands, device, language, and RVC model paths；
- `AGENT.md`：Project-level development constraints, Harness workflow, and verification requirements；
- `ARCHITECTURE.md`：Project architecture, directory responsibilities, and design constraints；
- `PROGRESS.md`：Current verification status, completed work, work in progress, and next steps；
- `FEATURES.md`：Feature list maintained by priority with verification evidence；
- `DECISIONS.md`：Important technical decisions, reasons, alternatives, and impact；
- `harness/harness_context.py`：Harness JSON/Markdown conversion and index query tool；
- `harness/ARCHITECTURE.md`：Harness submodule structure, usage, and constraints；

## 设计约束
- pipeline.py only orchestrates the flow and does not directly implement external model inference；
- All external models and commands must go through adapters.py; do not build shell commands in business logic；
- User-provided lyrics have priority over ASR; ASR is only a fallback when lyrics are missing；
- Candidate lyrics produced by the LLM must pass the Feibi syllable, pattern, and ending checks before they can reach ACE-Step；
- Every stage must have an explicit status; dry-run can only generate plans and reports, never fake audio outputs；
- The current syllable counter is a heuristic; a professional language syllable counter can be swapped in later；
- Real execution depends on user-provided separation tools, ASR, ACE-Step 1.5, RVC, and Feibi model paths; the repository does not store model weights or user audio；
- Harness Markdown files must be generated or converted from JSON through harness/harness_context.py instead of being edited directly；
