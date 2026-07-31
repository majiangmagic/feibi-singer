from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .adapters import ExternalAdapter
from .feibi_rules import rewrite_lyrics, validate_line
from .models import PipelineConfig, PipelineProtocol, PipelineReport, StageResult


class FeibiPipeline:
    def __init__(self, config: PipelineConfig | None = None, dry_run: bool = True):
        self.config = config or PipelineConfig()
        self.dry_run = dry_run

    def _write_json(self, path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def _read_lines(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line]

    def _manifest(
        self,
        input_audio: Path,
        output_dir: Path,
        lyrics: list[str],
        lyric_source: str,
        asr_enabled: bool,
        protocol: PipelineProtocol,
    ) -> dict:
        return {
            "input_audio": str(input_audio),
            "output_dir": str(output_dir),
            "lyric_source": lyric_source,
            "lyrics_provided": bool(lyrics),
            "lyrics_line_count": len(lyrics),
            "asr_enabled": asr_enabled,
            "protocol_version": protocol.version,
            "config": self.config.as_dict(),
            "dry_run": self.dry_run,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _source_mode(self, lyrics: list[str], use_asr_fallback: bool) -> str:
        if lyrics:
            return "user_provided"
        return "asr_fallback" if use_asr_fallback else "empty"

    def _build_validation(self, source_lines: list[str], rewritten_lines: list[str]) -> dict:
        checks = [validate_line(source, rewritten) for source, rewritten in zip(source_lines, rewritten_lines)]
        return {
            "all_passed": bool(source_lines) and len(source_lines) == len(rewritten_lines) and all(check.accepted for check in checks),
            "line_count": len(checks),
            "lines": [check.as_dict() for check in checks],
        }

    def _read_transcript_lines(self, output_dir: Path) -> list[str]:
        transcript_txt = output_dir / "stages" / "asr" / "transcript.txt"
        if transcript_txt.exists():
            return self._read_lines(transcript_txt)
        transcript_json = output_dir / "stages" / "asr" / "transcript.json"
        if not transcript_json.exists():
            return []
        payload = self._read_json(transcript_json)
        for key in ("lines", "transcript_lines"):
            value = payload.get(key)
            if isinstance(value, list):
                return [str(item) for item in value if str(item)]
        transcript = payload.get("transcript")
        if isinstance(transcript, str):
            return [line for line in transcript.splitlines() if line]
        return []

    def _read_rewritten_lines(self, output_dir: Path) -> list[str]:
        rewritten_txt = output_dir / "rewritten_lyrics.txt"
        if rewritten_txt.exists():
            return self._read_lines(rewritten_txt)
        rewritten_json = output_dir / "rewritten_lyrics.json"
        if not rewritten_json.exists():
            return []
        payload = self._read_json(rewritten_json)
        value = payload.get("rewritten_lines")
        if isinstance(value, list):
            return [str(item) for item in value if str(item)]
        return []

    def _require_stage_ok(self, stage: StageResult, *, required: bool, stage_name: str) -> None:
        if stage.status in {"planned", "skipped", "completed"}:
            return
        if required:
            raise RuntimeError(f"stage {stage_name} failed: {stage.details}")

    def run(
        self,
        input_audio: Path,
        output_dir: Path,
        lyrics: list[str] | None = None,
        *,
        use_asr_fallback: bool = True,
    ) -> PipelineReport:
        user_lyrics = list(lyrics or [])
        protocol = self.config.build_protocol()
        require_asr = not user_lyrics and use_asr_fallback
        if not self.dry_run:
            self.config.validate(require_commands=True, require_rvc=True, require_asr=require_asr)
            self.config.ensure_rvc_paths_exist()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(output_dir / "protocol.json", protocol.as_dict())
        lyric_source = self._source_mode(user_lyrics, use_asr_fallback)
        manifest = self._manifest(input_audio, output_dir, user_lyrics, lyric_source, use_asr_fallback, protocol)
        self._write_json(output_dir / "input_manifest.json", manifest)

        adapter = ExternalAdapter(self.config, self.dry_run)
        protocol_data = protocol.as_dict()
        stages: list[StageResult] = []
        stage_inputs = {
            "input_audio": str(input_audio),
            "user_lyrics": user_lyrics,
            "lyric_source": lyric_source,
            "config": self.config.as_dict(),
            "protocol_version": protocol.version,
        }

        separation_outputs = {
            "vocals": str(output_dir / "stages" / "separation" / "vocals.wav"),
            "instrumental": str(output_dir / "stages" / "separation" / "instrumental.wav"),
        }
        separation = adapter.run(
            "separation",
            self.config.separation_command,
            output_dir,
            stage_inputs,
            separation_outputs,
            protocol.stages["separation"],
            protocol_data,
        )
        stages.append(separation)
        self._require_stage_ok(separation, required=not self.dry_run, stage_name="separation")
        vocals_audio = separation_outputs["vocals"]
        instrumental_audio = separation_outputs["instrumental"]

        asr_stage: StageResult | None = None
        asr_transcript_lines: list[str] = []
        if user_lyrics:
            asr_artifact = output_dir / "stages" / "asr" / "stage.json"
            self._write_json(asr_artifact, {"stage": "asr", "skipped": True, "reason": "user_lyrics_provided"})
            stages.append(StageResult("asr", "skipped", asr_artifact, {"reason": "user_lyrics_provided"}))
        elif use_asr_fallback:
            asr_stage = adapter.run(
                "asr",
                self.config.asr_command,
                output_dir,
                {
                    **stage_inputs,
                    "language": self.config.language,
                    "role": "primary",
                    "source_audio": vocals_audio,
                    "vocals_audio": vocals_audio,
                    "instrumental_audio": instrumental_audio,
                    "asr_backend_command": self.config.asr_backend_command,
                    "asr_engine_command": self.config.asr_engine_command,
                },
                {
                    "transcript_json": str(output_dir / "stages" / "asr" / "transcript.json"),
                    "transcript_txt": str(output_dir / "stages" / "asr" / "transcript.txt"),
                },
                protocol.stages["asr"],
                protocol_data,
            )
            stages.append(asr_stage)
            self._require_stage_ok(asr_stage, required=not self.dry_run, stage_name="asr")
            if asr_stage.status == "completed":
                asr_transcript_lines = self._read_transcript_lines(output_dir)
        else:
            asr_artifact = output_dir / "stages" / "asr" / "stage.json"
            self._write_json(asr_artifact, {"stage": "asr", "skipped": True, "reason": "fallback_disabled"})
            stages.append(StageResult("asr", "skipped", asr_artifact, {"reason": "fallback_disabled"}))

        rewrite_source_lines = user_lyrics or asr_transcript_lines
        if not rewrite_source_lines and not self.dry_run:
            raise RuntimeError("no lyrics available for lyric rewrite")

        rewrite_stage = adapter.run(
            "lyric_rewrite",
            self.config.llm_command,
            output_dir,
            {
                **stage_inputs,
                "rewrite_source_lines": rewrite_source_lines,
                "asr_transcript_lines": asr_transcript_lines,
                "source_audio": vocals_audio if asr_transcript_lines else str(input_audio),
                "vocals_audio": vocals_audio,
                "instrumental_audio": instrumental_audio,
                "llm_backend_command": self.config.llm_backend_command,
            },
            {
                "rewritten_lyrics": str(output_dir / "rewritten_lyrics.txt"),
                "rewrite_json": str(output_dir / "rewritten_lyrics.json"),
            },
            protocol.stages["lyric_rewrite"],
            protocol_data,
        )
        stages.append(rewrite_stage)
        self._require_stage_ok(rewrite_stage, required=not self.dry_run, stage_name="lyric_rewrite")

        if self.dry_run:
            rewritten_lines, checks = rewrite_lyrics(rewrite_source_lines)
            validation = {
                "all_passed": all(check.accepted for check in checks),
                "line_count": len(checks),
                "lines": [check.as_dict() for check in checks],
            }
            self._write_json(
                output_dir / "rewritten_lyrics.json",
                {
                    "lyric_source": lyric_source,
                    "source_lines": rewrite_source_lines,
                    "rewritten_lines": rewritten_lines,
                    "validation": validation,
                },
            )
            (output_dir / "rewritten_lyrics.txt").write_text("\n".join(rewritten_lines) + ("\n" if rewritten_lines else ""), encoding="utf-8")
        else:
            rewritten_lines = self._read_rewritten_lines(output_dir)
            if not rewritten_lines:
                raise RuntimeError("lyric rewrite stage did not produce rewritten lyrics")
            validation = self._build_validation(rewrite_source_lines, rewritten_lines)
            self._write_json(
                output_dir / "rewritten_lyrics.json",
                {
                    "lyric_source": lyric_source,
                    "source_lines": rewrite_source_lines,
                    "rewritten_lines": rewritten_lines,
                    "validation": validation,
                },
            )
            (output_dir / "rewritten_lyrics.txt").write_text("\n".join(rewritten_lines) + ("\n" if rewritten_lines else ""), encoding="utf-8")

        if self.dry_run:
            validation = self._build_validation(rewrite_source_lines, rewritten_lines)
        self._write_json(output_dir / "validation.json", validation)

        generated_song = str(output_dir / "stages" / "ace_step_lyric_edit" / "ace_step_output.wav")
        ace_stage = adapter.run(
            "ace_step_lyric_edit",
            self.config.ace_step_command,
            output_dir,
            {
                **stage_inputs,
                "rewrite_source_lines": rewrite_source_lines,
                "rewritten_lines": rewritten_lines,
                "validation": validation,
                "mode": "lyric_edit",
                "source_audio": instrumental_audio,
                "vocals_audio": vocals_audio,
                "rewritten_lyrics_path": str(output_dir / "rewritten_lyrics.txt"),
                "ace_step_backend_command": self.config.ace_step_backend_command,
                "ace_step_engine_command": self.config.ace_step_engine_command,
            },
            {"generated_song": generated_song},
            protocol.stages["ace_step_lyric_edit"],
            protocol_data,
        )
        stages.append(ace_stage)
        self._require_stage_ok(ace_stage, required=not self.dry_run, stage_name="ace_step_lyric_edit")

        rvc_stage = adapter.run(
            "rvc_voice_conversion",
            self.config.rvc_command,
            output_dir,
            {
                **stage_inputs,
                "rewrite_source_lines": rewrite_source_lines,
                "rewritten_lines": rewritten_lines,
                "rvc_model": self.config.rvc_model,
                "rvc_index": self.config.rvc_index,
                "source_song": generated_song,
                "generated_song": generated_song,
                "rvc_backend_command": self.config.rvc_backend_command,
                "rvc_engine_command": self.config.rvc_engine_command,
            },
            {"final_song": str(output_dir / "final_feibi_song.wav")},
            protocol.stages["rvc_voice_conversion"],
            protocol_data,
        )
        stages.append(rvc_stage)
        self._require_stage_ok(rvc_stage, required=not self.dry_run, stage_name="rvc_voice_conversion")

        outputs = {
            "input_manifest": str(output_dir / "input_manifest.json"),
            "protocol": str(output_dir / "protocol.json"),
            "rewritten_lyrics": str(output_dir / "rewritten_lyrics.txt"),
            "rewritten_lyrics_json": str(output_dir / "rewritten_lyrics.json"),
            "validation": str(output_dir / "validation.json"),
            "final_song": str(output_dir / "final_feibi_song.wav"),
            "stage_root": str(output_dir / "stages"),
        }
        report = PipelineReport(
            output_dir,
            self.dry_run,
            stages,
            manifest,
            rewrite_source_lines,
            rewritten_lines,
            validation,
            outputs,
        )
        self._write_json(output_dir / "report.json", report.as_dict())
        return report
