from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PipelineConfig:
    separation_command: str = ""
    asr_command: str = ""
    llm_command: str = ""
    ace_step_command: str = ""
    rvc_command: str = ""
    rvc_model: str = ""
    device: str = "cuda"
    language: str = "auto"

    def as_dict(self) -> dict[str, Any]:
        return {
            "separation_command": self.separation_command,
            "asr_command": self.asr_command,
            "llm_command": self.llm_command,
            "ace_step_command": self.ace_step_command,
            "rvc_command": self.rvc_command,
            "rvc_model": self.rvc_model,
            "device": self.device,
            "language": self.language,
        }


@dataclass(frozen=True)
class StageResult:
    name: str
    status: str
    artifact: Path | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "artifact": str(self.artifact) if self.artifact else None,
            "details": self.details,
        }


@dataclass
class PipelineReport:
    run_dir: Path
    dry_run: bool
    stages: list[StageResult]
    input_manifest: dict[str, Any]
    source_lyrics: list[str]
    rewritten_lyrics: list[str]
    validation: dict[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_dir": str(self.run_dir),
            "dry_run": self.dry_run,
            "input_manifest": self.input_manifest,
            "stages": [stage.as_dict() for stage in self.stages],
            "source_lyrics": self.source_lyrics,
            "rewritten_lyrics": self.rewritten_lyrics,
            "validation": self.validation,
            "outputs": self.outputs,
        }
