# Feibi Singer

Local pipeline for lyric rewriting and singing generation with ACE-Step + RVC.

## What it does

- rewrites or preserves lyrics based on the project rules
- generates ACE-Step vocal candidates
- converts vocals with RVC
- merges the final song and caches segment workbench results
- supports per-segment seed, caption, lyrics, and RVC pitch overrides

## Key defaults

- New generation tasks now default to **RVC +6 semitones**
- The segment workbench still allows manual pitch override per segment
- Existing reports keep their recorded `rvc_f0_change` value

## Quick start

### Start the segment UI

```bat
start_feibi_ui.bat
```

This opens the local UI at:

```text
http://127.0.0.1:7860/
```

### Run the pipeline from CLI

```powershell
python scripts\feibi_pipeline.py --input .\song.wav --lyrics .\lyrics.txt --output-dir .\runs\demo --dry-run
```

## Main folders

- `feibi_singer/`: pipeline logic and workbench code
- `scripts/`: command-line entry points and UI launcher
- `tests/`: automated tests
- `models/`: ACE-Step / RVC / Demucs assets
- `runs/`: generated song runs and workbench outputs
- `.venv-acestep`, `.venv-rvc`, `.venv`: local Python environments

## Notes

- Keep `models/` intact unless you want to re-download large assets.
- Old run folders under `runs/` can be removed if you no longer need them.
- The repo is designed for local use on Windows.
