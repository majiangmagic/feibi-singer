#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def _arg_or_env(value: str | None, *names: str) -> str:
    if value:
        return value
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    return ""


def _install_repo_local_model(model_path: Path, index_path: Path, model_name: str) -> str:
    import rvc_infer.infer as infer_mod

    models_dir = Path(infer_mod.models_dir)
    target_dir = models_dir / model_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_pth = target_dir / model_path.name
    target_index = target_dir / index_path.name if index_path else None
    if not target_pth.exists() or target_pth.stat().st_size != model_path.stat().st_size:
        shutil.copyfile(model_path, target_pth)
    if index_path and index_path.exists() and target_index:
        if not target_index.exists() or target_index.stat().st_size != index_path.stat().st_size:
            shutil.copyfile(index_path, target_index)
    return model_name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Feibi real RVC engine using rvc_infer")
    parser.add_argument("--source-song")
    parser.add_argument("--model")
    parser.add_argument("--index")
    parser.add_argument("--output")
    parser.add_argument("--model-name", default=os.environ.get("FEIBI_RVC_MODEL_NAME", "feibi"))
    parser.add_argument("--f0-method", default=os.environ.get("FEIBI_RVC_F0_METHOD", "rmvpe"))
    parser.add_argument("--f0-change", type=int, default=int(os.environ.get("FEIBI_RVC_F0_CHANGE", "0")))
    args = parser.parse_args(argv)

    source = Path(_arg_or_env(args.source_song, "FEIBI_SOURCE_SONG", "FEIBI_SOURCE_AUDIO")).resolve()
    model = Path(_arg_or_env(args.model, "FEIBI_MODEL", "FEIBI_RVC_MODEL")).resolve()
    index = Path(_arg_or_env(args.index, "FEIBI_INDEX", "FEIBI_RVC_INDEX")).resolve()
    output = Path(_arg_or_env(args.output, "FEIBI_OUTPUT")).resolve()

    if not source.exists():
        raise SystemExit(f"RVC source song not found: {source}")
    if not model.exists():
        raise SystemExit(f"RVC model not found: {model}")
    if not index.exists():
        raise SystemExit(f"RVC index not found: {index}")

    try:
        from rvc_infer import infer_audio
    except Exception as exc:
        raise SystemExit(
            "rvc_infer is installed incompletely or missing its runtime dependency; "
            "install/fix the official RVC runtime for Python 3.13 before running conversion. "
            f"Original error: {exc}"
        ) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    model_name = _install_repo_local_model(model, index, args.model_name)
    generated = infer_audio(model_name, str(source), f0_change=args.f0_change, f0_method=args.f0_method, audio_format="wav")
    if not generated or not Path(str(generated)).exists():
        raise SystemExit(f"RVC inference did not produce output: {generated}")
    shutil.copyfile(str(generated), output)
    print(f"rvc_output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
