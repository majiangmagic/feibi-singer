#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _arg_or_env(value: str | None, *names: str) -> str:
    if value:
        return value
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    return ""


def _find_stem(output_dir: Path, stem: str) -> Path | None:
    stem_lower = stem.lower()
    candidates = []
    for path in output_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".wav", ".flac", ".mp3", ".m4a", ".ogg"}:
            name = path.stem.lower()
            if stem_lower in name:
                candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: (len(str(p)), str(p)))
    return candidates[0]


def _copy_audio(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return
    shutil.copyfile(src, dst)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Feibi real separation engine using audio-separator")
    parser.add_argument("--source-audio")
    parser.add_argument("--vocals")
    parser.add_argument("--instrumental")
    parser.add_argument("--stage-dir")
    parser.add_argument("--model", default=os.environ.get("FEIBI_SEPARATOR_MODEL", "model_bs_roformer_ep_317_sdr_12.9755.ckpt"))
    parser.add_argument("--model-dir", default=os.environ.get("AUDIO_SEPARATOR_MODEL_DIR", str(Path("models") / "separator")))
    parser.add_argument("--single-stem")
    args = parser.parse_args(argv)

    source = Path(_arg_or_env(args.source_audio, "FEIBI_SOURCE_AUDIO", "FEIBI_INPUT_AUDIO", "FEIBI_ASR_SOURCE_AUDIO")).resolve()
    vocals = Path(_arg_or_env(args.vocals, "FEIBI_VOCALS", "FEIBI_VOCALS_AUDIO")).resolve()
    instrumental = Path(_arg_or_env(args.instrumental, "FEIBI_INSTRUMENTAL", "FEIBI_INSTRUMENTAL_AUDIO")).resolve()
    stage_dir = Path(_arg_or_env(args.stage_dir, "FEIBI_STAGE_DIR") or ".").resolve()
    tmp_dir = stage_dir / "audio_separator_output"
    model_dir = Path(args.model_dir).resolve()

    if not source.exists():
        raise SystemExit(f"source audio not found: {source}")
    if not vocals or not instrumental:
        raise SystemExit("missing vocals/instrumental output path")

    tmp_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "audio-separator",
        "--model_filename", args.model,
        "--model_file_dir", str(model_dir),
        "--output_dir", str(tmp_dir),
        "--output_format", "WAV",
        str(source),
    ]
    completed = subprocess.run(command, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    vocals_src = _find_stem(tmp_dir, "vocals")
    instrumental_src = _find_stem(tmp_dir, "instrumental") or _find_stem(tmp_dir, "no_vocals") or _find_stem(tmp_dir, "karaoke")
    if vocals_src is None or instrumental_src is None:
        found = [str(p) for p in tmp_dir.rglob("*") if p.is_file()]
        raise SystemExit(f"audio-separator did not produce vocals/instrumental stems; found={found}")

    _copy_audio(vocals_src, vocals)
    _copy_audio(instrumental_src, instrumental)
    print(f"vocals={vocals}")
    print(f"instrumental={instrumental}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
