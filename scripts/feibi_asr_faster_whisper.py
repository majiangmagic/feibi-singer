#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _arg_or_env(value: str | None, *names: str) -> str:
    if value:
        return value
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Feibi real ASR engine using faster-whisper")
    parser.add_argument("--source-audio")
    parser.add_argument("--transcript-json")
    parser.add_argument("--transcript-txt")
    parser.add_argument("--language")
    parser.add_argument("--model", default=os.environ.get("FEIBI_ASR_MODEL", "small"))
    parser.add_argument("--device", default=os.environ.get("FEIBI_ASR_DEVICE", os.environ.get("FEIBI_DEVICE", "auto")))
    parser.add_argument("--compute-type", default=os.environ.get("FEIBI_ASR_COMPUTE_TYPE", "auto"))
    parser.add_argument("--beam-size", type=int, default=int(os.environ.get("FEIBI_ASR_BEAM_SIZE", "5")))
    args = parser.parse_args(argv)

    source = Path(_arg_or_env(args.source_audio, "FEIBI_ASR_SOURCE_AUDIO", "FEIBI_SOURCE_AUDIO")).resolve()
    transcript_json = Path(_arg_or_env(args.transcript_json, "FEIBI_ASR_TRANSCRIPT_JSON", "FEIBI_TRANSCRIPT_JSON")).resolve()
    transcript_txt = Path(_arg_or_env(args.transcript_txt, "FEIBI_ASR_TRANSCRIPT_TXT", "FEIBI_TRANSCRIPT_TXT")).resolve()
    language = _arg_or_env(args.language, "FEIBI_ASR_LANGUAGE", "FEIBI_LANGUAGE") or "auto"

    if not source.exists():
        raise SystemExit(f"source audio not found: {source}")
    if not transcript_json or not transcript_txt:
        raise SystemExit("missing ASR transcript output path")

    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise SystemExit(f"faster-whisper not available in this Python; use py -3.13: {exc}") from exc

    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    transcribe_kwargs = {"beam_size": args.beam_size, "vad_filter": True}
    if language and language.lower() != "auto":
        transcribe_kwargs["language"] = language
    segments_iter, info = model.transcribe(str(source), **transcribe_kwargs)
    segments = []
    lines = []
    for segment in segments_iter:
        text = (segment.text or "").strip()
        if not text:
            continue
        lines.append(text)
        segments.append({
            "id": getattr(segment, "id", len(segments)),
            "start": segment.start,
            "end": segment.end,
            "text": text,
        })

    payload = {
        "engine": "faster-whisper",
        "model": args.model,
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "lines": lines,
        "segments": segments,
        "text": "\n".join(lines),
    }
    transcript_json.parent.mkdir(parents=True, exist_ok=True)
    transcript_txt.parent.mkdir(parents=True, exist_ok=True)
    transcript_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    transcript_txt.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"transcript_json={transcript_json}")
    print(f"transcript_txt={transcript_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
