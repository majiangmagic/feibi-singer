#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feibi_singer.segment_workbench import SegmentWorkbench, WorkbenchError


def build_app(workbench: SegmentWorkbench):
    import gradio as gr

    def safe(callable_):
        try:
            return callable_()
        except Exception as exc:
            raise gr.Error(str(exc)) from exc

    def load_segment(index: int):
        def action():
            segment = workbench.segment(int(index))
            choices = workbench.candidate_choices(int(index))
            candidate_id = choices[0][1] if choices else None
            ace_audio = None
            rvc_choices = []
            rvc_id = None
            rvc_audio = None
            if candidate_id:
                candidate = workbench.candidate(int(index), candidate_id)
                ace_audio = candidate["ace_audio"]
                rvc_choices = workbench.rvc_choices(int(index), candidate_id)
                if rvc_choices:
                    rvc_id = rvc_choices[0][1]
                    rvc_audio = workbench.rvc_result(int(index), candidate_id, rvc_id)["audio"]
            approved = segment.get("approved")
            status = (
                f"已选最佳：seed {approved['seed']} / RVC {approved['f0_change']:+d}"
                if approved else "尚未选定本段最佳结果"
            )
            timing = (
                f"核心区间 {segment['core_start']:.3f}s–{segment['core_end']:.3f}s；"
                f"生成输入 {segment['input_start']:.3f}s–{segment['input_end']:.3f}s"
            )
            return (
                int(segment["default_seed"]),
                segment["default_caption"],
                segment["default_lyrics"],
                int(segment["default_f0_change"]),
                segment["source_audio"],
                gr.update(choices=choices, value=candidate_id),
                ace_audio,
                gr.update(choices=rvc_choices, value=rvc_id),
                rvc_audio,
                status,
                timing,
                workbench.approval_summary(),
            )
        return safe(action)

    def generate_ace(index: int, seed: int, caption: str, lyrics: str):
        def action():
            candidate = workbench.generate_ace(int(index), int(seed), caption, lyrics)
            choices = workbench.candidate_choices(int(index))
            return (
                gr.update(choices=choices, value=candidate["id"]),
                candidate["ace_audio"],
                gr.update(choices=[], value=None),
                None,
                f"ACE 已生成：{candidate['id']}。请试听；满意后再生成 RVC。",
            )
        return safe(action)

    def load_candidate(index: int, candidate_id: str | None):
        if not candidate_id:
            return None, gr.update(choices=[], value=None), None, "请先选择 ACE 候选"
        def action():
            candidate = workbench.candidate(int(index), candidate_id)
            choices = workbench.rvc_choices(int(index), candidate_id)
            rvc_id = choices[0][1] if choices else None
            rvc_audio = workbench.rvc_result(int(index), candidate_id, rvc_id)["audio"] if rvc_id else None
            return (
                candidate["ace_audio"],
                gr.update(choices=choices, value=rvc_id),
                rvc_audio,
                f"已载入 ACE 候选（seed {candidate['seed']}），可以试听或选择 RVC 结果。",
            )
        return safe(action)

    def generate_rvc(index: int, candidate_id: str | None, f0_change: int):
        if not candidate_id:
            raise gr.Error("请先选择一个 ACE 候选")
        def action():
            result = workbench.generate_rvc(int(index), candidate_id, int(f0_change))
            choices = workbench.rvc_choices(int(index), candidate_id)
            return (
                gr.update(choices=choices, value=result["id"]),
                result["audio"],
                f"RVC 已生成（动态升调 {result['f0_change']:+d}），请试听并决定是否选为本段最佳。",
            )
        return safe(action)

    def load_rvc(index: int, candidate_id: str | None, rvc_id: str | None):
        if not candidate_id or not rvc_id:
            return None, "请先选择 RVC 结果"
        def action():
            result = workbench.rvc_result(int(index), candidate_id, rvc_id)
            return result["audio"], f"已载入 RVC 结果（动态升调 {result['f0_change']:+d}）。"
        return safe(action)

    def approve(index: int, candidate_id: str | None, rvc_id: str | None):
        if not candidate_id or not rvc_id:
            raise gr.Error("请先选择 ACE 和 RVC 结果")
        def action():
            approved = workbench.approve(int(index), candidate_id, rvc_id)
            return (
                f"已选定第 {int(index)} 段：seed {approved['seed']} / RVC {approved['f0_change']:+d}",
                workbench.approval_summary(),
            )
        return safe(action)

    def merge(output_name: str):
        def action():
            clean_name = "".join(ch for ch in output_name.strip() if ch.isalnum() or ch in "-_ ").strip()
            if not clean_name:
                clean_name = "final_feibi_song"
            result = workbench.merge_approved(clean_name)
            return result["wav"], result["mp3"], result["report"], f"合并完成；最终人声响度增益 {result['vocal_gain_db']:+.2f} dB。"
        return safe(action)

    first = workbench.segment_indices[0]
    with gr.Blocks(title="菲比演唱分段工作台") as app:
        gr.Markdown(
            "# 菲比演唱分段工作台\n"
            "逐段调整 ACE-Step seed、提示词和预设歌词，试听 ACE 结果；再调整 RVC 动态升调并试听。"
            "每段选定最佳结果后，统一与原伴奏合并成完整歌曲。"
        )
        with gr.Row():
            segment_index = gr.Dropdown(
                choices=workbench.segment_indices,
                value=first,
                label="选择约 15 秒分段",
                interactive=True,
            )
            timing = gr.Textbox(label="分段时间", interactive=False)
        with gr.Row():
            source_audio = gr.Audio(label="原始分段试听", type="filepath")
            status = gr.Textbox(label="当前状态", interactive=False)

        gr.Markdown("## 1. ACE-Step（CAS）生成与试听")
        with gr.Row():
            seed = gr.Number(label="ACE seed", precision=0)
            caption = gr.Textbox(label="ACE 提示词 / Caption", lines=4)
        lyrics = gr.Textbox(label="ACE 预设歌词", lines=10)
        generate_ace_button = gr.Button("按当前设置重新生成 ACE", variant="primary")
        with gr.Row():
            candidate = gr.Dropdown(label="ACE 候选历史", choices=[], interactive=True)
            ace_audio = gr.Audio(label="ACE 结果试听", type="filepath")

        gr.Markdown("## 2. RVC 动态升调与试听")
        with gr.Row():
            f0_change = gr.Slider(-12, 12, value=2, step=1, label="RVC 动态升调（半音）")
            generate_rvc_button = gr.Button("用当前 ACE 生成 RVC", variant="primary")
        with gr.Row():
            rvc_result = gr.Dropdown(label="RVC 结果历史", choices=[], interactive=True)
            rvc_audio = gr.Audio(label="RVC 结果试听", type="filepath")
        approve_button = gr.Button("选为本段最佳结果", variant="primary")

        gr.Markdown("## 3. 确认全部分段并合并")
        approval_summary = gr.Textbox(label="分段选定情况", lines=7, interactive=False)
        with gr.Row():
            output_name = gr.Textbox(value="final_feibi_song", label="最终文件名")
            merge_button = gr.Button("合并所有最佳分段", variant="primary")
        with gr.Row():
            final_wav = gr.Audio(label="最终 WAV 试听", type="filepath")
            final_mp3 = gr.Audio(label="最终 MP3 试听", type="filepath")
        final_report = gr.File(label="下载合并报告")
        merge_status = gr.Textbox(label="合并状态", interactive=False)

        load_outputs = [
            seed, caption, lyrics, f0_change, source_audio, candidate, ace_audio,
            rvc_result, rvc_audio, status, timing, approval_summary,
        ]
        app.load(load_segment, inputs=[segment_index], outputs=load_outputs)
        segment_index.change(load_segment, inputs=[segment_index], outputs=load_outputs)
        generate_ace_button.click(
            generate_ace,
            inputs=[segment_index, seed, caption, lyrics],
            outputs=[candidate, ace_audio, rvc_result, rvc_audio, status],
        )
        candidate.change(
            load_candidate,
            inputs=[segment_index, candidate],
            outputs=[ace_audio, rvc_result, rvc_audio, status],
        )
        generate_rvc_button.click(
            generate_rvc,
            inputs=[segment_index, candidate, f0_change],
            outputs=[rvc_result, rvc_audio, status],
        )
        rvc_result.change(
            load_rvc,
            inputs=[segment_index, candidate, rvc_result],
            outputs=[rvc_audio, status],
        )
        approve_button.click(
            approve,
            inputs=[segment_index, candidate, rvc_result],
            outputs=[status, approval_summary],
        )
        merge_button.click(
            merge,
            inputs=[output_name],
            outputs=[final_wav, final_mp3, final_report, merge_status],
        )
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive ACE/RVC segment workbench")
    parser.add_argument("--run-dir", required=True, type=Path, help="completed segmented run directory")
    parser.add_argument("--workbench-dir", type=Path, help="session/cache directory; default RUN_DIR/workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    workbench = SegmentWorkbench(args.run_dir, args.workbench_dir)
    app = build_app(workbench)
    app.queue(default_concurrency_limit=1).launch(
        server_name=args.host,
        server_port=args.port,
        inbrowser=not args.no_browser,
        allowed_paths=[str(workbench.run_dir), str(workbench.workbench_dir)],
        show_error=True,
        theme=__import__("gradio").themes.Soft(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
