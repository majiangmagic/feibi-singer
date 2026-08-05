from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .timeline_pipeline import (
    ACE_CAPTION,
    STITCH_HANDLE_SECONDS,
    calculate_vocal_gain_db,
    measure_integrated_lufs,
    resolve_caption,
)

STATE_VERSION = 1


class WorkbenchError(RuntimeError):
    """Raised when the interactive segment workflow cannot continue."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(command: list[str], **kwargs: Any) -> None:
    subprocess.run(command, check=True, **kwargs)


def _run_logged(command: list[str], log_path: Path, timeout: float, **kwargs: Any) -> None:
    """Run a generation subprocess with durable logs and a bounded runtime."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = kwargs.pop("env", None)
    cwd = kwargs.pop("cwd", None)
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            log.write("$ " + subprocess.list2cmdline(command) + "\n")
            log.flush()
            subprocess.run(command, check=True, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise WorkbenchError(f"?????{timeout / 60:.1f} ?????????{log_path}") from exc
    except subprocess.CalledProcessError as exc:
        raise WorkbenchError(f"???????? {exc.returncode}???????{log_path}") from exc


class SegmentWorkbench:
    """Persisted editor for ACE/RVC segment candidates from a timeline run."""

    def __init__(self, run_dir: Path, workbench_dir: Path | None = None) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.report_path = self.run_dir / "report.json"
        if not self.report_path.exists():
            raise FileNotFoundError(self.report_path)
        self.report = json.loads(self.report_path.read_text(encoding="utf-8-sig"))
        segments = self.report.get("segmentation", {}).get("segments", [])
        if not segments:
            raise WorkbenchError("run report does not contain segmented timeline data")

        self.repo_root = Path(__file__).resolve().parents[1]
        self.project_python = self.repo_root / ".venv" / "Scripts" / "python.exe"
        self.ace_python = self.repo_root / ".venv-acestep" / "Scripts" / "python.exe"
        self.rvc_python = self.repo_root / ".venv-rvc" / "Scripts" / "python.exe"
        self.workbench_dir = (Path(workbench_dir) if workbench_dir else self.run_dir / "workbench").resolve()
        self.workbench_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.workbench_dir / "workbench.json"
        self.state = self._load_or_initialize(segments)

    def _load_or_initialize(self, segments: list[dict[str, Any]]) -> dict[str, Any]:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text(encoding="utf-8-sig"))
            if state.get("version") != STATE_VERSION:
                raise WorkbenchError(f"unsupported workbench state version: {state.get('version')}")
            if Path(state.get("source_run", "")).resolve() != self.run_dir:
                raise WorkbenchError("workbench belongs to a different source run")
            changed = False
            for key, state_segment in state.get("segments", {}).items():
                original_path = (
                    self.run_dir / "stages" / "segmented_voice_conversion"
                    / f"segment_{int(key):02d}" / "original_lyrics.txt"
                )
                if "default_original_lyrics" not in state_segment:
                    state_segment["default_original_lyrics"] = (
                        original_path.read_text(encoding="utf-8-sig").strip()
                        if original_path.exists() else ""
                    )
                    state_segment["flow_edit_available"] = original_path.exists()
                    changed = True
                if "default_source_caption" not in state_segment:
                    state_segment["default_source_caption"] = self.report.get("ace_source_caption") or state_segment["default_caption"]
                    changed = True
                if state_segment.get("approved") is None:
                    default_approval = self._default_approval(state_segment)
                    if default_approval is not None:
                        state_segment["approved"] = default_approval
                        changed = True
            if changed:
                self._save_state(state)
            return state

        state: dict[str, Any] = {
            "version": STATE_VERSION,
            "source_run": str(self.run_dir),
            "created_at": _now(),
            "updated_at": _now(),
            "segments": {},
            "final_outputs": [],
        }
        default_caption = self.report.get("ace_caption") or ACE_CAPTION
        for item in segments:
            index = int(item["index"])
            segment_dir = self.run_dir / "stages" / "segmented_voice_conversion" / f"segment_{index:02d}"
            source_audio = segment_dir / "source.wav"
            lyrics_path = segment_dir / "lyrics.txt"
            original_lyrics_path = segment_dir / "original_lyrics.txt"
            if not source_audio.exists() or not lyrics_path.exists():
                raise FileNotFoundError(source_audio if not source_audio.exists() else lyrics_path)
            selected_seed = item.get("selected_seed")
            rvc_f0 = item.get("rvc_f0_change", 2)
            state_segment = {
                "index": index,
                "core_start": item["core_start"],
                "core_end": item["core_end"],
                "input_start": item["input_start"],
                "input_end": item["input_end"],
                "source_audio": str(source_audio),
                "default_seed": selected_seed if selected_seed is not None else 44,
                "default_caption": default_caption,
                "default_source_caption": self.report.get("ace_source_caption") or default_caption,
                "default_lyrics": lyrics_path.read_text(encoding="utf-8-sig").strip(),
                "default_original_lyrics": (
                    original_lyrics_path.read_text(encoding="utf-8-sig").strip()
                    if original_lyrics_path.exists() else ""
                ),
                "flow_edit_available": original_lyrics_path.exists(),
                "default_f0_change": int(rvc_f0),
                "candidates": [],
                "approved": None,
            }
            self._add_existing_candidate(state_segment, segment_dir, selected_seed, int(rvc_f0))
            state_segment["approved"] = self._default_approval(state_segment)
            state["segments"][str(index)] = state_segment
        self._save_state(state)
        return state

    def _add_existing_candidate(
        self,
        segment: dict[str, Any],
        segment_dir: Path,
        selected_seed: int | None,
        f0_change: int,
    ) -> None:
        if selected_seed is None:
            return
        candidate_dir = segment_dir / "candidates" / f"seed_{selected_seed}"
        ace_audio = candidate_dir / "ace_step_output.wav"
        ace_vocals = next((candidate_dir / "demucs").rglob("vocals.wav"), None)
        rvc_audio = segment_dir / "converted_vocals.wav"
        if not ace_audio.exists() or ace_vocals is None:
            return
        candidate_id = f"source-seed-{selected_seed}"
        candidate: dict[str, Any] = {
            "id": candidate_id,
            "created_at": _now(),
            "source": "source_run",
            "seed": selected_seed,
            "caption": segment["default_caption"],
            "lyrics": segment["default_lyrics"],
            "ace_audio": str(ace_audio),
            "ace_vocals": str(ace_vocals),
            "rvc_results": [],
        }
        if rvc_audio.exists():
            candidate["rvc_results"].append(
                {
                    "id": f"source-f0-{f0_change:+d}",
                    "created_at": _now(),
                    "f0_change": f0_change,
                    "audio": str(rvc_audio),
                    "source": "source_run",
                }
            )
        segment["candidates"].append(candidate)

    @staticmethod
    def _default_approval(segment: dict[str, Any]) -> dict[str, Any] | None:
        """Return the original pipeline result as the initial selection.

        A fresh workbench should be merge-ready for unchanged segments: the
        first pipeline ACE/RVC result is the default until the user explicitly
        chooses another candidate.  Later ACE candidates are never selected
        implicitly.
        """
        candidates = segment.get("candidates") or []
        if not candidates:
            return None
        candidate = candidates[0]
        results = candidate.get("rvc_results") or []
        if not results:
            return None
        result = results[0]
        return {
            "candidate_id": candidate["id"],
            "rvc_id": result["id"],
            "seed": candidate["seed"],
            "caption": candidate["caption"],
            "lyrics": candidate["lyrics"],
            "f0_change": result["f0_change"],
            "audio": result["audio"],
            "approved_at": _now(),
            "selection_source": "default_initial_pipeline_result",
        }

    def _save_state(self, state: dict[str, Any] | None = None) -> None:
        if state is not None:
            self.state = state
        self.state["updated_at"] = _now()
        self.state_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @property
    def segment_indices(self) -> list[int]:
        return sorted(int(index) for index in self.state["segments"])

    def segment(self, index: int) -> dict[str, Any]:
        try:
            return self.state["segments"][str(int(index))]
        except KeyError as exc:
            raise WorkbenchError(f"unknown segment: {index}") from exc

    def candidate(self, index: int, candidate_id: str) -> dict[str, Any]:
        for candidate in self.segment(index)["candidates"]:
            if candidate["id"] == candidate_id:
                return candidate
        raise WorkbenchError(f"unknown ACE candidate for segment {index}: {candidate_id}")

    def rvc_result(self, index: int, candidate_id: str, rvc_id: str) -> dict[str, Any]:
        candidate = self.candidate(index, candidate_id)
        for result in candidate["rvc_results"]:
            if result["id"] == rvc_id:
                return result
        raise WorkbenchError(f"unknown RVC result for segment {index}: {rvc_id}")

    @staticmethod
    def _validate_preview_vocal_gain(voice_gain_db: float) -> float:
        gain = float(voice_gain_db)
        if not -6.0 <= gain <= 12.0:
            raise WorkbenchError("preview vocal gain must be between -6 and +12 dB")
        return gain

    def _preview_paths(
        self,
        index: int,
        candidate_id: str,
        rvc_id: str | None = None,
        voice_gain_db: float = 0.0,
    ) -> tuple[Path, Path]:
        gain = self._validate_preview_vocal_gain(voice_gain_db)
        base = self.workbench_dir / f"segment_{int(index):02d}" / "previews" / candidate_id
        gain_suffix = "" if gain == 0.0 else f"_voice_{gain:+.1f}dB".replace("+", "p").replace("-", "m")
        if rvc_id is None:
            return base / f"ace_with_original_melody{gain_suffix}.wav", base / "ace_generated_melody.wav"
        return base / f"{rvc_id}_with_original_melody{gain_suffix}.wav", base / f"{rvc_id}_vocal_only.wav"

    def _original_instrumental_preview(self, index: int, output: Path) -> Path:
        segment = self.segment(index)
        instrumental = Path(self.report["outputs"]["original_instrumental"])
        duration = float(segment["input_end"]) - float(segment["input_start"])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            return output
        _run([
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(max(0.0, float(segment["input_start"]))),
            "-t", str(duration), "-i", str(instrumental),
            "-af", f"apad,atrim=duration={duration}",
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(output),
        ])
        return output

    def _mix_preview(self, backing: Path, voice: Path, output: Path, voice_gain_db: float = 0.0) -> Path:
        gain = self._validate_preview_vocal_gain(voice_gain_db)
        output.parent.mkdir(parents=True, exist_ok=True)
        _run([
            "ffmpeg", "-y", "-v", "error", "-i", str(backing), "-i", str(voice),
            "-filter_complex",
            "[0:a]aresample=48000,volume=0.85[inst];"
            f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,volume={gain:+.1f}dB[voc];"
            "[inst][voc]amix=inputs=2:duration=first:normalize=0,volume=0.9,alimiter=limit=0.8913:level=false[out]",
            "-map", "[out]", "-c:a", "pcm_s24le", str(output),
        ])
        return output

    def ace_preview(self, index: int, candidate_id: str, voice_gain_db: float = 0.0) -> dict[str, str]:
        candidate = self.candidate(index, candidate_id)
        with_original, generated = self._preview_paths(index, candidate_id, voice_gain_db=voice_gain_db)
        generated.parent.mkdir(parents=True, exist_ok=True)
        if not generated.exists():
            shutil.copyfile(candidate["ace_audio"], generated)
        backing = self._original_instrumental_preview(
            index, with_original.parent / "original_instrumental.wav"
        )
        self._mix_preview(Path(backing), Path(candidate["ace_vocals"]), with_original, voice_gain_db)
        return {"with_original": str(with_original), "generated_melody": str(generated)}

    def rvc_preview(
        self, index: int, candidate_id: str, rvc_id: str, voice_gain_db: float = 0.0
    ) -> dict[str, str]:
        result = self.rvc_result(index, candidate_id, rvc_id)
        with_original, vocal_only = self._preview_paths(
            index, candidate_id, rvc_id, voice_gain_db=voice_gain_db
        )
        backing = self._original_instrumental_preview(
            index, with_original.parent / "original_instrumental.wav"
        )
        self._mix_preview(Path(backing), Path(result["audio"]), with_original, voice_gain_db)
        vocal_only.parent.mkdir(parents=True, exist_ok=True)
        if not vocal_only.exists():
            shutil.copyfile(result["audio"], vocal_only)
        return {"with_original": str(with_original), "vocal_only": str(vocal_only)}

    def candidate_choices(self, index: int) -> list[tuple[str, str]]:
        return [
            (f"{candidate['id']} | seed {candidate['seed']}", candidate["id"])
            for candidate in reversed(self.segment(index)["candidates"])
        ]

    def rvc_choices(self, index: int, candidate_id: str) -> list[tuple[str, str]]:
        candidate = self.candidate(index, candidate_id)
        return [
            (f"{result['id']} | pitch {result['f0_change']:+d}", result["id"])
            for result in reversed(candidate["rvc_results"])
        ]

    def ace_command(self, index: int, seed: int, caption: str, lyrics_path: Path, output: Path) -> list[str]:
        segment = self.segment(index)
        duration = float(segment["input_end"]) - float(segment["input_start"])
        command = [
            str(self.ace_python),
            str(self.repo_root / "scripts" / "feibi_ace_step_v15.py"),
            "--source-audio", str(Path(segment["source_audio"])),
            "--lyrics", str(lyrics_path),
            "--output", str(output),
            "--runtime-root", str(self.repo_root / "models" / "ace_step" / "runtime"),
            "--checkpoints-dir", str(self.repo_root / "models" / "ace_step" / "checkpoints"),
            "--caption", resolve_caption(caption),
            "--duration", str(duration),
            "--cover-strength", "1.0",
        ]
        original_lyrics = segment.get("default_original_lyrics", "").strip()
        if segment.get("flow_edit_available") and original_lyrics:
            # Keep the target and source musical caption identical.  Flow-edit
            # then computes the meaningful delta from lyrics only, while the
            # source audio remains the primary melody/rhythm anchor.
            source_caption = resolve_caption(caption)
            command.extend([
                "--flow-edit",
                "--flow-edit-source-lyrics", original_lyrics,
                "--flow-edit-source-caption", source_caption,
            ])
        command.extend(["--seed", str(int(seed))])
        return command

    def rvc_command(self, source: Path, f0_change: int, output: Path) -> list[str]:
        assets = self.repo_root / "models" / "rvc" / "assets"
        return [
            str(self.rvc_python),
            str(self.repo_root / "scripts" / "feibi_rvc_infer.py"),
            "--source-song", str(source),
            "--model", str(self.repo_root / "models" / "rvc" / "feibiv1.0.0_e200_s1600.pth"),
            "--index", str(self.repo_root / "models" / "rvc" / "feibiv1.0.0_v2.index"),
            "--runtime-root", str(self.repo_root / "models" / "rvc" / "runtime"),
            "--hubert-model", str(assets / "hubert_base.pt"),
            "--rmvpe-model", str(assets / "rmvpe.pt"),
            "--f0-change", str(int(f0_change)),
            "--output", str(output),
        ]

    def _environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "TORCH_HOME": str(self.repo_root / "models" / "demucs"),
                "HF_HOME": str(self.repo_root / "models" / "huggingface"),
                "HF_HUB_OFFLINE": "1",
                "MODELSCOPE_CACHE": str(self.repo_root / "models" / "modelscope"),
            }
        )
        return env

    def generate_ace(self, index: int, seed: int, caption: str, lyrics: str) -> dict[str, Any]:
        lyrics = lyrics.strip()
        if not lyrics:
            raise WorkbenchError("ACE preset lyrics cannot be blank")
        seed = int(seed)
        candidate_id = f"ace-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{seed}-{uuid.uuid4().hex[:6]}"
        candidate_dir = self.workbench_dir / f"segment_{index:02d}" / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=False)
        lyrics_path = candidate_dir / "lyrics.txt"
        lyrics_path.write_text(lyrics + "\n", encoding="utf-8")
        ace_audio = candidate_dir / "ace_step_output.wav"
        env = self._environment()
        env["ACESTEP_CHECKPOINTS_DIR"] = str(self.repo_root / "models" / "ace_step" / "checkpoints")
        try:
            _run_logged(
                self.ace_command(index, seed, caption, lyrics_path, ace_audio),
                candidate_dir / "ace_step.log",
                timeout=15 * 60,
                cwd=self.repo_root,
                env=env,
            )
            demucs_dir = candidate_dir / "demucs"
            _run_logged(
                [
                    str(self.rvc_python), "-m", "demucs.separate", "--two-stems", "vocals",
                    "-n", "htdemucs", "-d", "cuda", "-o", str(demucs_dir), "--", str(ace_audio),
                ],
                candidate_dir / "demucs.log",
                timeout=10 * 60,
                cwd=self.repo_root,
                env=env,
            )
        except Exception:
            (candidate_dir / "failed.txt").write_text(
                "ACE/RVC candidate generation failed; inspect ace_step.log or demucs.log.\n",
                encoding="utf-8",
            )
            raise
        ace_vocals = next(demucs_dir.rglob("vocals.wav"), None)
        if ace_vocals is None:
            raise WorkbenchError("Demucs did not produce ACE vocals")
        candidate = {
            "id": candidate_id,
            "created_at": _now(),
            "source": "workbench",
            "seed": seed,
            "caption": resolve_caption(caption),
            "lyrics": lyrics,
            "ace_audio": str(ace_audio),
            "ace_vocals": str(ace_vocals),
            "rvc_results": [],
        }
        self.segment(index)["candidates"].append(candidate)
        self._save_state()
        return candidate

    def generate_rvc(self, index: int, candidate_id: str, f0_change: int) -> dict[str, Any]:
        f0_change = int(f0_change)
        if not -24 <= f0_change <= 24:
            raise WorkbenchError("RVC pitch must be between -24 and +24 semitones")
        candidate = self.candidate(index, candidate_id)
        rvc_id = f"rvc-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{f0_change:+d}-{uuid.uuid4().hex[:6]}"
        output_dir = self.workbench_dir / f"segment_{index:02d}" / candidate_id / rvc_id
        output_dir.mkdir(parents=True, exist_ok=False)
        output = output_dir / "converted_vocals.wav"
        env = self._environment()
        env.update(
            {
                "HOME": str(self.repo_root / "models" / "rvc" / "home"),
                "USERPROFILE": str(self.repo_root / "models" / "rvc" / "home"),
            }
        )
        _run(self.rvc_command(Path(candidate["ace_vocals"]), f0_change, output), cwd=self.repo_root, env=env)
        result = {
            "id": rvc_id,
            "created_at": _now(),
            "f0_change": f0_change,
            "audio": str(output),
            "source": "workbench",
        }
        candidate["rvc_results"].append(result)
        self._save_state()
        return result

    def approve(self, index: int, candidate_id: str, rvc_id: str) -> dict[str, Any]:
        candidate = self.candidate(index, candidate_id)
        result = self.rvc_result(index, candidate_id, rvc_id)
        approved = {
            "candidate_id": candidate_id,
            "rvc_id": rvc_id,
            "seed": candidate["seed"],
            "caption": candidate["caption"],
            "lyrics": candidate["lyrics"],
            "f0_change": result["f0_change"],
            "audio": result["audio"],
            "approved_at": _now(),
        }
        self.segment(index)["approved"] = approved
        self._save_state()
        return approved

    def approval_summary(self) -> str:
        lines = []
        for index in self.segment_indices:
            approved = self.segment(index).get("approved")
            if approved:
                lines.append(
                    f"Segment {index}: seed {approved['seed']}, pitch {approved['f0_change']:+d}, {approved['candidate_id']}"
                )
            else:
                lines.append(f"Segment {index}: not approved")
        return "\n".join(lines)

    def merge_approved(self, output_name: str = "final_feibi_song") -> dict[str, Any]:
        missing = [index for index in self.segment_indices if not self.segment(index).get("approved")]
        if missing:
            raise WorkbenchError(f"approve every segment before merging; missing: {missing}")
        final_dir = self.workbench_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        normalized: list[Path] = []
        for position, index in enumerate(self.segment_indices):
            segment = self.segment(index)
            source = Path(segment["approved"]["audio"])
            if not source.exists():
                raise FileNotFoundError(source)
            keep_start = float(segment["core_start"]) - float(segment["input_start"])
            if position > 0:
                keep_start -= STITCH_HANDLE_SECONDS
            keep_end = float(segment["core_end"]) - float(segment["input_start"])
            if position < len(self.segment_indices) - 1:
                keep_end += STITCH_HANDLE_SECONDS
            target = final_dir / f"segment_{index:02d}_normalized.wav"
            _run(
                [
                    "ffmpeg", "-y", "-v", "error", "-ss", str(keep_start),
                    "-t", str(keep_end - keep_start), "-i", str(source),
                    "-af", f"apad,atrim=duration={keep_end - keep_start}",
                    "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(target),
                ]
            )
            normalized.append(target)

        converted = final_dir / "converted_vocals.wav"
        inputs = [item for audio in normalized for item in ("-i", str(audio))]
        filters: list[str] = []
        previous = "[0:a]"
        for position in range(1, len(normalized)):
            output = f"[mix{position}]"
            filters.append(
                f"{previous}[{position}:a]acrossfade=d={STITCH_HANDLE_SECONDS * 2}:c1=tri:c2=tri{output}"
            )
            previous = output
        vocal_window = self.report["vocal_window"]
        vocal_duration = float(vocal_window["end"]) - float(vocal_window["start"])
        filters.append(f"{previous}apad,atrim=duration={vocal_duration}[out]")
        _run(
            [
                "ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
                "-map", "[out]", "-c:a", "pcm_s24le", str(converted),
            ]
        )

        instrumental = Path(self.report["outputs"]["original_instrumental"])
        separated_vocals = self.run_dir / "stages" / "separation" / "vocals.wav"
        if not instrumental.exists() or not separated_vocals.exists():
            raise FileNotFoundError(instrumental if not instrumental.exists() else separated_vocals)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(instrumental)],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(probe.stdout.strip())
        aligned = final_dir / "aligned_vocals.wav"
        delay_ms = round(float(vocal_window["start"]) * 1000)
        _run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(converted), "-filter_complex",
                f"[0:a]adelay={delay_ms}|{delay_ms},apad=whole_dur={duration},atrim=duration={duration}[out]",
                "-map", "[out]", "-c:a", "pcm_s24le", str(aligned),
            ]
        )
        original_lufs = measure_integrated_lufs(
            separated_vocals, float(vocal_window["start"]), vocal_duration
        )
        converted_lufs = measure_integrated_lufs(
            aligned, float(vocal_window["start"]), vocal_duration
        )
        gain_db = calculate_vocal_gain_db(original_lufs, converted_lufs)
        wav = final_dir / f"{output_name}.wav"
        mix_filter = (
            "[0:a]aresample=48000[inst];"
            f"[1:a]pan=stereo|c0=c0|c1=c0,volume={gain_db}dB[voc];"
            "[inst][voc]amix=inputs=2:duration=first:normalize=0,"
            "volume=0.85,alimiter=limit=0.8913:level=false[out]"
        )
        _run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(instrumental), "-i", str(aligned),
                "-filter_complex", mix_filter, "-map", "[out]", "-c:a", "pcm_s24le", str(wav),
            ]
        )
        mp3 = final_dir / f"{output_name}.mp3"
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "320k", str(mp3)])
        output = {
            "created_at": _now(),
            "wav": str(wav),
            "mp3": str(mp3),
            "vocal_gain_db": gain_db,
            "original_vocal_lufs": original_lufs,
            "converted_vocal_lufs": converted_lufs,
            "segments": [self.segment(index)["approved"] for index in self.segment_indices],
        }
        report_path = final_dir / f"{output_name}.json"
        report_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output["report"] = str(report_path)
        self.state["final_outputs"].append(output)
        self._save_state()
        return output
