from __future__ import annotations

import json
from pathlib import Path
from .models import PipelineConfig, StageResult


class AdapterError(RuntimeError):
    pass


class ExternalAdapter:
    def __init__(self, config: PipelineConfig, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run

    def run(self, name: str, command: str, run_dir: Path, inputs: dict, outputs: dict | None = None) -> StageResult:
        stage_dir = run_dir / "stages" / name
        stage_dir.mkdir(parents=True, exist_ok=True)
        artifact = stage_dir / "stage.json"
        payload = {
            "stage": name,
            "command": command,
            "inputs": inputs,
            "outputs": outputs or {},
            "dry_run": self.dry_run,
        }
        artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if self.dry_run:
            return StageResult(name, "planned", artifact, {"mode": "dry_run"})
        if not command:
            return StageResult(name, "blocked", artifact, {"reason": "command_not_configured"})
        return StageResult(name, "prepared", artifact, {"mode": "integration_pending"})


class LLMAdapter(ExternalAdapter):
    def rewrite(self, lines: list[str], run_dir: Path) -> Path:
        stage_dir = run_dir / "stages" / "lyric_rewrite"
        stage_dir.mkdir(parents=True, exist_ok=True)
        artifact = stage_dir / "llm_request.json"
        artifact.write_text(
            json.dumps(
                {
                    "lyrics": lines,
                    "instruction": "Rewrite lyrics into Feibi-style syllable-preserving placeholders.",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return artifact
