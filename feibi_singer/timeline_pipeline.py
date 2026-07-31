from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .feibi_rules import rewrite_lyrics

def measure_integrated_lufs(audio: Path, start: float = 0.0, duration: float | None = None) -> float:
    command = ["ffmpeg", "-hide_banner", "-ss", str(start)]
    if duration is not None:
        command.extend(["-t", str(duration)])
    command.extend(["-i", str(audio), "-af", "ebur128=framelog=verbose", "-f", "null", "NUL"])
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    values = re.findall(r"\bI:\s+(-?\d+(?:\.\d+)?)\s+LUFS", result.stderr)
    if not values:
        raise RuntimeError(f"unable to measure integrated loudness: {audio}")
    return float(values[-1])


def calculate_vocal_gain_db(original_lufs: float, converted_lufs: float) -> float:
    return round(original_lufs - converted_lufs, 2)


def select_vocal_window(silencedetect_output: str, duration: float) -> tuple[float, float]:
    starts = [float(value) for value in re.findall(r"silence_start: ([0-9.]+)", silencedetect_output)]
    ends = [float(value) for value in re.findall(r"silence_end: ([0-9.]+)", silencedetect_output)]
    intervals = [(start, end) for start, end in zip(starts, ends) if end > start]
    leading = [end for start, end in intervals if end - start >= 2 and end <= duration * 0.35]
    trailing = [start for start, end in intervals if end - start >= 2 and end >= duration - 0.25]
    vocal_start = max(leading, default=0.0)
    vocal_end = min(trailing, default=duration)
    if vocal_end <= vocal_start:
        raise RuntimeError(f"invalid detected vocal window: {vocal_start}-{vocal_end}")
    return vocal_start, vocal_end


def run_timeline_pipeline(
    input_audio: Path,
    output_dir: Path,
    lyrics: list[str],
    *,
    use_asr_fallback: bool = True,
) -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    project_python = repo_root / ".venv" / "Scripts" / "python.exe"
    ace_python = repo_root / ".venv-acestep" / "Scripts" / "python.exe"
    rvc_python = repo_root / ".venv-rvc" / "Scripts" / "python.exe"
    for path in (project_python, ace_python, rvc_python, input_audio):
        if not path.exists():
            raise FileNotFoundError(path)

    output_dir.mkdir(parents=True, exist_ok=True)
    stages = output_dir / "stages"
    separation_dir = stages / "separation"
    demucs_dir = separation_dir / "demucs"
    env = os.environ.copy()
    env.update({
        "TORCH_HOME": str(repo_root / "models" / "demucs"),
        "HF_HOME": str(repo_root / "models" / "huggingface"),
        "MODELSCOPE_CACHE": str(repo_root / "models" / "modelscope"),
    })

    subprocess.run(
        [str(rvc_python), "-m", "demucs.separate", "--two-stems", "vocals", "-n", "htdemucs", "-d", "cuda", "-o", str(demucs_dir), "--", str(input_audio)],
        cwd=repo_root,
        env=env,
        check=True,
    )
    vocals = next(demucs_dir.rglob("vocals.wav"))
    instrumental = next(demucs_dir.rglob("no_vocals.wav"))
    separation_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(vocals, separation_dir / "vocals.wav")
    shutil.copyfile(instrumental, separation_dir / "instrumental.wav")
    vocals = separation_dir / "vocals.wav"
    instrumental = separation_dir / "instrumental.wav"

    duration_result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(input_audio)],
        capture_output=True,
        text=True,
        check=True,
    )
    duration = float(duration_result.stdout.strip())
    silence_result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(vocals), "-af", "silencedetect=noise=-42dB:d=0.5", "-f", "null", "NUL"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    vocal_start, vocal_end = select_vocal_window(silence_result.stderr, duration)
    vocal_duration = vocal_end - vocal_start

    source_lines = [line for line in lyrics if line.strip()]
    if not source_lines:
        if not use_asr_fallback:
            raise RuntimeError("no lyrics supplied and ASR fallback is disabled")
        asr_dir = stages / "asr"
        subprocess.run(
            [str(project_python), str(repo_root / "scripts" / "feibi_asr_faster_whisper.py"), "--source-audio", str(vocals), "--transcript-json", str(asr_dir / "transcript.json"), "--transcript-txt", str(asr_dir / "transcript.txt"), "--language", "auto", "--device", "cpu", "--compute-type", "int8"],
            cwd=repo_root,
            check=True,
        )
        source_lines = (asr_dir / "transcript.txt").read_text(encoding="utf-8-sig").splitlines()

    rewritten, checks = rewrite_lyrics(source_lines)
    rewritten_path = output_dir / "rewritten_lyrics.txt"
    rewritten_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    validation = {"all_passed": all(check.accepted for check in checks), "lines": [check.as_dict() for check in checks]}
    (output_dir / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not validation["all_passed"]:
        raise RuntimeError("rewritten lyrics failed validation")

    ace_dir = stages / "ace_step_lyric_edit"
    ace_source = ace_dir / "source_vocal_window.wav"
    ace_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(vocal_start), "-t", str(vocal_duration), "-i", str(input_audio), "-c:a", "pcm_s16le", str(ace_source)], check=True)
    ace_output = ace_dir / "ace_step_output.wav"
    ace_env = env | {"ACESTEP_CHECKPOINTS_DIR": str(repo_root / "models" / "ace_step" / "checkpoints")}
    subprocess.run(
        [str(ace_python), str(repo_root / "scripts" / "feibi_ace_step_v15.py"), "--source-audio", str(ace_source), "--lyrics", str(rewritten_path), "--output", str(ace_output), "--runtime-root", str(repo_root / "models" / "ace_step" / "runtime"), "--checkpoints-dir", str(repo_root / "models" / "ace_step" / "checkpoints"), "--duration", str(vocal_duration), "--cover-strength", "0.95"],
        cwd=repo_root,
        env=ace_env,
        check=True,
    )

    generated_demucs = stages / "generated_song_separation"
    subprocess.run(
        [str(rvc_python), "-m", "demucs.separate", "--two-stems", "vocals", "-n", "htdemucs", "-d", "cuda", "-o", str(generated_demucs), "--", str(ace_output)],
        cwd=repo_root,
        env=env,
        check=True,
    )
    generated_vocals = next(generated_demucs.rglob("vocals.wav"))

    rvc_dir = stages / "rvc_voice_conversion"
    converted = rvc_dir / "converted_vocals.wav"
    rvc_dir.mkdir(parents=True, exist_ok=True)
    rvc_assets = repo_root / "models" / "rvc" / "assets"
    rvc_env = env | {"HOME": str(repo_root / "models" / "rvc" / "home"), "USERPROFILE": str(repo_root / "models" / "rvc" / "home")}
    subprocess.run(
        [str(rvc_python), str(repo_root / "scripts" / "feibi_rvc_infer.py"), "--source-song", str(generated_vocals), "--model", str(repo_root / "models" / "rvc" / "feibiv1.0.0_e200_s1600.pth"), "--index", str(repo_root / "models" / "rvc" / "feibiv1.0.0_v2.index"), "--runtime-root", str(repo_root / "models" / "rvc" / "runtime"), "--hubert-model", str(rvc_assets / "hubert_base.pt"), "--rmvpe-model", str(rvc_assets / "rmvpe.pt"), "--output", str(converted)],
        cwd=repo_root,
        env=rvc_env,
        check=True,
    )

    aligned = rvc_dir / "aligned_vocals.wav"
    delay_ms = round(vocal_start * 1000)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(converted), "-filter_complex", f"[0:a]adelay={delay_ms}|{delay_ms},apad=whole_dur={duration},atrim=duration={duration}[out]", "-map", "[out]", "-c:a", "pcm_s24le", str(aligned)], check=True)
    original_lufs = measure_integrated_lufs(vocals, vocal_start, vocal_duration)
    converted_lufs = measure_integrated_lufs(aligned, vocal_start, vocal_duration)
    vocal_gain_db = calculate_vocal_gain_db(original_lufs, converted_lufs)
    final_song = output_dir / "final_feibi_song.wav"
    mix_filter = (
        "[0:a]aresample=48000[inst];"
        f"[1:a]pan=stereo|c0=c0|c1=c0,volume={vocal_gain_db}dB[voc];"
        "[inst][voc]amix=inputs=2:duration=first:normalize=0,"
        "volume=0.85,alimiter=limit=0.8913:level=false[out]"
    )
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(instrumental), "-i", str(aligned), "-filter_complex", mix_filter, "-map", "[out]", "-c:a", "pcm_s24le", str(final_song)], check=True)
    final_mp3 = output_dir / "final_feibi_song.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(final_song), "-c:a", "libmp3lame", "-b:a", "320k", str(final_mp3)], check=True)

    report = {"status": "completed", "strategy": "timeline_aligned_original_instrumental", "input_audio": str(input_audio), "lyrics_source": "user_provided" if lyrics else "asr_fallback", "vocal_window": {"start": vocal_start, "end": vocal_end, "delay_ms": delay_ms}, "mix": {"vocal_gain_db": vocal_gain_db, "gain_mode": "match_original_vocal_integrated_lufs", "original_vocal_lufs": original_lufs, "converted_vocal_lufs": converted_lufs}, "outputs": {"final_song": str(final_song), "final_mp3": str(final_mp3), "aligned_vocals": str(aligned), "original_instrumental": str(instrumental)}}
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
