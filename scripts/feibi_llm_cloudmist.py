#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_API_BASE = 'https://api.cloudmist.cloud/v1'
DEFAULT_MODEL = 'gpt-4o'


def _read_lines(value: str | None) -> list[str]:
    if not value:
        return []
    value = value.strip()
    if not value:
        return []
    path = Path(value)
    if path.exists():
        return [line for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return [line for line in value.splitlines() if line.strip()]
    if isinstance(loaded, list):
        return [str(item) for item in loaded if str(item).strip()]
    if isinstance(loaded, str):
        return [line for line in loaded.splitlines() if line.strip()]
    return []


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', raw, re.S)
    if match:
        candidate = match.group(0)
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    raise ValueError('LLM response is not valid JSON')


def _build_prompt(source_lines: list[str]) -> tuple[str, str]:
    system_lines = [
        '你是菲比演唱器的歌词改写器。',
        '任务：把输入歌词改写成菲比风格歌词。',
        '硬性要求：',
        '1. 输出行数必须与输入行数完全一致。',
        '2. 尽量保持每一行的音节数、拍点、节奏长度不变。',
        '3. 旋律贴合优先，优先使用这些菲比风格片段：菲+比+、菲+比+啾+、菲+比+啾+比、菲+八、菲+八啾+比、菲八分钱。',
        '4. 其中 + 表示至少出现一次；菲+比+啾+比 代表菲/比/啾可重复，但结尾必须是比。',
        '5. 支持中文、日文、英文及混合语言输入，必要时优先用音节近似与语气节奏，而不是逐字直译。',
        '6. 只输出 JSON，不要解释，不要 markdown，不要代码块。',
        '7. JSON 格式必须是 {"rewritten_lines": ["...", ...]}。',
    ]
    user_lines = [f'{idx}. {line}' for idx, line in enumerate(source_lines, 1)]
    system = '\n'.join(system_lines)
    user = '输入歌词：\n' + '\n'.join(user_lines) + '\n\n请输出对应的 rewritten_lines。'
    return system, user


def _call_openai_compatible(api_base: str, api_key: str, model: str, system: str, user: str, temperature: float) -> str:
    url = api_base.rstrip('/') + '/chat/completions'
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'temperature': temperature,
    }
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace') if hasattr(exc, 'read') else str(exc)
        raise RuntimeError(f'CloudMist request failed: {exc.code} {exc.reason}: {detail}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'CloudMist request failed: {exc.reason}') from exc
    response_payload = json.loads(body)
    choices = response_payload.get('choices') or []
    if not choices:
        raise RuntimeError('CloudMist response has no choices')
    message = choices[0].get('message') or {}
    content = message.get('content')
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError('CloudMist response has empty content')
    return content


def _normalize_output(source_lines: list[str], payload: dict[str, Any], raw_text: str) -> list[str]:
    rewritten = payload.get('rewritten_lines')
    if isinstance(rewritten, list):
        lines = [str(item).strip() for item in rewritten if str(item).strip()]
        if lines:
            if len(lines) == len(source_lines):
                return lines
            if len(lines) > len(source_lines):
                return lines[: len(source_lines)]
            return lines + source_lines[len(lines):]
    text = str(payload.get('text') or payload.get('content') or '').strip()
    if not text:
        text = raw_text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) == len(source_lines):
        return lines
    if len(lines) > len(source_lines):
        return lines[: len(source_lines)]
    if len(lines) == 1 and len(source_lines) == 1:
        return lines
    return [line for line in (lines + source_lines[len(lines):]) if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Feibi lyric rewrite helper using CloudMist OpenAI-compatible API')
    parser.add_argument('--source-lines')
    parser.add_argument('--rewritten-json')
    parser.add_argument('--rewritten-lines')
    parser.add_argument('--api-base')
    parser.add_argument('--api-key')
    parser.add_argument('--model')
    parser.add_argument('--temperature', type=float)
    args = parser.parse_args(argv)

    source_lines = _read_lines(args.source_lines or os.environ.get('FEIBI_SOURCE_LINES_JSON') or os.environ.get('FEIBI_SOURCE_LINES'))
    if not source_lines:
        raise SystemExit('no source lines provided')

    rewritten_json = args.rewritten_json or os.environ.get('FEIBI_REWRITTEN_JSON')
    rewritten_lines_path = args.rewritten_lines or os.environ.get('FEIBI_REWRITTEN_LINES')
    if not rewritten_json or not rewritten_lines_path:
        raise SystemExit('missing rewritten output paths')

    api_base = args.api_base or os.environ.get('CLOUDMIST_API_BASE') or os.environ.get('FEIBI_LLM_API_BASE') or DEFAULT_API_BASE
    api_key = args.api_key or os.environ.get('CLOUDMIST_API_KEY') or os.environ.get('OPENAI_API_KEY') or os.environ.get('FEIBI_LLM_API_KEY')
    if not api_key:
        raise SystemExit('missing CloudMist API key in CLOUDMIST_API_KEY or OPENAI_API_KEY')

    model = args.model or os.environ.get('CLOUDMIST_MODEL') or os.environ.get('FEIBI_LLM_MODEL') or DEFAULT_MODEL
    temperature = args.temperature if args.temperature is not None else float(os.environ.get('FEIBI_LLM_TEMPERATURE', '0.2'))

    stage_dir = Path(os.environ.get('FEIBI_STAGE_DIR', '.')).resolve()
    stage_dir.mkdir(parents=True, exist_ok=True)
    request_path = Path(os.environ.get('FEIBI_REQUEST_JSON', stage_dir / 'request.json'))

    system, user = _build_prompt(source_lines)
    request_payload = {
        'api_base': api_base,
        'model': model,
        'temperature': temperature,
        'source_lines': source_lines,
        'system_prompt': system,
        'user_prompt': user,
        'request_json': str(request_path),
    }
    (stage_dir / 'llm_request.json').write_text(json.dumps(request_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    raw_text = _call_openai_compatible(api_base, api_key, model, system, user, temperature)
    try:
        payload = _extract_json(raw_text)
    except Exception:
        payload = {'rewritten_lines': [line.strip() for line in raw_text.splitlines() if line.strip()], 'raw_text': raw_text}

    rewritten_lines = _normalize_output(source_lines, payload, raw_text)
    result_payload = {
        'api_base': api_base,
        'model': model,
        'temperature': temperature,
        'source_lines': source_lines,
        'rewritten_lines': rewritten_lines,
        'raw_text': raw_text,
        'parsed': payload,
    }
    Path(rewritten_json).write_text(json.dumps(result_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path(rewritten_lines_path).write_text('\n'.join(rewritten_lines) + ('\n' if rewritten_lines else ''), encoding='utf-8')
    (stage_dir / 'llm_response.json').write_text(json.dumps(result_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
