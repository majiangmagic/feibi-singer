from pathlib import Path
from feibi_singer.pipeline import FeibiPipeline

def test_dry_run(tmp_path):
    inp=tmp_path/"song.wav"; inp.write_bytes(b"placeholder")
    report=FeibiPipeline(dry_run=True).run(inp,tmp_path/"run",[chr(0x4f60)+chr(0x597d)+chr(0x4e16)+chr(0x754c)])
    assert report.validation["all_passed"]
    assert (tmp_path/"run"/"report.json").exists()
    assert all(s.status == "planned" for s in report.stages)
