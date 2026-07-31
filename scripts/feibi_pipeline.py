import argparse, json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feibi_singer.models import PipelineConfig
from feibi_singer.pipeline import FeibiPipeline

def main():
 p=argparse.ArgumentParser(description="??????????? dry-run?")
 p.add_argument("--input",required=True,type=Path); p.add_argument("--output-dir",required=True,type=Path); p.add_argument("--lyrics",type=Path); p.add_argument("--config",type=Path); p.add_argument("--dry-run",action="store_true")
 a=p.parse_args(); cfg=PipelineConfig()
 if a.config: cfg=PipelineConfig(**json.loads(a.config.read_text(encoding="utf-8-sig")))
 lines=a.lyrics.read_text(encoding="utf-8").splitlines() if a.lyrics else []
 report=FeibiPipeline(cfg,dry_run=a.dry_run).run(a.input,a.output_dir,lines)
 print(json.dumps(report.as_dict(),ensure_ascii=False,indent=2))
 return 0
if __name__=="__main__": raise SystemExit(main())
