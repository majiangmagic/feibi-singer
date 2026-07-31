from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .models import PipelineConfig, StageContract, StageResult


class AdapterError(RuntimeError):
    pass


class ExternalAdapter:
    def __init__(self, config: PipelineConfig, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run

    def _write_json(self, path: Path, payload: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return json.dumps(value, ensure_ascii=False)

    def _context(
        self,
        name: str,
        run_dir: Path,
        stage_dir: Path,
        request_path: Path,
        outputs: dict[str, str] | None,
        inputs: dict[str, Any],
        contract: StageContract | None,
        protocol: dict[str, Any] | None,
    ) -> dict[str, str]:
        repo_root = Path(__file__).resolve().parents[1]
        context: dict[str, str] = {
            "stage": name,
            "run_dir": str(run_dir),
            "stage_dir": str(stage_dir),
            "repo_root": str(repo_root),
            "request_json": str(request_path),
            "stage_request_json": str(request_path),
            "request": str(request_path),
            "inputs_json": json.dumps(inputs, ensure_ascii=False),
            "outputs_json": json.dumps(outputs or {}, ensure_ascii=False),
            "config_json": json.dumps(self.config.as_dict(), ensure_ascii=False),
        }
        if contract is not None and not self.dry_run:
            context["stage_contract_json"] = json.dumps(contract.as_dict(), ensure_ascii=False)
        if protocol is not None:
            context["protocol_json"] = json.dumps(protocol, ensure_ascii=False)
        if outputs:
            for key, value in outputs.items():
                context[key] = value
        for key, value in inputs.items():
            context[key] = self._stringify(value)
        return context

    def _render_command(self, command: str, context: dict[str, str]) -> str:
        class SafeDict(dict):
            def __missing__(self, key: str) -> str:
                return "{" + key + "}"

        rendered = command
        for _ in range(5):
            next_rendered = rendered.format_map(SafeDict(context))
            if next_rendered == rendered:
                break
            rendered = next_rendered
        return rendered

    def _prepare_env(
        self,
        name: str,
        run_dir: Path,
        stage_dir: Path,
        request_path: Path,
        outputs: dict[str, str] | None,
        inputs: dict[str, Any],
        command: str,
        contract: StageContract | None,
        protocol: dict[str, Any] | None,
    ) -> dict[str, str]:
        env = os.environ.copy()
        repo_root = Path(__file__).resolve().parents[1]
        env.update(
            {
                "FEIBI_STAGE": name,
                "FEIBI_RUN_DIR": str(run_dir),
                "FEIBI_STAGE_DIR": str(stage_dir),
                "FEIBI_REPO_ROOT": str(repo_root),
                "FEIBI_REQUEST_JSON": str(request_path),
                "FEIBI_STAGE_REQUEST_JSON": str(request_path),
                "FEIBI_INPUTS_JSON": json.dumps(inputs, ensure_ascii=False),
                "FEIBI_OUTPUTS_JSON": json.dumps(outputs or {}, ensure_ascii=False),
                "FEIBI_CONFIG_JSON": json.dumps(self.config.as_dict(), ensure_ascii=False),
                "FEIBI_COMMAND": command,
            }
        )
        pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(repo_root) if not pythonpath else str(repo_root) + os.pathsep + pythonpath
        if contract is not None and not self.dry_run:
            env["FEIBI_STAGE_CONTRACT_JSON"] = json.dumps(contract.as_dict(), ensure_ascii=False)
        if protocol is not None:
            env["FEIBI_PROTOCOL_JSON"] = json.dumps(protocol, ensure_ascii=False)
        for key, value in inputs.items():
            env_key = "FEIBI_" + "".join(ch if ch.isalnum() else "_" for ch in key).upper()
            env[env_key] = self._stringify(value)
        return env

    def run(
        self,
        name: str,
        command: str,
        run_dir: Path,
        inputs: dict[str, Any],
        outputs: dict[str, str] | None = None,
        contract: StageContract | None = None,
        protocol: dict[str, Any] | None = None,
    ) -> StageResult:
        if contract is not None and contract.name != name:
            raise AdapterError(f"stage contract mismatch: expected {name}, got {contract.name}")
        if contract is not None and not self.dry_run:
            missing_inputs = [field for field in contract.required_inputs if field not in inputs or self._stringify(inputs[field]) == ""]
            if missing_inputs:
                raise AdapterError(f"stage {name} is missing required inputs: {', '.join(missing_inputs)}")
            missing_outputs = [field for field in contract.required_outputs if not outputs or field not in outputs or not outputs[field]]
            if missing_outputs:
                raise AdapterError(f"stage {name} is missing required outputs: {', '.join(missing_outputs)}")

        stage_dir = run_dir / "stages" / name
        stage_dir.mkdir(parents=True, exist_ok=True)
        request_path = stage_dir / "request.json"
        stage_path = stage_dir / "stage.json"
        stdout_path = stage_dir / "stdout.log"
        stderr_path = stage_dir / "stderr.log"

        request_payload = {
            "stage": name,
            "command": command,
            "inputs": inputs,
            "outputs": outputs or {},
            "dry_run": self.dry_run,
            "request_json": str(request_path),
            "stage_dir": str(stage_dir),
            "run_dir": str(run_dir),
        }
        if contract is not None:
            request_payload["contract"] = contract.as_dict()
        if protocol is not None:
            request_payload["protocol_version"] = protocol.get("version")
            request_payload["protocol"] = protocol
        self._write_json(request_path, request_payload)

        if self.dry_run:
            summary = {
                **request_payload,
                "status": "planned",
                "result": {"mode": "dry_run"},
                "request_json": str(request_path),
            }
            self._write_json(stage_path, summary)
            return StageResult(name, "planned", stage_path, {"mode": "dry_run", "request_json": str(request_path)})

        if not command.strip():
            summary = {
                **request_payload,
                "status": "blocked",
                "result": {"reason": "command_not_configured"},
                "request_json": str(request_path),
            }
            self._write_json(stage_path, summary)
            return StageResult(name, "blocked", stage_path, {"reason": "command_not_configured", "request_json": str(request_path)})

        context = self._context(name, run_dir, stage_dir, request_path, outputs, inputs, contract, protocol)
        resolved_command = self._render_command(command, context)
        env = self._prepare_env(name, run_dir, stage_dir, request_path, outputs, inputs, resolved_command, contract, protocol)
        completed = subprocess.run(
            resolved_command,
            cwd=stage_dir,
            shell=True,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")

        missing_outputs = [label for label, path in (outputs or {}).items() if path and not Path(path).exists()]
        status = "completed" if completed.returncode == 0 and not missing_outputs else "failed"
        details: dict[str, Any] = {
            "returncode": completed.returncode,
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "request_json": str(request_path),
            "resolved_command": resolved_command,
        }
        if missing_outputs:
            details["missing_outputs"] = missing_outputs
        if completed.returncode != 0:
            details["reason"] = "command_failed"
        elif missing_outputs:
            details["reason"] = "missing_outputs"

        summary = {
            **request_payload,
            "status": status,
            "resolved_command": resolved_command,
            "execution": {
                "returncode": completed.returncode,
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "missing_outputs": missing_outputs,
            },
            "request_json": str(request_path),
        }
        self._write_json(stage_path, summary)
        return StageResult(name, status, stage_path, details)


class LLMAdapter(ExternalAdapter):
    def rewrite(self, lines: list[str], run_dir: Path) -> Path:
        stage_dir = run_dir / "stages" / "lyric_rewrite"
        stage_dir.mkdir(parents=True, exist_ok=True)
        artifact = stage_dir / "llm_request.json"
        artifact.write_text(
            json.dumps(
                {
                    "lyrics": lines,
                    "instruction": "Rewrite lyrics into Feibi-style syllable-preserving placeholders.",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return artifact
