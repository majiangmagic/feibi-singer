from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from .feibi_rules import rewrite_lyrics, syllable_count

SEGMENT_TARGET_SECONDS = 15.0
SEGMENT_SEARCH_SECONDS = 2.5
SEGMENT_CONTEXT_SECONDS = 7.5
STITCH_HANDLE_SECONDS = 0.25
ACE_CANDIDATE_SEEDS = (44, 43, 45, 46, 47, 48, 49, 50)
MIN_VOCAL_WINDOW_RMS_DB = -40.0
MIN_VOCAL_COVERAGE = 0.85
PREFERRED_VOCAL_COVERAGE = 1.0
RVC_F0_CHANGE = 2
ACE_CAPTION = (
    "Studio indie rock vocal. Clear standard Mandarin diction and lyric intelligibility "
    "are the highest priority. Restrained, clean, even singing; preserve the original "
    "melody and rhythm. No live-concert delivery, shouting, belting, rasp, growling, "
    "ad-libs, or exaggerated emotion."
)


def resolve_caption(caption: str | None = None) -> str:
    """Use a one-run caption override, otherwise preserve the approved default."""

    return caption.strip() if caption and caption.strip() else ACE_CAPTION


@dataclass(frozen=True)
class SegmentPlan:
    core_start: float
    core_end: float
    input_start: float
    input_end: float
    lyrics: tuple[str, ...]

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


def parse_mean_volume_db(output: str) -> float:
    match = re.search(r"mean_volume:\s*(-?(?:\d+(?:\.\d+)?|inf))\s+dB", output)
    if not match:
        raise RuntimeError("unable to parse mean volume")
    return float(match.group(1))


def measure_mean_volume_db(audio: Path) -> float:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(audio), "-af", "volumedetect", "-f", "null", "NUL"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return parse_mean_volume_db(result.stderr)


def measure_vocal_coverage(audio: Path, start: float, duration: float, window_seconds: float = 1.0) -> dict:
    levels = []
    position = 0.0
    while position < duration:
        window_duration = min(window_seconds, duration - position)
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-ss", str(start + position), "-t", str(window_duration), "-i", str(audio), "-af", "volumedetect", "-f", "null", "NUL"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        levels.append(parse_mean_volume_db(result.stderr))
        position += window_seconds
    active = sum(level >= MIN_VOCAL_WINDOW_RMS_DB for level in levels)
    return {"coverage": active / len(levels), "window_rms_db": levels}


def has_preferred_vocal_coverage(coverage: float) -> bool:
    return coverage >= PREFERRED_VOCAL_COVERAGE


def select_dynamic_split_points(
    rms_values: list[float],
    sample_rate: int,
    duration: float,
    *,
    target_seconds: float = SEGMENT_TARGET_SECONDS,
    search_seconds: float = SEGMENT_SEARCH_SECONDS,
) -> list[float]:
    segment_count = max(1, math.ceil(duration / target_seconds))
    target_spacing = duration / segment_count
    points = []
    for point_index in range(1, segment_count):
        target = target_spacing * point_index
        start = max(0, round((target - search_seconds) * sample_rate))
        end = min(len(rms_values), round((target + search_seconds) * sample_rate) + 1)
        if start >= end:
            break
        best = min(
            range(start, end),
            key=lambda index: (
                20 * math.log10(max(rms_values[index], 1e-9))
                + 1.5 * abs(index / sample_rate - target),
                abs(index / sample_rate - target),
            ),
        )
        point = best / sample_rate
        if not points or point - points[-1] >= target_spacing / 2:
            points.append(round(point, 3))
    return points


def assign_segment_lyrics(lines: list[str], split_points: list[float], duration: float) -> list[tuple[str, ...]]:
    weights = [max(1, syllable_count(line)) for line in lines]
    total_weight = sum(weights)
    line_ends = []
    cumulative = 0
    for weight in weights:
        cumulative += weight
        line_ends.append(duration * cumulative / total_weight)

    segments = []
    line_index = 0
    for segment_end in [*split_points, duration]:
        segment_lines = []
        while line_index < len(lines) and (line_ends[line_index] <= segment_end or not segment_lines):
            segment_lines.append(lines[line_index])
            line_index += 1
        segments.append(tuple(segment_lines))
    if line_index < len(lines):
        segments[-1] += tuple(lines[line_index:])
    return segments


def build_segment_plan(
    lines: list[str],
    split_points: list[float],
    duration: float,
    *,
    leading_context: float = 0.0,
    trailing_context: float = 0.0,
) -> list[SegmentPlan]:
    boundaries = [0.0, *split_points, duration]
    weights = [max(1, syllable_count(line)) for line in lines]
    total_weight = sum(weights)
    line_ranges = []
    cumulative = 0
    for line, weight in zip(lines, weights):
        line_start = duration * cumulative / total_weight
        cumulative += weight
        line_end = duration * cumulative / total_weight
        line_ranges.append((line_start, line_end, line))

    plans = []
    for start, end in zip(boundaries, boundaries[1:]):
        input_start = max(-leading_context, start - SEGMENT_CONTEXT_SECONDS)
        input_end = min(duration + trailing_context, end + SEGMENT_CONTEXT_SECONDS)
        segment_lyrics = tuple(
            line for line_start, line_end, line in line_ranges
            if line_end > input_start and line_start < input_end
        )
        plans.append(SegmentPlan(start, end, input_start, input_end, segment_lyrics))
    return plans


def measure_vocal_rms(audio: Path, start: float, duration: float, sample_rate: int = 50) -> list[float]:
    with wave.open(str(audio), "rb") as source:
        if source.getsampwidth() != 2:
            raise RuntimeError(f"dynamic segmentation requires 16-bit PCM vocals: {audio}")
        channels = source.getnchannels()
        source_rate = source.getframerate()
        frames_per_window = max(1, round(source_rate / sample_rate))
        source.setpos(min(source.getnframes(), round(start * source_rate)))
        remaining = round(duration * source_rate)
        values = []
        while remaining > 0:
            frame_count = min(frames_per_window, remaining)
            samples = array("h")
            samples.frombytes(source.readframes(frame_count))
            if not samples:
                break
            frame_total = len(samples) // channels
            energy = 0.0
            for frame in range(frame_total):
                offset = frame * channels
                mono = sum(samples[offset : offset + channels]) / channels / 32768.0
                energy += mono * mono
            values.append(math.sqrt(energy / max(1, frame_total)))
            remaining -= frame_count
    return values


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
    caption: str | None = None,
    seed_plan: tuple[int, ...] | None = None,
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
        "HF_HUB_OFFLINE": "1",
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

    rms_values = measure_vocal_rms(vocals, vocal_start, vocal_duration)
    split_points = select_dynamic_split_points(rms_values, 50, vocal_duration)
    segment_plan = build_segment_plan(
        rewritten,
        split_points,
        vocal_duration,
        trailing_context=min(SEGMENT_CONTEXT_SECONDS, duration - vocal_end),
    )
    segmented_dir = stages / "segmented_voice_conversion"
    segmented_dir.mkdir(parents=True, exist_ok=True)
    ace_env = env | {"ACESTEP_CHECKPOINTS_DIR": str(repo_root / "models" / "ace_step" / "checkpoints")}
    rvc_dir = stages / "rvc_voice_conversion"
    rvc_dir.mkdir(parents=True, exist_ok=True)
    rvc_assets = repo_root / "models" / "rvc" / "assets"
    rvc_env = env | {"HOME": str(repo_root / "models" / "rvc" / "home"), "USERPROFILE": str(repo_root / "models" / "rvc" / "home")}

    if seed_plan is not None and len(seed_plan) != len(segment_plan):
        raise ValueError(f"seed plan must contain exactly {len(segment_plan)} seeds, got {len(seed_plan)}")

    converted_segments = []
    segment_reports = []
    for index, segment in enumerate(segment_plan, start=1):
        segment_dir = segmented_dir / f"segment_{index:02d}"
        segment_dir.mkdir(parents=True, exist_ok=True)
        segment_duration = segment.input_end - segment.input_start
        ace_source = segment_dir / "source.wav"
        segment_lyrics_path = segment_dir / "lyrics.txt"
        segment_lyrics_path.write_text("\n".join(segment.lyrics) + "\n", encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", str(vocal_start + segment.input_start), "-t", str(segment_duration), "-i", str(input_audio), "-c:a", "pcm_s16le", str(ace_source)],
            check=True,
        )
        candidates = []
        candidate_seeds = (seed_plan[index - 1],) if seed_plan is not None else ACE_CANDIDATE_SEEDS
        for seed in candidate_seeds:
            candidate_dir = segment_dir / "candidates" / f"seed_{seed}"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            ace_output = candidate_dir / "ace_step_output.wav"
            if not ace_output.exists():
                subprocess.run(
                    [str(ace_python), str(repo_root / "scripts" / "feibi_ace_step_v15.py"), "--source-audio", str(ace_source), "--lyrics", str(segment_lyrics_path), "--output", str(ace_output), "--runtime-root", str(repo_root / "models" / "ace_step" / "runtime"), "--checkpoints-dir", str(repo_root / "models" / "ace_step" / "checkpoints"), "--caption", resolve_caption(caption), "--duration", str(segment_duration), "--cover-strength", "0.95", "--seed", str(seed)],
                    cwd=repo_root,
                    env=ace_env,
                    check=True,
                )
            generated_demucs = candidate_dir / "demucs"
            generated_vocals = next(generated_demucs.rglob("vocals.wav"), None)
            if generated_vocals is None:
                subprocess.run(
                    [str(rvc_python), "-m", "demucs.separate", "--two-stems", "vocals", "-n", "htdemucs", "-d", "cuda", "-o", str(generated_demucs), "--", str(ace_output)],
                    cwd=repo_root,
                    env=env,
                    check=True,
                )
                generated_vocals = next(generated_demucs.rglob("vocals.wav"))
            core_offset = segment.core_start - segment.input_start
            coverage = measure_vocal_coverage(generated_vocals, core_offset, segment.core_end - segment.core_start)
            candidate = {"seed": seed, "vocals": generated_vocals, "rms_db": measure_mean_volume_db(generated_vocals), **coverage}
            candidates.append(candidate)
            if has_preferred_vocal_coverage(candidate["coverage"]):
                break
        selected_candidate = max(candidates, key=lambda candidate: (candidate["coverage"], candidate["rms_db"]))
        if selected_candidate["coverage"] < MIN_VOCAL_COVERAGE:
            raise RuntimeError(f"segment {index} has no usable ACE vocal candidate: {candidates}")
        generated_vocals = selected_candidate["vocals"]
        converted = segment_dir / "converted_vocals.wav"
        subprocess.run(
            [str(rvc_python), str(repo_root / "scripts" / "feibi_rvc_infer.py"), "--source-song", str(generated_vocals), "--model", str(repo_root / "models" / "rvc" / "feibiv1.0.0_e200_s1600.pth"), "--index", str(repo_root / "models" / "rvc" / "feibiv1.0.0_v2.index"), "--runtime-root", str(repo_root / "models" / "rvc" / "runtime"), "--hubert-model", str(rvc_assets / "hubert_base.pt"), "--rmvpe-model", str(rvc_assets / "rmvpe.pt"), "--f0-change", str(RVC_F0_CHANGE), "--output", str(converted)],
            cwd=repo_root,
            env=rvc_env,
            check=True,
        )
        normalized = segment_dir / "converted_normalized.wav"
        keep_start = segment.core_start - segment.input_start
        if index > 1:
            keep_start -= STITCH_HANDLE_SECONDS
        keep_end = segment.core_end - segment.input_start
        if index < len(segment_plan):
            keep_end += STITCH_HANDLE_SECONDS
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", str(keep_start), "-t", str(keep_end - keep_start), "-i", str(converted), "-af", f"apad,atrim=duration={keep_end - keep_start}", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(normalized)],
            check=True,
        )
        converted_segments.append(normalized)
        segment_reports.append({"index": index, "core_start": segment.core_start, "core_end": segment.core_end, "input_start": segment.input_start, "input_end": segment.input_end, "lyrics": list(segment.lyrics), "ace_candidates": [{"seed": item["seed"], "rms_db": item["rms_db"], "coverage": item["coverage"], "window_rms_db": item["window_rms_db"]} for item in candidates], "selected_seed": selected_candidate["seed"], "rvc_f0_change": RVC_F0_CHANGE})

    converted = rvc_dir / "converted_vocals.wav"
    inputs = [item for path in converted_segments for item in ("-i", str(path))]
    filters = []
    previous = "[0:a]"
    for index, _segment in enumerate(segment_plan[1:], start=1):
        overlap = STITCH_HANDLE_SECONDS * 2
        output = f"[mix{index}]"
        filters.append(f"{previous}[{index}:a]acrossfade=d={overlap}:c1=tri:c2=tri{output}")
        previous = output
    filters.append(f"{previous}apad,atrim=duration={vocal_duration}[out]")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]", "-c:a", "pcm_s24le", str(converted)],
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

    report = {"status": "completed", "strategy": "dynamic_segmented_timeline_aligned_original_instrumental", "ace_caption": resolve_caption(caption), "seed_mode": "fixed_plan" if seed_plan is not None else "coverage_search", "input_audio": str(input_audio), "lyrics_source": "user_provided" if lyrics else "asr_fallback", "vocal_window": {"start": vocal_start, "end": vocal_end, "delay_ms": delay_ms}, "segmentation": {"target_seconds": SEGMENT_TARGET_SECONDS, "search_seconds": SEGMENT_SEARCH_SECONDS, "context_seconds": SEGMENT_CONTEXT_SECONDS, "stitch_handle_seconds": STITCH_HANDLE_SECONDS, "split_points": split_points, "segments": segment_reports}, "mix": {"vocal_gain_db": vocal_gain_db, "gain_mode": "match_original_vocal_integrated_lufs", "original_vocal_lufs": original_lufs, "converted_vocal_lufs": converted_lufs}, "outputs": {"final_song": str(final_song), "final_mp3": str(final_mp3), "segmented_vocals": str(converted), "aligned_vocals": str(aligned), "original_instrumental": str(instrumental)}}
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
