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
    parser.add_argument("--config", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-asr-fallback", action="store_true", help="skip ASR fallback when lyrics are provided")
    args = parser.parse_args()

    cfg = PipelineConfig()
    if args.config:
        cfg = PipelineConfig(**json.loads(args.config.read_text(encoding="utf-8-sig")))
    lines = args.lyrics.read_text(encoding="utf-8-sig").splitlines() if args.lyrics else []
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
