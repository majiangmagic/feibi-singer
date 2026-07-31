from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PIPELINE_PROTOCOL_VERSION = "feibi.pipeline.v1"
PIPELINE_STAGE_ORDER = (
    "separation",
    "asr",
    "lyric_rewrite",
    "ace_step_lyric_edit",
    "rvc_voice_conversion",
)
PIPELINE_COMMAND_ENVIRONMENT = {
    "FEIBI_STAGE": "Current stage name.",
    "FEIBI_RUN_DIR": "Absolute run directory.",
    "FEIBI_STAGE_DIR": "Absolute stage directory.",
    "FEIBI_REQUEST_JSON": "Stage request JSON path.",
    "FEIBI_STAGE_REQUEST_JSON": "Alias for the stage request JSON path.",
    "FEIBI_INPUTS_JSON": "Serialized stage inputs.",
    "FEIBI_OUTPUTS_JSON": "Serialized stage outputs.",
    "FEIBI_CONFIG_JSON": "Serialized pipeline config.",
    "FEIBI_COMMAND": "Resolved shell command.",
    "FEIBI_BACKEND_COMMAND": "Resolved backend shell command.",
    "FEIBI_SEPARATION_BACKEND_COMMAND": "Resolved separation backend shell command.",
    "FEIBI_ASR_BACKEND_COMMAND": "Resolved ASR backend shell command.",
    "FEIBI_ASR_ENGINE_COMMAND": "Resolved ASR engine shell command.",
    "FEIBI_LLM_BACKEND_COMMAND": "Resolved lyric rewrite backend shell command.",
    "FEIBI_ACE_STEP_BACKEND_COMMAND": "Resolved ACE-Step backend shell command.",
    "FEIBI_ACE_STEP_ENGINE_COMMAND": "Resolved ACE-Step engine shell command.",
    "FEIBI_RVC_BACKEND_COMMAND": "Resolved RVC backend shell command.",
    "FEIBI_RVC_ENGINE_COMMAND": "Resolved RVC engine shell command.",
    "FEIBI_STAGE_CONTRACT_JSON": "Serialized stage contract.",
    "FEIBI_PROTOCOL_JSON": "Serialized pipeline protocol.",
}


@dataclass(frozen=True)
class StageContract:
    name: str
    purpose: str
    command: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    required_inputs: tuple[str, ...] = ()
    required_outputs: tuple[str, ...] = ()
    command_placeholders: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "command": self.command,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "required_inputs": list(self.required_inputs),
            "required_outputs": list(self.required_outputs),
            "command_placeholders": list(self.command_placeholders),
        }

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.name.strip():
            issues.append("stage contract name is empty")
        if not self.purpose.strip():
            issues.append(f"stage {self.name or '<unnamed>'} purpose is empty")
        if not self.inputs:
            issues.append(f"stage {self.name or '<unnamed>'} declares no inputs")
        if not self.outputs:
            issues.append(f"stage {self.name or '<unnamed>'} declares no outputs")
        if len(set(self.required_inputs)) != len(self.required_inputs):
            issues.append(f"stage {self.name or '<unnamed>'} has duplicate required inputs")
        if len(set(self.required_outputs)) != len(self.required_outputs):
            issues.append(f"stage {self.name or '<unnamed>'} has duplicate required outputs")
        return issues


@dataclass(frozen=True)
class PipelineProtocol:
    version: str
    stage_order: tuple[str, ...]
    command_environment: dict[str, str]
    stages: dict[str, StageContract]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "stage_order": list(self.stage_order),
            "command_environment": self.command_environment,
            "stages": {name: stage.as_dict() for name, stage in self.stages.items()},
        }

    def validate(self) -> list[str]:
        issues: list[str] = []
        missing = [name for name in self.stage_order if name not in self.stages]
        if missing:
            issues.append(f"protocol missing stage contracts: {', '.join(missing)}")
        extra = [name for name in self.stages if name not in self.stage_order]
        if extra:
            issues.append(f"protocol has unexpected stages: {', '.join(extra)}")
        for name in self.stage_order:
            stage = self.stages.get(name)
            if stage is None:
                continue
            if stage.name != name:
                issues.append(f"stage contract key {name} does not match contract name {stage.name}")
            issues.extend(stage.validate())
        return issues


@dataclass(frozen=True)
class PipelineConfig:
    separation_command: str = ""
    separation_backend_command: str = ""
    asr_command: str = ""
    asr_backend_command: str = ""
    asr_engine_command: str = ""
    llm_command: str = ""
    llm_backend_command: str = ""
    ace_step_command: str = ""
    ace_step_backend_command: str = ""
    ace_step_engine_command: str = ""
    rvc_command: str = ""
    rvc_backend_command: str = ""
    rvc_engine_command: str = ""
    rvc_model: str = ""
    rvc_index: str = ""
    device: str = "cuda"
    language: str = "auto"

    def as_dict(self) -> dict[str, Any]:
        return {
            "separation_command": self.separation_command,
            "separation_backend_command": self.separation_backend_command,
            "asr_command": self.asr_command,
            "asr_backend_command": self.asr_backend_command,
            "asr_engine_command": self.asr_engine_command,
            "llm_command": self.llm_command,
            "llm_backend_command": self.llm_backend_command,
            "ace_step_command": self.ace_step_command,
            "ace_step_backend_command": self.ace_step_backend_command,
            "ace_step_engine_command": self.ace_step_engine_command,
            "rvc_command": self.rvc_command,
            "rvc_backend_command": self.rvc_backend_command,
            "rvc_engine_command": self.rvc_engine_command,
            "rvc_model": self.rvc_model,
            "rvc_index": self.rvc_index,
            "device": self.device,
            "language": self.language,
        }

    def build_protocol(self) -> PipelineProtocol:
        protocol = PipelineProtocol(
            version=PIPELINE_PROTOCOL_VERSION,
            stage_order=PIPELINE_STAGE_ORDER,
            command_environment=PIPELINE_COMMAND_ENVIRONMENT,
            stages={
                "separation": StageContract(
                    name="separation",
                    purpose="Split input audio into vocals and instrumental stems.",
                    command=self.separation_command,
                    inputs=("input_audio", "user_lyrics", "lyric_source", "config", "protocol_version"),
                    outputs=("vocals", "instrumental"),
                    required_inputs=("input_audio",),
                    required_outputs=("vocals", "instrumental"),
                    command_placeholders=("input_audio", "vocals", "instrumental", "request_json", "stage_dir", "run_dir"),
                ),
                "asr": StageContract(
                    name="asr",
                    purpose="Transcribe the vocal stem when the user did not provide lyrics.",
                    command=self.asr_command,
                    inputs=(
                        "input_audio",
                        "user_lyrics",
                        "lyric_source",
                        "config",
                        "protocol_version",
                        "language",
                        "role",
                        "source_audio",
                        "vocals_audio",
                        "instrumental_audio",
                        "asr_backend_command",
                    ),
                    outputs=("transcript_json", "transcript_txt"),
                    required_inputs=("source_audio", "vocals_audio"),
                    required_outputs=("transcript_json", "transcript_txt"),
                    command_placeholders=("source_audio", "transcript_json", "transcript_txt", "language", "request_json", "stage_dir", "asr_backend_command"),
                ),
                "lyric_rewrite": StageContract(
                    name="lyric_rewrite",
                    purpose="Rewrite the source lyrics into Feibi-style syllable-preserving lyrics.",
                    command=self.llm_command,
                    inputs=(
                        "input_audio",
                        "user_lyrics",
                        "lyric_source",
                        "config",
                        "protocol_version",
                        "rewrite_source_lines",
                        "asr_transcript_lines",
                        "source_audio",
                        "vocals_audio",
                        "instrumental_audio",
                        "llm_backend_command",
                    ),
                    outputs=("rewritten_lyrics", "rewrite_json"),
                    required_inputs=("rewrite_source_lines",),
                    required_outputs=("rewritten_lyrics", "rewrite_json"),
                    command_placeholders=("rewritten_lyrics", "rewrite_json", "stage_request_json", "request_json", "stage_dir", "llm_backend_command"),
                ),
                "ace_step_lyric_edit": StageContract(
                    name="ace_step_lyric_edit",
                    purpose="Generate a new song in ACE-Step 1.5 lyric-edit mode.",
                    command=self.ace_step_command,
                    inputs=(
                        "input_audio",
                        "user_lyrics",
                        "lyric_source",
                        "config",
                        "protocol_version",
                        "rewrite_source_lines",
                        "rewritten_lines",
                        "validation",
                        "mode",
                        "source_audio",
                        "vocals_audio",
                        "rewritten_lyrics_path",
                        "ace_step_backend_command",
                    ),
                    outputs=("generated_song",),
                    required_inputs=("rewritten_lines", "source_audio", "rewritten_lyrics_path"),
                    required_outputs=("generated_song",),
                    command_placeholders=("source_audio", "rewritten_lyrics_path", "generated_song", "mode", "validation", "request_json", "stage_dir", "ace_step_backend_command"),
                ),
                "rvc_voice_conversion": StageContract(
                    name="rvc_voice_conversion",
                    purpose="Convert the generated singing voice into Feibi timbre with the provided RVC model.",
                    command=self.rvc_command,
                    inputs=(
                        "input_audio",
                        "user_lyrics",
                        "lyric_source",
                        "config",
                        "protocol_version",
                        "rewrite_source_lines",
                        "rewritten_lines",
                        "rvc_model",
                        "rvc_index",
                        "source_song",
                        "generated_song",
                        "rvc_backend_command",
                    ),
                    outputs=("final_song",),
                    required_inputs=("source_song", "rvc_model", "rvc_index"),
                    required_outputs=("final_song",),
                    command_placeholders=("source_song", "rvc_model", "rvc_index", "final_song", "request_json", "stage_dir", "rvc_backend_command"),
                ),
            },
        )
        issues = protocol.validate()
        if issues:
            raise ValueError("; ".join(issues))
        return protocol

    def validate(
        self,
        *,
        require_commands: bool = False,
        require_rvc: bool = False,
        require_asr: bool = False,
    ) -> None:
        issues: list[str] = []
        if require_commands:
            for field_name in (
                "separation_command",
                "llm_command",
                "llm_backend_command",
                "asr_engine_command",
                "ace_step_command",
                "ace_step_backend_command",
                "ace_step_engine_command",
                "rvc_command",
                "rvc_backend_command",
                "rvc_engine_command",
            ):
                if not getattr(self, field_name).strip():
                    issues.append(f"{field_name} is required for real execution")
        if require_asr:
            if not self.asr_command.strip():
                issues.append("asr_command is required when ASR fallback is enabled")
            if not self.asr_backend_command.strip():
                issues.append("asr_backend_command is required when ASR fallback is enabled")
            if not self.asr_engine_command.strip():
                issues.append("asr_engine_command is required when ASR fallback is enabled")
        if require_rvc:
            if not self.rvc_model.strip():
                issues.append("rvc_model is required for real execution")
            if not self.rvc_index.strip():
                issues.append("rvc_index is required for real execution")
        if issues:
            raise ValueError("; ".join(issues))

    def ensure_rvc_paths_exist(self) -> None:
        missing = []
        if self.rvc_model and not Path(self.rvc_model).exists():
            missing.append(f"rvc_model not found: {self.rvc_model}")
        if self.rvc_index and not Path(self.rvc_index).exists():
            missing.append(f"rvc_index not found: {self.rvc_index}")
        if missing:
            raise FileNotFoundError("; ".join(missing))


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
