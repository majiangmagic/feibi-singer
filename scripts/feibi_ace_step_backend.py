#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Feibi ACE-Step backend bridge')
    parser.add_argument('--engine-command')
    args = parser.parse_args(argv)

    output = Path(os.environ.get('FEIBI_OUTPUT', 'ace_step_output.wav'))
    stage_dir = Path(os.environ.get('FEIBI_STAGE_DIR', '.')).resolve()
    engine_command = args.engine_command or os.environ.get('FEIBI_ACE_STEP_ENGINE_COMMAND') or os.environ.get('ACE_STEP_ENGINE_COMMAND')
    if not engine_command:
        raise SystemExit('missing ACE-Step engine command; set FEIBI_ACE_STEP_ENGINE_COMMAND')
    env = os.environ.copy()
    env['FEIBI_OUTPUT'] = str(output)
    completed = subprocess.run(engine_command, shell=True, cwd=stage_dir, env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    if not output.exists():
        raise SystemExit('ACE-Step engine did not produce output')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
