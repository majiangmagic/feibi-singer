from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_lines(value: str | None) -> list[str]:
    if not value:
        return []
    value = value.strip()
    if not value:
        return []
    path = Path(value)
    if path.exists():
        return [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line]
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return [line for line in value.splitlines() if line]
    if isinstance(loaded, list):
        return [str(item) for item in loaded if str(item)]
    if isinstance(loaded, str):
        return [line for line in loaded.splitlines() if line]
    return []


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_or_placeholder(source: str | Path, destination: str | Path, placeholder: bytes) -> None:
    src = Path(source)
    dst = Path(destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists() and src.is_file():
        shutil.copyfile(src, dst)
    else:
        dst.write_bytes(placeholder)


def _run_backend(stage: str, backend_command: str, stage_dir: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        backend_command,
        cwd=stage_dir,
        shell=True,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _write_text(stage_dir / "backend.stdout.log", completed.stdout)
    _write_text(stage_dir / "backend.stderr.log", completed.stderr)
    return completed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feibi local protocol entry")
    parser.add_argument("--stage", required=True, choices=["separation", "asr", "lyric_rewrite", "ace_step_lyric_edit", "rvc_voice_conversion"])
    parser.add_argument("--request-json")
    parser.add_argument("--stage-dir")
    parser.add_argument("--run-dir")
    parser.add_argument("--input")
    parser.add_argument("--source")
    parser.add_argument("--source-audio")
    parser.add_argument("--source-song")
    parser.add_argument("--vocals")
    parser.add_argument("--instrumental")
    parser.add_argument("--transcript-json")
    parser.add_argument("--transcript-txt")
    parser.add_argument("--rewritten-json")
    parser.add_argument("--rewritten-lines")
    parser.add_argument("--lyrics")
    parser.add_argument("--output")
    parser.add_argument("--language")
    parser.add_argument("--mode")
    parser.add_argument("--validation")
    parser.add_argument("--model")
    parser.add_argument("--index")
    parser.add_argument("--source-lines")
    parser.add_argument("--backend-command")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    request_payload = None
    if args.request_json:
        request_payload = _read_json(Path(args.request_json))
    stage_dir = Path(args.stage_dir or (request_payload.get("stage_dir") if isinstance(request_payload, dict) else ".")).resolve()
    stage_dir.mkdir(parents=True, exist_ok=True)

    if args.stage == "separation":
        if not args.vocals or not args.instrumental:
            raise SystemExit("separation requires --vocals and --instrumental")
        source = Path(args.input or args.source or args.source_audio or "")
        env = os.environ.copy()
        env.update({
            "FEIBI_STAGE": args.stage,
            "FEIBI_STAGE_DIR": str(stage_dir),
            "FEIBI_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_STAGE_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_SOURCE_AUDIO": str(source),
            "FEIBI_INPUT_AUDIO": str(source),
            "FEIBI_VOCALS": str(args.vocals),
            "FEIBI_INSTRUMENTAL": str(args.instrumental),
            "FEIBI_COMMAND": args.backend_command or "",
            "FEIBI_BACKEND_COMMAND": args.backend_command or "",
            "FEIBI_SEPARATION_BACKEND_COMMAND": args.backend_command or "",
        })
        if args.backend_command:
            completed = _run_backend(args.stage, args.backend_command, stage_dir, env)
            if completed.returncode != 0:
                _write_json(stage_dir / "result.json", {
                    "stage": args.stage,
                    "status": "failed",
                    "returncode": completed.returncode,
                    "backend_command": args.backend_command,
                    "vocals": args.vocals,
                    "instrumental": args.instrumental,
                })
                raise SystemExit(completed.returncode)
            if not Path(args.vocals).exists() or not Path(args.instrumental).exists():
                _write_json(stage_dir / "result.json", {
                    "stage": args.stage,
                    "status": "failed",
                    "reason": "missing_separation_outputs",
                    "backend_command": args.backend_command,
                    "vocals": args.vocals,
                    "instrumental": args.instrumental,
                })
                raise SystemExit("separation backend did not produce vocals/instrumental outputs")
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "completed",
                "backend_command": args.backend_command,
                "vocals": args.vocals,
                "instrumental": args.instrumental,
            })
        else:
            _copy_or_placeholder(args.input or args.source or args.source_audio or "", args.vocals, b"FEIBI_VOCALS")
            _copy_or_placeholder(args.input or args.source or args.source_audio or "", args.instrumental, b"FEIBI_INSTRUMENTAL")
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "completed",
                "vocals": args.vocals,
                "instrumental": args.instrumental,
                "request_json": args.request_json,
            })
    elif args.stage == "asr":
        if not args.transcript_json or not args.transcript_txt:
            raise SystemExit("asr requires --transcript-json and --transcript-txt")
        if not args.backend_command:
            raise SystemExit("asr requires --backend-command")
        source = Path(args.source or args.source_audio or args.input or "")
        env = os.environ.copy()
        env.update({
            "FEIBI_STAGE": args.stage,
            "FEIBI_STAGE_DIR": str(stage_dir),
            "FEIBI_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_STAGE_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_TRANSCRIPT_JSON": str(args.transcript_json),
            "FEIBI_TRANSCRIPT_TXT": str(args.transcript_txt),
            "FEIBI_LANGUAGE": args.language or "auto",
            "FEIBI_SOURCE_AUDIO": str(source),
            "FEIBI_ASR_SOURCE_AUDIO": str(source),
            "FEIBI_ASR_TRANSCRIPT_JSON": str(args.transcript_json),
            "FEIBI_ASR_TRANSCRIPT_TXT": str(args.transcript_txt),
            "FEIBI_ASR_LANGUAGE": args.language or "auto",
            "FEIBI_COMMAND": args.backend_command,
            "FEIBI_BACKEND_COMMAND": args.backend_command,
            "FEIBI_ASR_BACKEND_COMMAND": args.backend_command,
        })
        completed = _run_backend(args.stage, args.backend_command, stage_dir, env)
        if completed.returncode != 0:
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "failed",
                "returncode": completed.returncode,
                "backend_command": args.backend_command,
                "transcript_json": args.transcript_json,
                "transcript_txt": args.transcript_txt,
            })
            raise SystemExit(completed.returncode)
        if not Path(args.transcript_json).exists() or not Path(args.transcript_txt).exists():
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "failed",
                "reason": "missing_transcript_outputs",
                "backend_command": args.backend_command,
                "transcript_json": args.transcript_json,
                "transcript_txt": args.transcript_txt,
            })
            raise SystemExit("asr backend did not produce transcript outputs")
        _write_json(stage_dir / "result.json", {
            "stage": args.stage,
            "status": "completed",
            "backend_command": args.backend_command,
            "transcript_json": args.transcript_json,
            "transcript_txt": args.transcript_txt,
        })
    elif args.stage == "lyric_rewrite":
        if not args.rewritten_json or not args.rewritten_lines:
            raise SystemExit("lyric_rewrite requires --rewritten-json and --rewritten-lines")
        if not args.backend_command:
            raise SystemExit("lyric_rewrite requires --backend-command")
        source_lines = _read_lines(args.source_lines) if args.source_lines else []
        if not source_lines and request_payload:
            raw = request_payload.get("inputs", {}).get("rewrite_source_lines") if isinstance(request_payload, dict) else None
            if isinstance(raw, list):
                source_lines = [str(item) for item in raw if str(item)]
        env = os.environ.copy()
        env.update({
            "FEIBI_STAGE": args.stage,
            "FEIBI_STAGE_DIR": str(stage_dir),
            "FEIBI_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_STAGE_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_SOURCE_LINES": "\n".join(source_lines),
            "FEIBI_SOURCE_LINES_JSON": json.dumps(source_lines, ensure_ascii=False),
            "FEIBI_REWRITE_SOURCE_LINES_JSON": json.dumps(source_lines, ensure_ascii=False),
            "FEIBI_REWRITTEN_JSON": str(args.rewritten_json),
            "FEIBI_REWRITTEN_LINES": str(args.rewritten_lines),
            "FEIBI_COMMAND": args.backend_command,
            "FEIBI_BACKEND_COMMAND": args.backend_command,
            "FEIBI_LLM_BACKEND_COMMAND": args.backend_command,
        })
        completed = _run_backend(args.stage, args.backend_command, stage_dir, env)
        if completed.returncode != 0:
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "failed",
                "returncode": completed.returncode,
                "backend_command": args.backend_command,
                "rewritten_json": args.rewritten_json,
                "rewritten_lines": args.rewritten_lines,
            })
            raise SystemExit(completed.returncode)
        if not Path(args.rewritten_json).exists() or not Path(args.rewritten_lines).exists():
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "failed",
                "reason": "missing_rewrite_outputs",
                "backend_command": args.backend_command,
                "rewritten_json": args.rewritten_json,
                "rewritten_lines": args.rewritten_lines,
            })
            raise SystemExit("lyric_rewrite backend did not produce rewritten outputs")
        _write_json(stage_dir / "result.json", {
            "stage": args.stage,
            "status": "completed",
            "backend_command": args.backend_command,
            "rewritten_json": args.rewritten_json,
            "rewritten_lines": args.rewritten_lines,
        })
    elif args.stage == "ace_step_lyric_edit":
        if not args.output:
            raise SystemExit("ace_step_lyric_edit requires --output")
        if not args.backend_command:
            raise SystemExit("ace_step_lyric_edit requires --backend-command")
        src = Path(args.source_audio or args.input or args.source_song or "")
        env = os.environ.copy()
        env.update({
            "FEIBI_STAGE": args.stage,
            "FEIBI_STAGE_DIR": str(stage_dir),
            "FEIBI_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_STAGE_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_SOURCE_AUDIO": str(src),
            "FEIBI_SOURCE_SONG": str(src),
            "FEIBI_MODE": args.mode or "lyric_edit",
            "FEIBI_VALIDATION": args.validation or "",
            "FEIBI_OUTPUT": str(args.output),
            "FEIBI_COMMAND": args.backend_command,
            "FEIBI_BACKEND_COMMAND": args.backend_command,
            "FEIBI_ACE_STEP_BACKEND_COMMAND": args.backend_command,
        })
        completed = _run_backend(args.stage, args.backend_command, stage_dir, env)
        if completed.returncode != 0:
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "failed",
                "returncode": completed.returncode,
                "backend_command": args.backend_command,
                "output": args.output,
            })
            raise SystemExit(completed.returncode)
        if not Path(args.output).exists():
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "failed",
                "reason": "missing_ace_step_output",
                "backend_command": args.backend_command,
                "output": args.output,
            })
            raise SystemExit("ace_step_lyric_edit backend did not produce output")
        _write_json(stage_dir / "result.json", {
            "stage": args.stage,
            "status": "completed",
            "backend_command": args.backend_command,
            "output": args.output,
            "mode": args.mode or "lyric_edit",
            "validation": args.validation,
        })
    elif args.stage == "rvc_voice_conversion":
        if not args.output:
            raise SystemExit("rvc_voice_conversion requires --output")
        if not args.backend_command:
            raise SystemExit("rvc_voice_conversion requires --backend-command")
        src = Path(args.source_song or args.source_audio or args.input or "")
        env = os.environ.copy()
        env.update({
            "FEIBI_STAGE": args.stage,
            "FEIBI_STAGE_DIR": str(stage_dir),
            "FEIBI_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_STAGE_REQUEST_JSON": str(args.request_json or ""),
            "FEIBI_SOURCE_SONG": str(src),
            "FEIBI_SOURCE_AUDIO": str(src),
            "FEIBI_MODEL": args.model or "",
            "FEIBI_INDEX": args.index or "",
            "FEIBI_OUTPUT": str(args.output),
            "FEIBI_COMMAND": args.backend_command,
            "FEIBI_BACKEND_COMMAND": args.backend_command,
            "FEIBI_RVC_BACKEND_COMMAND": args.backend_command,
        })
        completed = _run_backend(args.stage, args.backend_command, stage_dir, env)
        if completed.returncode != 0:
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "failed",
                "returncode": completed.returncode,
                "backend_command": args.backend_command,
                "output": args.output,
                "model": args.model,
                "index": args.index,
            })
            raise SystemExit(completed.returncode)
        if not Path(args.output).exists():
            _write_json(stage_dir / "result.json", {
                "stage": args.stage,
                "status": "failed",
                "reason": "missing_rvc_output",
                "backend_command": args.backend_command,
                "output": args.output,
                "model": args.model,
                "index": args.index,
            })
            raise SystemExit("rvc_voice_conversion backend did not produce output")
        _write_json(stage_dir / "result.json", {
            "stage": args.stage,
            "status": "completed",
            "backend_command": args.backend_command,
            "output": args.output,
            "model": args.model,
            "index": args.index,
        })
    else:
        raise SystemExit(f"unsupported stage: {args.stage}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
