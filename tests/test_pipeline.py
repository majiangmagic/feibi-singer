from feibi_singer.models import PipelineConfig
from feibi_singer.pipeline import FeibiPipeline


def test_dry_run_prefers_user_lyrics(tmp_path):
    inp = tmp_path / "song.wav"
    inp.write_bytes(b"placeholder")
    report = FeibiPipeline(dry_run=True).run(
        inp,
        tmp_path / "run",
        [chr(0x4F60) + chr(0x597D) + chr(0x4E16) + chr(0x754C)],
    )

    run_dir = tmp_path / "run"
    assert report.input_manifest["lyric_source"] == "user_provided"
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


def test_dry_run_can_disable_asr_fallback(tmp_path):
    inp = tmp_path / "song.wav"
    inp.write_bytes(b"placeholder")
    report = FeibiPipeline(dry_run=True).run(inp, tmp_path / "run2", [], use_asr_fallback=False)

    asr_stage = next(stage for stage in report.stages if stage.name == "asr")
    assert report.input_manifest["lyric_source"] == "empty"
    assert asr_stage.status == "skipped"
    assert asr_stage.details["reason"] == "lyrics_provided_and_fallback_disabled"


def test_pipeline_config_includes_rvc_paths():
    cfg = PipelineConfig(
        rvc_model="C:/Users/Admin/Desktop/feibiv1.0.0_e200_s1600.pth",
        rvc_index="C:/Users/Admin/Desktop/feibiv1.0.0_v2.index",
    )
    data = cfg.as_dict()
    assert data["rvc_model"].endswith("feibiv1.0.0_e200_s1600.pth")
    assert data["rvc_index"].endswith("feibiv1.0.0_v2.index")
