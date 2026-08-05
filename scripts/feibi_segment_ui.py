#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feibi_singer.segment_workbench import SegmentWorkbench, WorkbenchError


def _song_id(run_dir: Path) -> str:
    return str(run_dir.resolve())


def _label(run_dir: Path) -> str:
    return run_dir.name


def _discover(workspace_dir: Path) -> dict[str, SegmentWorkbench]:
    sessions: dict[str, SegmentWorkbench] = {}
    if not workspace_dir.exists():
        return sessions
    for report in sorted(workspace_dir.glob("*/report.json")):
        try:
            wb = SegmentWorkbench(report.parent, report.parent / "workbench")
            sessions[_song_id(report.parent)] = wb
        except (FileNotFoundError, WorkbenchError, json.JSONDecodeError):
            continue
    return sessions


def build_app(workbench: SegmentWorkbench, workspace_dir: Path | None = None):
    import gradio as gr

    workspace_dir = (workspace_dir or workbench.run_dir.parent).resolve()
    sessions = _discover(workspace_dir)
    sessions.setdefault(_song_id(workbench.run_dir), workbench)
    current = {"value": workbench}

    def wb() -> SegmentWorkbench:
        return current["value"]

    def safe(fn):
        try:
            return fn()
        except Exception as exc:
            raise gr.Error(str(exc)) from exc

    def song_choices():
        return [(f"{_label(item.run_dir)} ({item.run_dir})", key) for key, item in sessions.items()]

    def segment_choices():
        return wb().segment_indices

    def segment_values(index: int | float | None, voice_gain_db: float = 0.0):
        index = int(index or wb().segment_indices[0])
        segment = wb().segment(index)
        choices = wb().candidate_choices(index)
        candidate_id = choices[0][1] if choices else None
        ace_audio = ace_original = ace_generated = None
        rvc_choices: list[tuple[str, str]] = []
        rvc_id = rvc_audio = rvc_original = rvc_vocal_only = None
        if candidate_id:
            candidate = wb().candidate(index, candidate_id)
            ace_audio = candidate["ace_audio"]
            previews = wb().ace_preview(index, candidate_id, voice_gain_db)
            ace_original, ace_generated = previews["with_original"], previews["generated_melody"]
            rvc_choices = wb().rvc_choices(index, candidate_id)
            if rvc_choices:
                rvc_id = rvc_choices[0][1]
                result = wb().rvc_result(index, candidate_id, rvc_id)
                rvc_audio = result["audio"]
                previews = wb().rvc_preview(index, candidate_id, rvc_id, voice_gain_db)
                rvc_original, rvc_vocal_only = previews["with_original"], previews["vocal_only"]
        approved = segment.get("approved")
        status = (f"已选定：seed {approved['seed']} / RVC {approved['f0_change']:+d}"
                  if approved else "尚未选定本段最佳结果")
        timing = (f"核心区间 {segment['core_start']:.3f}s–{segment['core_end']:.3f}s；"
                  f"生成输入 {segment['input_start']:.3f}s–{segment['input_end']:.3f}s")
        return (
            int(segment["default_seed"]), segment["default_caption"], segment["default_lyrics"],
            int(segment["default_f0_change"]), float(voice_gain_db), segment["source_audio"],
            gr.update(choices=choices, value=candidate_id), ace_audio, ace_original, ace_generated,
            gr.update(choices=rvc_choices, value=rvc_id), rvc_audio, rvc_original, rvc_vocal_only,
            status, timing, wb().approval_summary(),
        )

    def load_segment(index):
        return safe(lambda: segment_values(index, 0.0))

    def select_song(song_id: str):
        def action():
            if song_id not in sessions:
                raise WorkbenchError("找不到歌曲运行项目")
            current["value"] = sessions[song_id]
            first = wb().segment_indices[0]
            return (gr.update(choices=segment_choices(), value=first), *segment_values(first, 0.0),
                    f"已切换到：{wb().run_dir}")
        return safe(action)

    def refresh_songs():
        sessions.update(_discover(workspace_dir))
        choices = song_choices()
        value = _song_id(wb().run_dir)
        return gr.update(choices=choices, value=value)

    def generate_song(input_audio, lyrics_text, run_name, caption_override, seed_plan):
        def action():
            if not input_audio:
                raise WorkbenchError("请先选择输入音频")
            name = "".join(ch for ch in (run_name or "new_song").strip() if ch.isalnum() or ch in "-_ ").strip()
            if not name:
                name = "new_song"
            output_dir = workspace_dir / name
            if output_dir.exists() and (output_dir / "report.json").exists():
                raise WorkbenchError(f"运行目录已存在：{output_dir}")
            cmd = [sys.executable, str(Path(__file__).with_name("feibi_pipeline.py")),
                   "--input", str(Path(input_audio).resolve()), "--output-dir", str(output_dir)]
            if lyrics_text and lyrics_text.strip():
                cmd += ["--lyrics-text", lyrics_text, "--no-asr-fallback"]
            if caption_override and caption_override.strip():
                cmd += ["--caption", caption_override.strip()]
            if seed_plan and seed_plan.strip():
                cmd += ["--seed-plan", seed_plan.strip()]
            completed = subprocess.run(cmd, cwd=str(Path(__file__).parents[1]), text=True,
                                       capture_output=True, encoding="utf-8", errors="replace")
            if completed.returncode:
                raise WorkbenchError((completed.stderr or completed.stdout)[-4000:])
            new_wb = SegmentWorkbench(output_dir, output_dir / "workbench")
            key = _song_id(output_dir)
            sessions[key] = new_wb
            current["value"] = new_wb
            first = new_wb.segment_indices[0]
            return (gr.update(choices=song_choices(), value=key),
                    gr.update(choices=new_wb.segment_indices, value=first), *segment_values(first),
                    f"从头生成完成：{output_dir}")
        return safe(action)

    def generate_ace(index, seed, caption, lyrics, voice_gain_db=0.0):
        def action():
            candidate = wb().generate_ace(int(index), int(seed), caption or "", lyrics or "")
            previews = wb().ace_preview(int(index), candidate["id"], voice_gain_db)
            return (gr.update(choices=wb().candidate_choices(int(index)), value=candidate["id"]),
                    candidate["ace_audio"], previews["with_original"], previews["generated_melody"],
                    gr.update(choices=[], value=None), None, None, None,
                    f"ACE 已生成：{candidate['id']}。请试听 ACE+原旋律 与 ACE 生成旋律。")
        return safe(action)

    def load_candidate(index, candidate_id, voice_gain_db=0.0):
        if not candidate_id:
            return None, None, None, gr.update(choices=[], value=None), None, None, None, "请先选择 ACE 候选"
        def action():
            candidate = wb().candidate(int(index), candidate_id)
            previews = wb().ace_preview(int(index), candidate_id, voice_gain_db)
            choices = wb().rvc_choices(int(index), candidate_id)
            rvc_id = choices[0][1] if choices else None
            if rvc_id:
                result = wb().rvc_result(int(index), candidate_id, rvc_id)
                rp = wb().rvc_preview(int(index), candidate_id, rvc_id, voice_gain_db)
                return (candidate["ace_audio"], previews["with_original"], previews["generated_melody"],
                        gr.update(choices=choices, value=rvc_id), result["audio"], rp["with_original"], rp["vocal_only"],
                        f"已加载 ACE 候选（seed {candidate['seed']}）")
            return (candidate["ace_audio"], previews["with_original"], previews["generated_melody"],
                    gr.update(choices=[], value=None), None, None, None, "已加载 ACE 候选，尚无 RVC 结果")
        return safe(action)

    def generate_rvc(index, candidate_id, f0_change, voice_gain_db=0.0):
        if not candidate_id:
            raise gr.Error("请先选择 ACE 候选")
        def action():
            result = wb().generate_rvc(int(index), candidate_id, int(f0_change))
            previews = wb().rvc_preview(int(index), candidate_id, result["id"], voice_gain_db)
            return (gr.update(choices=wb().rvc_choices(int(index), candidate_id), value=result["id"]),
                    result["audio"], previews["with_original"], previews["vocal_only"],
                    f"RVC 已生成：动态升调 {result['f0_change']:+d} 半音")
        return safe(action)

    def load_rvc(index, candidate_id, rvc_id, voice_gain_db=0.0):
        if not candidate_id or not rvc_id:
            return None, None, None, "请选择 RVC 结果"
        def action():
            result = wb().rvc_result(int(index), candidate_id, rvc_id)
            previews = wb().rvc_preview(int(index), candidate_id, rvc_id, voice_gain_db)
            return result["audio"], previews["with_original"], previews["vocal_only"], f"已加载 RVC：{result['f0_change']:+d} 半音"
        return safe(action)

    def update_preview_gain(index, candidate_id, rvc_id, voice_gain_db):
        def action():
            ace_original = rvc_original = None
            if candidate_id:
                ace_original = wb().ace_preview(int(index), candidate_id, float(voice_gain_db))["with_original"]
                if rvc_id:
                    rvc_original = wb().rvc_preview(
                        int(index), candidate_id, rvc_id, float(voice_gain_db)
                    )["with_original"]
            return ace_original, rvc_original, f"试听人声音量：{float(voice_gain_db):+.1f} dB"
        return safe(action)

    def approve(index, candidate_id, rvc_id):
        if not candidate_id or not rvc_id:
            raise gr.Error("请先选择 ACE 和 RVC 结果")
        return safe(lambda: (f"已选定第 {int(index)} 段：" + str(wb().approve(int(index), candidate_id, rvc_id)["seed"]), wb().approval_summary()))

    def merge(output_name):
        def action():
            clean = "".join(ch for ch in (output_name or "").strip() if ch.isalnum() or ch in "-_ ").strip() or "final_feibi_song"
            result = wb().merge_approved(clean)
            return result["wav"], result["mp3"], result["report"], f"合并完成；人声响度增益 {result['vocal_gain_db']:+.2f} dB"
        return safe(action)

    first = wb().segment_indices[0]
    with gr.Blocks(title="菲比歌手分段工作台") as app:
        gr.Markdown("# 菲比歌手分段工作台\n逐段替换 ACE seed / caption / 预设歌词，试听 **ACE+原旋律** 和 **ACE生成旋律**；再调整 RVC 动态升调，选定后合并。")
        with gr.Row():
            song = gr.Dropdown(choices=song_choices(), value=_song_id(wb().run_dir), label="歌曲 / 运行项目", interactive=True)
            refresh = gr.Button("刷新歌曲列表")
            song_status = gr.Textbox(label="项目状态", interactive=False)
        gr.Markdown("## 从头开始生成（新歌曲会加入上面的项目列表）")
        with gr.Row():
            input_audio = gr.Audio(label="输入歌曲音频", type="filepath")
            lyrics_text = gr.Textbox(label="原始歌词文本（可选）", placeholder="直接输入多行原始歌词", lines=6)
        with gr.Row():
            run_name = gr.Textbox(label="输出运行名称", value="new_song")
            caption_override = gr.Textbox(label="Caption 覆盖（留空使用原默认值）")
            seed_plan = gr.Textbox(label="Seed 计划（可选，如 44,46,45）")
        generate_song_button = gr.Button("从头开始生成歌曲", variant="primary")
        with gr.Row():
            segment_index = gr.Dropdown(choices=segment_choices(), value=first, label="选择 15 秒分段", interactive=True)
            timing = gr.Textbox(label="分段时间", interactive=False)
        with gr.Row():
            source_audio = gr.Audio(label="原始分段试听", type="filepath")
            status = gr.Textbox(label="当前状态", interactive=False)
        gr.Markdown("## 1. ACE-Step（CAS）")
        with gr.Row():
            seed = gr.Number(label="ACE seed", precision=0)
            caption = gr.Textbox(label="ACE Caption", lines=3)
        lyrics = gr.Textbox(label="ACE 预设歌词", lines=5)
        generate_ace_button = gr.Button("按当前设置重新生成 ACE", variant="primary")
        candidate = gr.Dropdown(label="ACE 候选历史", choices=[], interactive=True)
        with gr.Row():
            ace_audio = gr.Audio(label="ACE 原始结果", type="filepath")
            ace_original_audio = gr.Audio(label="ACE + 原旋律", type="filepath")
            ace_generated_audio = gr.Audio(label="ACE 生成旋律", type="filepath")
        gr.Markdown("## 2. RVC 动态升调")
        with gr.Row():
            f0_change = gr.Slider(-12, 12, value=2, step=1, label="RVC 动态升调（半音）")
            voice_gain_db = gr.Slider(-6, 12, value=0, step=1, label="试听人声音量增益（dB）")
            generate_rvc_button = gr.Button("用当前 ACE 生成 RVC", variant="primary")
        preview_gain_status = gr.Textbox(
            label="试听混音状态", value="试听人声音量：+0.0 dB", interactive=False
        )
        rvc_result = gr.Dropdown(label="RVC 结果历史", choices=[], interactive=True)
        with gr.Row():
            rvc_audio = gr.Audio(label="RVC 原始结果", type="filepath")
            rvc_original_audio = gr.Audio(label="RVC + 原旋律", type="filepath")
            rvc_vocal_only_audio = gr.Audio(label="RVC 纯人声（辅助）", type="filepath")
        approve_button = gr.Button("选为本段最佳结果", variant="primary")
        approval_summary = gr.Textbox(label="分段选定情况", lines=7, interactive=False)
        with gr.Row():
            output_name = gr.Textbox(value="final_feibi_song", label="最终文件名")
            merge_button = gr.Button("合并所有最佳分段", variant="primary")
        with gr.Row():
            final_wav = gr.Audio(label="最终 WAV", type="filepath")
            final_mp3 = gr.Audio(label="最终 MP3", type="filepath")
        final_report = gr.File(label="合并报告")
        merge_status = gr.Textbox(label="合并状态", interactive=False)

        load_outputs = [seed, caption, lyrics, f0_change, voice_gain_db, source_audio, candidate, ace_audio, ace_original_audio, ace_generated_audio, rvc_result, rvc_audio, rvc_original_audio, rvc_vocal_only_audio, status, timing, approval_summary]
        app.load(load_segment, inputs=[segment_index], outputs=load_outputs)
        segment_index.change(load_segment, inputs=[segment_index], outputs=load_outputs)
        song.change(select_song, inputs=[song], outputs=[segment_index, *load_outputs, song_status])
        refresh.click(refresh_songs, outputs=[song])
        generate_song_button.click(generate_song, inputs=[input_audio, lyrics_text, run_name, caption_override, seed_plan], outputs=[song, segment_index, *load_outputs, song_status])
        generate_ace_button.click(generate_ace, inputs=[segment_index, seed, caption, lyrics, voice_gain_db], outputs=[candidate, ace_audio, ace_original_audio, ace_generated_audio, rvc_result, rvc_audio, rvc_original_audio, rvc_vocal_only_audio, status], queue=False)
        candidate.input(load_candidate, inputs=[segment_index, candidate, voice_gain_db], outputs=[ace_audio, ace_original_audio, ace_generated_audio, rvc_result, rvc_audio, rvc_original_audio, rvc_vocal_only_audio, status])
        generate_rvc_button.click(generate_rvc, inputs=[segment_index, candidate, f0_change, voice_gain_db], outputs=[rvc_result, rvc_audio, rvc_original_audio, rvc_vocal_only_audio, status])
        rvc_result.input(load_rvc, inputs=[segment_index, candidate, rvc_result, voice_gain_db], outputs=[rvc_audio, rvc_original_audio, rvc_vocal_only_audio, status])
        voice_gain_db.release(update_preview_gain, inputs=[segment_index, candidate, rvc_result, voice_gain_db], outputs=[ace_original_audio, rvc_original_audio, preview_gain_status])
        approve_button.click(approve, inputs=[segment_index, candidate, rvc_result], outputs=[status, approval_summary])
        merge_button.click(merge, inputs=[output_name], outputs=[final_wav, final_mp3, final_report, merge_status])
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive ACE/RVC segment workbench")
    parser.add_argument("--run-dir", type=Path, help="initial completed run directory")
    parser.add_argument("--workbench-dir", type=Path)
    parser.add_argument("--workspace-dir", type=Path, help="directory containing multiple run directories")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    workspace = (args.workspace_dir or (args.run_dir.parent if args.run_dir else Path("runs"))).resolve()
    initial = args.run_dir.resolve() if args.run_dir else None
    if initial is None:
        found = _discover(workspace)
        if not found:
            parser.error("请提供 --run-dir，或在 --workspace-dir 下放置至少一个包含 report.json 的运行项目")
        initial = next(iter(found.values())).run_dir
    workbench = SegmentWorkbench(initial, args.workbench_dir)
    app = build_app(workbench, workspace)
    app.queue(default_concurrency_limit=1).launch(server_name=args.host, server_port=args.port,
        inbrowser=not args.no_browser, allowed_paths=[str(workspace), str(initial)], show_error=True,
        theme=__import__("gradio").themes.Soft())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

