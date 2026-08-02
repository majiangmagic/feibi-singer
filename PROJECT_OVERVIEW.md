# Feibi Singer Project Overview

## Short description
A local singing pipeline that rewrites lyrics, generates ACE-Step cover candidates, converts vocals with RVC, and assembles the final song.

## Structure
- `feibi_singer/`: pipeline, timeline segmentation, models, adapters, and lyric rules.
- `scripts/`: command-line entry points and backend bridges.
- `tests/`: unit and integration tests.
- `models/`, `.venv*`, `runs/`: local runtime assets and generated artifacts.

## Features
- Dynamic timeline segmentation and candidate seed search.
- ACE-Step caption with optional per-run CLI override.
- RVC conversion, vocal alignment, loudness matching, and report generation.

## Dependencies
Python, pytest, ffmpeg/ffprobe, ACE-Step, Demucs, RVC, and project virtual environments.

## API / CLI
- `scripts/feibi_pipeline.py`: main pipeline CLI.
- `scripts/feibi_ace_step_v15.py`: ACE-Step CLI, including `--caption`.

## Changelog
- Added optional `--caption` override to the timeline pipeline. Without the option, the approved `ACE_CAPTION` remains unchanged.
