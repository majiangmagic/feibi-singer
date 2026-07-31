from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .adapters import ExternalAdapter
from .feibi_rules import rewrite_lyrics
from .models import PipelineConfig, PipelineReport, StageResult


class FeibiPipeline:
    def __init__(self, config: PipelineConfig | None = None, dry_run: bool = True):
        self.config = config or PipelineConfig()
        self.dry_run = dry_run

    def _write_json(self, path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def _manifest(self, input_audio: Path, output_dir: Path, lyrics: list[str]) -> dict:
        return {
            "input_audio": str(input_audio),
            "output_dir": str(output_dir),
            "lyrics_provided": bool(lyrics),
            "lyrics_line_count": len(lyrics),
            "config": self.config.as_dict(),
            "dry_run": self.dry_run,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def run(self, input_audio: Path, output_dir: Path, lyrics: list[str] | None = None) -> PipelineReport:
        output_dir.mkdir(parents=True, exist_ok=True)
        source_lines = list(lyrics or [])
        manifest = self._manifest(input_audio, output_dir, source_lines)
        self._write_json(output_dir / "input_manifest.json", manifest)

        rewritten_lines, checks = rewrite_lyrics(source_lines)
        validation = {
            "all_passed": all(check.accepted for check in checks),
            "line_count": len(checks),
            "lines": [check.as_dict() for check in checks],
        }
        self._write_json(
            output_dir / "rewritten_lyrics.json",
            {
                "source_lines": source_lines,
                "rewritten_lines": rewritten_lines,
                "validation": validation,
            },
        )
        (output_dir / "rewritten_lyrics.txt").write_text("\n".join(rewritten_lines) + ("\n" if rewritten_lines else ""), encoding="utf-8")
        self._write_json(output_dir / "validation.json", validation)

        adapter = ExternalAdapter(self.config, self.dry_run)
        stage_inputs = {
            "input_audio": str(input_audio),
            "lyrics_source": source_lines,
            "lyrics_rewritten": rewritten_lines,
            "config": self.config.as_dict(),
        }
        stages: list[StageResult] = []
        stages.append(
            adapter.run(
                "separation",
                self.config.separation_command,
                output_dir,
                stage_inputs,
                {"vocals": str(output_dir / "stages" / "separation" / "vocals.wav"), "instrumental": str(output_dir / "stages" / "separation" / "instrumental.wav")},
            )
        )
        stages.append(
            adapter.run(
                "asr",
                self.config.asr_command,
                output_dir,
                {**stage_inputs, "language": self.config.language},
                {"transcript_json": str(output_dir / "stages" / "asr" / "transcript.json"), "transcript_txt": str(output_dir / "stages" / "asr" / "transcript.txt")},
            )
        )
        stages.append(
            adapter.run(
                "lyric_rewrite",
                self.config.llm_command,
                output_dir,
                {**stage_inputs, "validation": validation},
                {"rewritten_lyrics": str(output_dir / "rewritten_lyrics.txt"), "rewrite_json": str(output_dir / "rewritten_lyrics.json")},
            )
        )
        stages.append(
            adapter.run(
                "ace_step_lyric_edit",
                self.config.ace_step_command,
                output_dir,
                {**stage_inputs, "mode": "lyric_edit"},
                {"generated_song": str(output_dir / "stages" / "ace_step_lyric_edit" / "ace_step_output.wav")},
            )
        )
        stages.append(
            adapter.run(
                "rvc_voice_conversion",
                self.config.rvc_command,
                output_dir,
                {**stage_inputs, "rvc_model": self.config.rvc_model},
                {"final_song": str(output_dir / "final_feibi_song.wav")},
            )
        )

        outputs = {
            "input_manifest": str(output_dir / "input_manifest.json"),
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
            source_lines,
            rewritten_lines,
            validation,
            outputs,
        )
        self._write_json(output_dir / "report.json", report.as_dict())
        return report
