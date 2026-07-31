#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def _run(command: str, env: dict[str, str], cwd: Path) -> int:
    completed = subprocess.run(command, shell=True, cwd=cwd, env=env)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Feibi ASR backend bridge')
    parser.add_argument('--engine-command')
    args = parser.parse_args(argv)

    transcript_json = Path(os.environ.get('FEIBI_ASR_TRANSCRIPT_JSON', os.environ.get('FEIBI_TRANSCRIPT_JSON', 'transcript.json')))
    transcript_txt = Path(os.environ.get('FEIBI_ASR_TRANSCRIPT_TXT', os.environ.get('FEIBI_TRANSCRIPT_TXT', 'transcript.txt')))
    stage_dir = Path(os.environ.get('FEIBI_STAGE_DIR', '.')).resolve()
    engine_command = args.engine_command or os.environ.get('FEIBI_ASR_ENGINE_COMMAND') or os.environ.get('ASR_ENGINE_COMMAND')
    if not engine_command:
        raise SystemExit('missing ASR engine command; set FEIBI_ASR_ENGINE_COMMAND')
    env = os.environ.copy()
    env['FEIBI_ASR_TRANSCRIPT_JSON'] = str(transcript_json)
    env['FEIBI_ASR_TRANSCRIPT_TXT'] = str(transcript_txt)
    env['FEIBI_TRANSCRIPT_JSON'] = str(transcript_json)
    env['FEIBI_TRANSCRIPT_TXT'] = str(transcript_txt)
    rc = _run(engine_command, env, stage_dir)
    if rc != 0:
        raise SystemExit(rc)
    if not transcript_json.exists() or not transcript_txt.exists():
        raise SystemExit('ASR engine did not produce transcript outputs')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
