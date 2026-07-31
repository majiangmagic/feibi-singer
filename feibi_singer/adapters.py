import json
import shlex
from pathlib import Path
from .models import PipelineConfig, StageResult

class AdapterError(RuntimeError): pass

class ExternalAdapter:
    def __init__(self, config: PipelineConfig, dry_run: bool = False): self.config, self.dry_run = config, dry_run
    def run(self, name: str, command: str, run_dir: Path, inputs: dict) -> StageResult:
        plan=run_dir/(name+".plan.json")
        payload={"stage":name,"command":command,"inputs":inputs,"dry_run":self.dry_run}
        plan.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        if self.dry_run or not command:
            return StageResult(name,"planned" if self.dry_run else "blocked",plan,{"reason": "dry_run" if self.dry_run else "command_not_configured"})
        # Deliberately do not shell=True: templates are passed to a future runner after explicit integration.
        raise AdapterError(f"??????????{name}???????????????")

class LLMAdapter(ExternalAdapter):
    def rewrite(self, lines: list[str], run_dir: Path) -> list[str]:
        (run_dir/"llm_request.json").write_text(json.dumps({"lyrics":lines,"instruction":"????????????????"},ensure_ascii=False,indent=2),encoding="utf-8")
        return []
