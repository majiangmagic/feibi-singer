#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feibi_singer.models import PipelineConfig
from feibi_singer.pipeline import FeibiPipeline


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Feibi singer pipeline skeleton")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--lyrics", type=Path)
    parser.add_argument("--lyrics-text", help="lyrics text supplied directly instead of a file")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-asr-fallback", action="store_true", help="skip ASR fallback when lyrics are provided")
    parser.add_argument("--legacy-direct-pipeline", action="store_true", help="use the old whole-song ACE/RVC path")
    parser.add_argument("--caption", help="override the default ACE-Step caption for this run")
    parser.add_argument("--seed-plan", help="fixed ACE seeds per segment, comma-separated; omit to search candidates")
    args = parser.parse_args()
    seed_plan = None
    if args.seed_plan:
        try:
            seed_plan = tuple(int(item.strip()) for item in args.seed_plan.split(",") if item.strip())
        except ValueError as exc:
            parser.error(f"--seed-plan must be comma-separated integers: {exc}")

    cfg = PipelineConfig()
    if args.config:
        cfg = PipelineConfig(**json.loads(args.config.read_text(encoding="utf-8-sig")))
    if args.lyrics and args.lyrics_text:
        parser.error("use only one of --lyrics and --lyrics-text")
    lines = args.lyrics.read_text(encoding="utf-8-sig").splitlines() if args.lyrics else (args.lyrics_text.splitlines() if args.lyrics_text else [])
    if not args.dry_run and not args.legacy_direct_pipeline:
        from feibi_singer.timeline_pipeline import run_timeline_pipeline

        report = run_timeline_pipeline(
            args.input.resolve(),
            args.output_dir.resolve(),
            lines,
            use_asr_fallback=not args.no_asr_fallback,
            caption=args.caption,
            seed_plan=seed_plan,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    report = FeibiPipeline(cfg, dry_run=args.dry_run).run(
        args.input,
        args.output_dir,
        lines,
        use_asr_fallback=not args.no_asr_fallback,
    )
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
