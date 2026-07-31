#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def _value(value: str | None, *environment_names: str) -> str:
    if value:
        return value
    for name in environment_names:
        candidate = os.environ.get(name)
        if candidate:
            return candidate
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACE-Step 1.5 non-interactive cover engine")
    parser.add_argument("--source-audio")
    parser.add_argument("--lyrics")
    parser.add_argument("--output")
    parser.add_argument("--runtime-root")
    parser.add_argument("--checkpoints-dir")
    parser.add_argument("--caption", default="Indie rock, emotional, preserve the original melody and rhythm")
    parser.add_argument("--cover-strength", type=float, default=0.9)
    parser.add_argument("--duration", type=float, default=-1.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    source = Path(_value(args.source_audio, "FEIBI_SOURCE_AUDIO", "FEIBI_SOURCE_SONG")).resolve()
    lyrics = Path(_value(args.lyrics, "FEIBI_LYRICS", "FEIBI_REWRITTEN_LINES")).resolve()
    output = Path(_value(args.output, "FEIBI_OUTPUT")).resolve()
    runtime_root = Path(_value(args.runtime_root, "FEIBI_ACE_STEP_RUNTIME_ROOT")).resolve()
    checkpoints_dir = Path(_value(args.checkpoints_dir, "ACESTEP_CHECKPOINTS_DIR")).resolve()

    for label, path in (("source audio", source), ("lyrics", lyrics), ("runtime root", runtime_root)):
        if not path.exists():
            raise SystemExit(f"ACE-Step {label} not found: {path}")
    if not checkpoints_dir.exists():
        raise SystemExit(f"ACE-Step checkpoints not found: {checkpoints_dir}")

    os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(checkpoints_dir)
    os.environ.setdefault("ACESTEP_OFFLOAD_TO_CPU", "true")
    os.environ.setdefault("ACESTEP_DISABLE_TQDM", "true")

    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    handler = AceStepHandler()
    status, initialized = handler.initialize_service(
        project_root=str(runtime_root),
        config_path="acestep-v15-turbo",
        device="cuda",
        compile_model=False,
        offload_to_cpu=True,
        quantization="int8_weight_only",
    )
    if not initialized:
        raise SystemExit(f"ACE-Step initialization failed: {status}")

    params = GenerationParams(
        task_type="cover",
        src_audio=str(source),
        caption=args.caption,
        lyrics=lyrics.read_text(encoding="utf-8-sig"),
        vocal_language="zh",
        duration=args.duration,
        audio_cover_strength=args.cover_strength,
        thinking=False,
        inference_steps=8,
        guidance_scale=1.0,
        seed=args.seed,
    )
    generation_dir = output.parent / "ace_step_generation"
    generation_dir.mkdir(parents=True, exist_ok=True)
    result = generate_music(
        handler,
        None,
        params=params,
        config=GenerationConfig(batch_size=1, use_random_seed=False, seeds=[args.seed], audio_format="wav"),
        save_dir=str(generation_dir),
    )
    if not result.success or not result.audios:
        raise SystemExit(f"ACE-Step generation failed: {result.status_message}")

    generated_path = Path(result.audios[0]["path"]).resolve()
    if not generated_path.exists():
        raise SystemExit(f"ACE-Step reported missing output: {generated_path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(generated_path, output)
    metadata = {
        "engine": "ACE-Step 1.5",
        "model": "acestep-v15-turbo",
        "task_type": "cover",
        "source_audio": str(source),
        "lyrics": str(lyrics),
        "caption": args.caption,
        "cover_strength": args.cover_strength,
        "seed": args.seed,
        "generated_path": str(generated_path),
        "output": str(output),
        "initialization_status": status,
    }
    output.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"ace_step_output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
