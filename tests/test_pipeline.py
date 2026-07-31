from pathlib import Path

import pytest

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
    assert all(s.status == "planned" or s.status == "skipped" for s in report.stages)
    assert report.outputs["final_song"].endswith("final_feibi_song.wav")


def test_dry_run_skips_asr_when_user_lyrics_exist(tmp_path):
    inp = tmp_path / "song.wav"
    inp.write_bytes(b"placeholder")
    report = FeibiPipeline(dry_run=True).run(
        inp,
        tmp_path / "run_user",
        [chr(0x4F60) + chr(0x597D)],
    )

    asr_stage = next(stage for stage in report.stages if stage.name == "asr")
    assert report.input_manifest["lyric_source"] == "user_provided"
    assert asr_stage.status == "skipped"
    assert asr_stage.details["reason"] == "user_lyrics_provided"


def test_dry_run_can_disable_asr_fallback(tmp_path):
    inp = tmp_path / "song.wav"
    inp.write_bytes(b"placeholder")
    report = FeibiPipeline(dry_run=True).run(inp, tmp_path / "run2", [], use_asr_fallback=False)

    asr_stage = next(stage for stage in report.stages if stage.name == "asr")
    assert report.input_manifest["lyric_source"] == "empty"
    assert asr_stage.status == "skipped"
    assert asr_stage.details["reason"] == "fallback_disabled"


def test_pipeline_config_includes_rvc_paths():
    cfg = PipelineConfig(
        rvc_model="C:/Users/Admin/Desktop/feibiv1.0.0_e200_s1600.pth",
        rvc_index="C:/Users/Admin/Desktop/feibiv1.0.0_v2.index",
    )
    data = cfg.as_dict()
    assert data["rvc_model"].endswith("feibiv1.0.0_e200_s1600.pth")
    assert data["rvc_index"].endswith("feibiv1.0.0_v2.index")


def test_pipeline_config_validation_for_real_run():
    cfg = PipelineConfig()
    with pytest.raises(ValueError):
        cfg.validate(require_commands=True, require_rvc=True, require_asr=True)


def test_pipeline_config_checks_rvc_paths(tmp_path):
    cfg = PipelineConfig(
        rvc_model=str(tmp_path / "missing.pth"),
        rvc_index=str(tmp_path / "missing.index"),
    )
    with pytest.raises(FileNotFoundError):
        cfg.ensure_rvc_paths_exist()


def test_pipeline_protocol_exposes_command_templates():
    cfg = PipelineConfig(
        separation_command="sep {request_json}",
        asr_command="asr {transcript_json}",
        asr_backend_command="backend {source_audio}",
        llm_command="llm {rewrite_json}",
        ace_step_command="ace {generated_song}",
        rvc_command="rvc {final_song}",
        rvc_model="models/rvc/feibiv1.0.0_e200_s1600.pth",
        rvc_index="models/rvc/feibiv1.0.0_v2.index",
    )
    protocol = cfg.build_protocol()
    assert "request_json" in protocol.stages["separation"].command_placeholders
    assert "stage_request_json" in protocol.stages["lyric_rewrite"].command_placeholders
    assert "asr_backend_command" in protocol.stages["asr"].command_placeholders
    assert "validation" in protocol.stages["ace_step_lyric_edit"].command_placeholders
    assert "final_song" in protocol.stages["rvc_voice_conversion"].command_placeholders
