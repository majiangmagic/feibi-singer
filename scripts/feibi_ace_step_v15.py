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
    parser = argparse.ArgumentParser(description="ACE-Step 1.5 non-interactive lyric-preserving cover engine")
    parser.add_argument("--source-audio")
    parser.add_argument("--lyrics")
    parser.add_argument("--lyrics-text", help="lyrics text supplied directly")
    parser.add_argument("--flow-edit-source-lyrics", help="original lyrics for flow-edit source conditioning")
    parser.add_argument("--flow-edit-source-caption", default="", help="original caption for flow-edit source conditioning")
    parser.add_argument("--flow-edit", action="store_true", help="enable ACE-Step 1.5 flow-edit on top of cover")
    parser.add_argument("--output")
    parser.add_argument("--runtime-root")
    parser.add_argument("--checkpoints-dir")
    parser.add_argument("--caption", default="Indie rock, emotional, preserve the original melody and rhythm")
    parser.add_argument("--cover-strength", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=-1.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    source_value = _value(args.source_audio, "FEIBI_SOURCE_AUDIO", "FEIBI_SOURCE_SONG")
    lyrics_value = _value(args.lyrics, "FEIBI_LYRICS", "FEIBI_REWRITTEN_LINES")
    output_value = _value(args.output, "FEIBI_OUTPUT")
    runtime_value = _value(args.runtime_root, "FEIBI_ACE_STEP_RUNTIME_ROOT")
    checkpoints_value = _value(args.checkpoints_dir, "ACESTEP_CHECKPOINTS_DIR")
    if not source_value or not output_value or not runtime_value or not checkpoints_value:
        parser.error("source audio, output, runtime root, and checkpoints directory are required")
    if args.lyrics_text is not None and lyrics_value:
        parser.error("use only one of --lyrics and --lyrics-text")
    if args.lyrics_text is None and not lyrics_value:
        parser.error("one of --lyrics and --lyrics-text is required")
    if args.flow_edit and not (args.flow_edit_source_lyrics or "").strip():
        parser.error("--flow-edit requires non-blank --flow-edit-source-lyrics")

    source = Path(source_value).resolve()
    lyrics = Path(lyrics_value).resolve() if lyrics_value else None
    output = Path(output_value).resolve()
    runtime_root = Path(runtime_value).resolve()
    checkpoints_dir = Path(checkpoints_value).resolve()

    for label, path in (("source audio", source), ("runtime root", runtime_root)):
        if not path.exists():
            raise SystemExit(f"ACE-Step {label} not found: {path}")
    if lyrics is not None and not lyrics.exists():
        raise SystemExit(f"ACE-Step lyrics not found: {lyrics}")
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
        lyrics=args.lyrics_text if args.lyrics_text is not None else lyrics.read_text(encoding="utf-8-sig"),
        vocal_language="zh",
        duration=args.duration,
        audio_cover_strength=args.cover_strength,
        cover_noise_strength=0.0,
        flow_edit_morph=args.flow_edit,
        flow_edit_source_caption=args.flow_edit_source_caption,
        flow_edit_source_lyrics=args.flow_edit_source_lyrics or "",
        flow_edit_n_min=0.0,
        flow_edit_n_max=1.0,
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
        "lyrics": str(lyrics) if lyrics is not None else None,
        "lyrics_input": "text" if args.lyrics_text is not None else "file",
        "caption": args.caption,
        "cover_strength": args.cover_strength,
        "cover_noise_strength": 0.0,
        "flow_edit": args.flow_edit,
        "flow_edit_source_lyrics": bool(args.flow_edit_source_lyrics),
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
