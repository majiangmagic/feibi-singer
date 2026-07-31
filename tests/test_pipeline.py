from pathlib import Path

from feibi_singer.pipeline import FeibiPipeline


def test_dry_run_creates_stage_artifacts(tmp_path):
    inp = tmp_path / "song.wav"
    inp.write_bytes(b"placeholder")
    report = FeibiPipeline(dry_run=True).run(inp, tmp_path / "run", [chr(0x4F60) + chr(0x597D) + chr(0x4E16) + chr(0x754C)])

    run_dir = tmp_path / "run"
    assert report.validation["all_passed"]
    assert (run_dir / "report.json").exists()
    assert (run_dir / "input_manifest.json").exists()
    assert (run_dir / "rewritten_lyrics.json").exists()
    assert (run_dir / "validation.json").exists()
    assert (run_dir / "stages" / "separation" / "stage.json").exists()
    assert (run_dir / "stages" / "asr" / "stage.json").exists()
    assert (run_dir / "stages" / "lyric_rewrite" / "stage.json").exists()
    assert (run_dir / "stages" / "ace_step_lyric_edit" / "stage.json").exists()
    assert (run_dir / "stages" / "rvc_voice_conversion" / "stage.json").exists()
    assert all(s.status == "planned" for s in report.stages)
    assert report.outputs["final_song"].endswith("final_feibi_song.wav")
