import json
from pathlib import Path

import pytest

from feibi_singer.segment_workbench import SegmentWorkbench, WorkbenchError
from feibi_singer.timeline_pipeline import ACE_CAPTION


def make_run(tmp_path: Path, segment_count: int = 2) -> Path:
    run_dir = tmp_path / "run"
    segments = []
    for index in range(1, segment_count + 1):
        start = (index - 1) * 15.0
        end = index * 15.0
        segment_dir = run_dir / "stages" / "segmented_voice_conversion" / f"segment_{index:02d}"
        candidate_dir = segment_dir / "candidates" / "seed_44"
        vocals = candidate_dir / "demucs" / "htdemucs" / "ace_step_output" / "vocals.wav"
        vocals.parent.mkdir(parents=True, exist_ok=True)
        for path in [segment_dir / "source.wav", candidate_dir / "ace_step_output.wav", vocals, segment_dir / "converted_vocals.wav"]:
            path.write_bytes(b"audio")
        (segment_dir / "lyrics.txt").write_text(f"line {index}\n", encoding="utf-8")
        (segment_dir / "original_lyrics.txt").write_text(f"original line {index}\n", encoding="utf-8")
        segments.append(
            {
                "index": index,
                "core_start": start,
                "core_end": end,
                "input_start": max(0.0, start - 7.5),
                "input_end": end + 7.5,
                "selected_seed": 44,
                "rvc_f0_change": 2,
            }
        )
    separation = run_dir / "stages" / "separation"
    separation.mkdir(parents=True)
    (separation / "instrumental.wav").write_bytes(b"audio")
    (separation / "vocals.wav").write_bytes(b"audio")
    report = {
        "ace_caption": ACE_CAPTION,
        "vocal_window": {"start": 10.0, "end": 10.0 + segment_count * 15.0},
        "segmentation": {"segments": segments},
        "outputs": {"original_instrumental": str(separation / "instrumental.wav")},
    }
    (run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return run_dir


def test_workbench_loads_existing_segment_candidates(tmp_path):
    workbench = SegmentWorkbench(make_run(tmp_path))

    assert workbench.segment_indices == [1, 2]
    segment = workbench.segment(1)
    assert segment["default_seed"] == 44
    assert segment["default_caption"] == ACE_CAPTION
    assert segment["default_lyrics"] == "line 1"
    assert segment["default_original_lyrics"] == "original line 1"
    assert segment["flow_edit_available"] is True
    assert workbench.candidate_choices(1)[0][1] == "source-seed-44"
    assert workbench.rvc_choices(1, "source-seed-44")[0][1] == "source-f0-+2"


def test_workbench_persists_approved_candidate(tmp_path):
    run_dir = make_run(tmp_path)
    workbench = SegmentWorkbench(run_dir)

    approved = workbench.approve(1, "source-seed-44", "source-f0-+2")
    reloaded = SegmentWorkbench(run_dir)

    assert approved["seed"] == 44
    assert approved["f0_change"] == 2
    assert reloaded.segment(1)["approved"]["rvc_id"] == "source-f0-+2"
    assert "Segment 1: seed 44" in reloaded.approval_summary()


def test_ace_command_uses_segment_duration_and_custom_controls(tmp_path):
    workbench = SegmentWorkbench(make_run(tmp_path))
    lyrics = tmp_path / "lyrics.txt"
    output = tmp_path / "ace.wav"

    command = workbench.ace_command(2, 48, " custom caption ", lyrics, output)

    assert command[command.index("--seed") + 1] == "48"
    assert command[command.index("--caption") + 1] == "custom caption"
    assert command[command.index("--duration") + 1] == "30.0"
    assert command[command.index("--lyrics") + 1] == str(lyrics)
    assert command[command.index("--cover-strength") + 1] == "1.0"
    assert "--flow-edit" in command
    assert command[command.index("--flow-edit-source-lyrics") + 1] == "original line 2"
    assert command[command.index("--flow-edit-source-caption") + 1] == ACE_CAPTION


def test_preview_methods_return_original_melody_and_generated_melody_paths(tmp_path, monkeypatch):
    run_dir = make_run(tmp_path)
    workbench = SegmentWorkbench(run_dir)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(command[-1]).write_bytes(b"preview")

    monkeypatch.setattr("feibi_singer.segment_workbench._run", fake_run)
    ace = workbench.ace_preview(1, "source-seed-44")
    rvc = workbench.rvc_preview(1, "source-seed-44", "source-f0-+2")

    assert Path(ace["with_original"]).exists()
    assert Path(ace["generated_melody"]).exists()
    assert Path(rvc["with_original"]).exists()
    assert Path(rvc["vocal_only"]).exists()
    assert len(calls) == 3


def test_rvc_command_uses_per_segment_pitch(tmp_path):
    workbench = SegmentWorkbench(make_run(tmp_path))
    command = workbench.rvc_command(tmp_path / "vocals.wav", -3, tmp_path / "rvc.wav")

    assert command[command.index("--f0-change") + 1] == "-3"


def test_generate_ace_rejects_blank_preset_lyrics(tmp_path):
    workbench = SegmentWorkbench(make_run(tmp_path))

    with pytest.raises(WorkbenchError, match="cannot be blank"):
        workbench.generate_ace(1, 44, ACE_CAPTION, "   ")


def test_merge_requires_every_segment_to_be_approved(tmp_path):
    workbench = SegmentWorkbench(make_run(tmp_path))
    workbench.approve(1, "source-seed-44", "source-f0-+2")

    with pytest.raises(WorkbenchError, match=r"missing: \[2\]"):
        workbench.merge_approved()

