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

@dataclass
class StageResult:
    name: str
    status: str
    artifact: Path | None = None
    details: dict[str, Any] = field(default_factory=dict)

@dataclass
class PipelineReport:
    run_dir: Path
    dry_run: bool
    stages: list[StageResult]
    rewritten_lyrics: list[str]
    validation: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_dir": str(self.run_dir), "dry_run": self.dry_run,
            "stages": [{"name": s.name, "status": s.status, "artifact": str(s.artifact) if s.artifact else None, "details": s.details} for s in self.stages],
            "rewritten_lyrics": self.rewritten_lyrics, "validation": self.validation,
        }
