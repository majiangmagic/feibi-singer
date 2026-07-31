#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def _arg_or_env(value: str | None, *names: str) -> str:
    if value:
        return value
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    return ""


def _call_http_api(api_url: str, source_audio: Path, lyrics_path: Path, output: Path) -> int:
    import json
    import urllib.error
    import urllib.request

    payload = {
        "task_type": os.environ.get("FEIBI_ACE_STEP_TASK_TYPE", "cover"),
        "src_audio": str(source_audio),
        "lyrics": lyrics_path.read_text(encoding="utf-8-sig"),
        "output_path": str(output),
        "format": output.suffix.lstrip(".") or "wav",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api_url.rstrip("/") + "/generate_music",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(os.environ.get("FEIBI_ACE_STEP_TIMEOUT", "3600"))) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"ACE-Step API failed HTTP {exc.code}: {detail}") from exc
    response_path = output.with_suffix(output.suffix + ".ace_step_response.json")
    response_path.write_bytes(body)
    return 0


def _call_official_python(source_audio: Path, lyrics_path: Path, output: Path) -> int:
    # ACE-Step 官方包/仓库版本之间入口名不稳定，所以这里优先跑用户给的真实命令，
    # 其次尝试已安装包的 python 模块入口；失败时直接报清楚，不再静默造假音频。
    module_command = os.environ.get("FEIBI_ACE_STEP_MODULE_COMMAND")
    if module_command:
        env = os.environ.copy()
        env.update({
            "ACE_STEP_SOURCE_AUDIO": str(source_audio),
            "ACE_STEP_LYRICS": str(lyrics_path),
            "ACE_STEP_OUTPUT": str(output),
            "ACE_STEP_TASK_TYPE": os.environ.get("FEIBI_ACE_STEP_TASK_TYPE", "cover"),
        })
        completed = subprocess.run(module_command, shell=True, env=env)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)
        return 0
    raise SystemExit(
        "ACE-Step engine not installed/configured. Set FEIBI_ACE_STEP_API_URL to a running official ACE-Step API "
        "or set FEIBI_ACE_STEP_MODULE_COMMAND to the official local inference command."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Feibi ACE-Step lyric-edit engine bridge")
    parser.add_argument("--source-audio")
    parser.add_argument("--lyrics")
    parser.add_argument("--output")
    parser.add_argument("--api-url")
    args = parser.parse_args(argv)

    source_audio = Path(_arg_or_env(args.source_audio, "FEIBI_SOURCE_AUDIO", "FEIBI_SOURCE_SONG")).resolve()
    lyrics_path = Path(_arg_or_env(args.lyrics, "FEIBI_LYRICS", "FEIBI_REWRITTEN_LINES")).resolve()
    output = Path(_arg_or_env(args.output, "FEIBI_OUTPUT")).resolve()
    api_url = _arg_or_env(args.api_url, "FEIBI_ACE_STEP_API_URL", "ACE_STEP_API_URL")

    if not source_audio.exists():
        raise SystemExit(f"ACE-Step source audio not found: {source_audio}")
    if not lyrics_path.exists():
        raise SystemExit(f"ACE-Step lyrics file not found: {lyrics_path}")
    output.parent.mkdir(parents=True, exist_ok=True)

    if api_url:
        _call_http_api(api_url, source_audio, lyrics_path, output)
    else:
        _call_official_python(source_audio, lyrics_path, output)

    if not output.exists():
        raise SystemExit("ACE-Step completed but did not write FEIBI_OUTPUT")
    print(f"ace_step_output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
