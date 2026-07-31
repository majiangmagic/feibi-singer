import json
from pathlib import Path
from .adapters import ExternalAdapter
from .feibi_rules import rewrite_lyrics
from .models import PipelineConfig, PipelineReport, StageResult

class FeibiPipeline:
    def __init__(self, config: PipelineConfig | None = None, dry_run: bool = True): self.config=config or PipelineConfig(); self.dry_run=dry_run
    def run(self, input_audio: Path, output_dir: Path, lyrics: list[str] | None = None) -> PipelineReport:
        output_dir.mkdir(parents=True,exist_ok=True)
        lines=lyrics or []
        rewritten,checks=rewrite_lyrics(lines)
        validation={"all_passed": all(c.accepted for c in checks), "lines":[c.__dict__ for c in checks]}
        (output_dir/"rewritten_lyrics.txt").write_text("\n".join(rewritten)+"\n",encoding="utf-8")
        (output_dir/"validation.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8")
        adapter=ExternalAdapter(self.config,self.dry_run); stages=[]
        common={"input_audio":str(input_audio),"lyrics":str(output_dir/"rewritten_lyrics.txt")}
        stages.append(adapter.run("separation",self.config.separation_command,output_dir,common))
        stages.append(adapter.run("transcription",self.config.asr_command,output_dir,common))
        stages.append(adapter.run("ace_step_lyric_edit",self.config.ace_step_command,output_dir,common))
        stages.append(adapter.run("rvc_voice_conversion",self.config.rvc_command,output_dir,{**common,"rvc_model":self.config.rvc_model}))
        report=PipelineReport(output_dir,self.dry_run,stages,rewritten,validation)
        (output_dir/"report.json").write_text(json.dumps(report.as_dict(),ensure_ascii=False,indent=2),encoding="utf-8")
        return report
