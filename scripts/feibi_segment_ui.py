#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
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
    generation_jobs: dict[str, dict[str, Any]] = {}
    ace_jobs: dict[str, dict[str, Any]] = {}
    rvc_jobs: dict[str, dict[str, Any]] = {}
    generation_lock = threading.Lock()

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

    def _write_generation_status(output_dir: Path, status: str, **extra: Any) -> None:
        payload = {"status": status, "updated_at": time.time(), **extra}
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "pipeline_status.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _run_generation(job_key: str, cmd: list[str], output_dir: Path) -> None:
        log_path = output_dir / "pipeline.log"
        try:
            _write_generation_status(output_dir, "starting", command=cmd)
            with log_path.open("w", encoding="utf-8", errors="replace") as log:
                log.write("$ " + subprocess.list2cmdline(cmd) + "\n\n")
                log.flush()
                process = subprocess.Popen(
                    cmd, cwd=str(Path(__file__).parents[1]), stdout=log, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace"
                )
                with generation_lock:
                    generation_jobs[job_key].update({"process": process, "status": "running", "started_at": time.time()})
                _write_generation_status(output_dir, "running", pid=process.pid, log=str(log_path))
                returncode = process.wait()
            if returncode != 0:
                _write_generation_status(output_dir, "failed", returncode=returncode, log=str(log_path))
                with generation_lock:
                    generation_jobs[job_key].update({"status": "failed", "returncode": returncode})
                return
            if not (output_dir / "report.json").exists():
                raise WorkbenchError("pipeline exited successfully but report.json is missing")
            _write_generation_status(output_dir, "completed", returncode=0, log=str(log_path))
            with generation_lock:
                generation_jobs[job_key].update({"status": "completed", "returncode": 0})
        except Exception as exc:
            message = str(exc)
            _write_generation_status(output_dir, "failed", error=message, log=str(log_path))
            with generation_lock:
                generation_jobs[job_key].update({"status": "failed", "error": message})

    def _generation_result(job_key: str):
        with generation_lock:
            job = generation_jobs.get(job_key)
        if not job:
            return tuple([gr.update()] * 21)
        status = job.get("status", "starting")
        if status not in {"completed", "failed"}:
            message = f"\u6b63\u5728\u751f\u6210\uff1a{job['output_dir']}\uff08\u65e5\u5fd7\uff1a{job['output_dir']}\\pipeline.log\uff09"
            return tuple([gr.update()] * 19 + [message, gr.update(value="\u751f\u6210\u4e2d\u2026", interactive=False)])
        if status == "failed":
            detail = job.get("error") or f"\u9000\u51fa\u7801 {job.get('returncode')}"
            message = f"\u4ece\u5934\u751f\u6210\u5931\u8d25\uff1a{detail}\uff1b\u65e5\u5fd7\uff1a{job['output_dir']}\\pipeline.log"
            return tuple([gr.update()] * 19 + [message, gr.update(value="\u4ece\u5934\u5f00\u59cb\u751f\u6210\u6b4c\u66f2", interactive=True)])
        output_dir = Path(job["output_dir"])
        try:
            new_wb = SegmentWorkbench(output_dir, output_dir / "workbench")
            key = _song_id(output_dir)
            sessions[key] = new_wb
            current["value"] = new_wb
            first = new_wb.segment_indices[0]
            with generation_lock:
                generation_jobs.pop(job_key, None)
            return (gr.update(choices=song_choices(), value=key),
                    gr.update(choices=new_wb.segment_indices, value=first), *segment_values(first),
                    f"\u4ece\u5934\u751f\u6210\u5b8c\u6210\uff1a{output_dir}\uff08\u65e5\u5fd7\uff1a{output_dir / 'pipeline.log'}\uff09",
                    gr.update(value="\u4ece\u5934\u5f00\u59cb\u751f\u6210\u6b4c\u66f2", interactive=True))
        except Exception as exc:
            message = f"\u751f\u6210\u5df2\u7ed3\u675f\u4f46\u65e0\u6cd5\u52a0\u8f7d\u7ed3\u679c\uff1a{exc}\uff1b\u65e5\u5fd7\uff1a{output_dir / 'pipeline.log'}"
            return tuple([gr.update()] * 19 + [message, gr.update(value="\u4ece\u5934\u5f00\u59cb\u751f\u6210\u6b4c\u66f2", interactive=True)])

    def generate_song(input_audio, lyrics_text, run_name, caption_override, seed_plan):
        def action():
            if not input_audio:
                raise WorkbenchError("\u8bf7\u5148\u9009\u62e9\u8f93\u5165\u97f3\u9891")
            name = "".join(ch for ch in (run_name or "new_song").strip() if ch.isalnum() or ch in "-_ ").strip() or "new_song"
            output_dir = workspace_dir / name
            if output_dir.exists() and any(output_dir.iterdir()):
                raise WorkbenchError(f"\u8fd0\u884c\u76ee\u5f55\u5df2\u5b58\u5728\u4e14\u975e\u7a7a\uff1a{output_dir}")
            cmd = [sys.executable, str(Path(__file__).with_name("feibi_pipeline.py")),
                   "--input", str(Path(input_audio).resolve()), "--output-dir", str(output_dir)]
            if lyrics_text and lyrics_text.strip():
                cmd += ["--lyrics-text", lyrics_text, "--no-asr-fallback"]
            if caption_override and caption_override.strip():
                cmd += ["--caption", caption_override.strip()]
            if seed_plan and seed_plan.strip():
                cmd += ["--seed-plan", seed_plan.strip()]
            key = _song_id(output_dir)
            with generation_lock:
                if any(item.get("status") in {"starting", "running"} for item in generation_jobs.values()):
                    raise WorkbenchError("\u5df2\u6709\u4ece\u5934\u751f\u6210\u4efb\u52a1\u6b63\u5728\u8fd0\u884c")
                generation_jobs[key] = {"status": "starting", "output_dir": str(output_dir)}
            threading.Thread(target=_run_generation, args=(key, cmd, output_dir), daemon=True).start()
            return (f"\u6b63\u5728\u4ece\u5934\u751f\u6210\uff1a{output_dir}\uff1b\u65e7\u8bd5\u542c\u5c06\u4fdd\u7559\uff0c\u5b8c\u6210\u540e\u81ea\u52a8\u66ff\u6362\uff08\u65e5\u5fd7\uff1a{output_dir / 'pipeline.log'}\uff09",
                    gr.update(value="\u751f\u6210\u4e2d\u2026", interactive=False))
        return safe(action)

    def poll_generation():
        with generation_lock:
            keys = list(generation_jobs)
        if not keys:
            return tuple([gr.update()] * 21)
        return _generation_result(keys[0])

    def _run_ace_generation(job_key, index, seed, caption, lyrics, voice_gain_db):
        try:
            with generation_lock: ace_jobs[job_key]["status"] = "running"
            candidate = wb().generate_ace(index, seed, caption, lyrics)
            previews = wb().ace_preview(index, candidate["id"], voice_gain_db)
            result = (gr.update(choices=wb().candidate_choices(index), value=candidate["id"]), candidate["ace_audio"], previews["with_original"], previews["generated_melody"], gr.update(choices=[], value=None), None, None, None, f"ACE \u5df2\u751f\u6210\uff1a{candidate['id']}\u3002\u8bf7\u8bd5\u542c ACE+\u539f\u65cb\u5f8b \u4e0e ACE \u751f\u6210\u65cb\u5f8b\u3002")
            with generation_lock: ace_jobs[job_key].update(status="completed", result=result)
        except Exception as exc:
            with generation_lock: ace_jobs[job_key].update(status="failed", error=str(exc))

    def generate_ace(index, seed, caption, lyrics, voice_gain_db=0.0):
        def action():
            if not lyrics or not str(lyrics).strip(): raise WorkbenchError("ACE \u9884\u8bbe\u6b4c\u8bcd\u4e0d\u80fd\u4e3a\u7a7a")
            key=f"{int(index)}:{time.time_ns()}"
            with generation_lock:
                if any(j.get("status") in {"starting","running"} for j in ace_jobs.values()): raise WorkbenchError("\u5df2\u6709 ACE \u751f\u6210\u4efb\u52a1\u6b63\u5728\u8fd0\u884c\uff0c\u8bf7\u7b49\u5f85\u5b8c\u6210")
                ace_jobs[key]={"status":"starting"}
            threading.Thread(target=_run_ace_generation,args=(key,int(index),int(seed),caption or "",lyrics or "",float(voice_gain_db)),daemon=True).start()
            return "ACE \u751f\u6210\u4e2d\u2026\u65e7\u64ad\u653e\u5668\u6682\u65f6\u4fdd\u7559\uff0c\u5b8c\u6210\u540e\u81ea\u52a8\u66ff\u6362",gr.update(value="ACE \u751f\u6210\u4e2d\u2026",interactive=False)
        return safe(action)

    def poll_ace_generation():
        with generation_lock: keys=list(ace_jobs); job=ace_jobs.get(keys[0]) if keys else None
        if not job: return tuple([gr.update()]*10)
        if job["status"] in {"starting","running"}: return tuple([gr.update()]*9+[gr.update(value="ACE \u751f\u6210\u4e2d\u2026",interactive=False)])
        if job["status"]=="failed":
            msg=f"ACE \u751f\u6210\u5931\u8d25\uff1a{job.get('error','????')}\u3002\u65e7\u64ad\u653e\u5668\u672a\u66ff\u6362\uff0c\u8bf7\u68c0\u67e5 ace_step.log"
            with generation_lock: ace_jobs.pop(keys[0],None)
            return tuple([gr.update()]*8+[msg,gr.update(value="\u91cd\u65b0\u751f\u6210 ACE",interactive=True)])
        result=job["result"]
        with generation_lock: ace_jobs.pop(keys[0],None)
        return (*result,gr.update(value="\u91cd\u65b0\u751f\u6210 ACE",interactive=True))

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

    def _run_rvc_generation(job_key, index, candidate_id, f0_change, voice_gain_db):
        try:
            with generation_lock: rvc_jobs[job_key]["status"]="running"
            result=wb().generate_rvc(index,candidate_id,f0_change)
            previews=wb().rvc_preview(index,candidate_id,result["id"],voice_gain_db)
            payload=(gr.update(choices=wb().rvc_choices(index,candidate_id),value=result["id"]),result["audio"],previews["with_original"],previews["vocal_only"],f"RVC \u5df2\u751f\u6210\uff1a\u52a8\u6001\u5347\u8c03 {result['f0_change']:+d} \u534a\u97f3")
            with generation_lock: rvc_jobs[job_key].update(status="completed",result=payload)
        except Exception as exc:
            with generation_lock: rvc_jobs[job_key].update(status="failed",error=str(exc))

    def generate_rvc(index, candidate_id, f0_change, voice_gain_db=0.0):
        def action():
            if not candidate_id: raise WorkbenchError("\u8bf7\u5148\u9009\u62e9 ACE \u5019\u9009")
            key=f"{int(index)}:{time.time_ns()}"
            with generation_lock:
                if any(j.get("status") in {"starting","running"} for j in rvc_jobs.values()): raise WorkbenchError("\u5df2\u6709 RVC \u751f\u6210\u4efb\u52a1\u6b63\u5728\u8fd0\u884c\uff0c\u8bf7\u7b49\u5f85\u5b8c\u6210")
                rvc_jobs[key]={"status":"starting"}
            threading.Thread(target=_run_rvc_generation,args=(key,int(index),candidate_id,int(f0_change),float(voice_gain_db)),daemon=True).start()
            return "RVC \u751f\u6210\u4e2d\u2026\u65e7\u64ad\u653e\u5668\u6682\u65f6\u4fdd\u7559\uff0c\u5b8c\u6210\u540e\u81ea\u52a8\u66ff\u6362",gr.update(value="RVC \u751f\u6210\u4e2d\u2026",interactive=False)
        return safe(action)

    def poll_rvc_generation():
        with generation_lock: keys=list(rvc_jobs); job=rvc_jobs.get(keys[0]) if keys else None
        if not job: return tuple([gr.update()]*6)
        if job["status"] in {"starting","running"}: return tuple([gr.update()]*5+[gr.update(value="RVC \u751f\u6210\u4e2d\u2026",interactive=False)])
        if job["status"]=="failed":
            msg=f"RVC \u751f\u6210\u5931\u8d25\uff1a{job.get('error','????')}\u3002\u65e7\u64ad\u653e\u5668\u672a\u66ff\u6362\uff0c\u8bf7\u68c0\u67e5 RVC \u65e5\u5fd7"
            with generation_lock: rvc_jobs.pop(keys[0],None)
            return tuple([gr.update()]*4+[msg,gr.update(value="\u7528\u5f53\u524d ACE \u751f\u6210 RVC",interactive=True)])
        result=job["result"]
        with generation_lock: rvc_jobs.pop(keys[0],None)
        return (*result,gr.update(value="\u7528\u5f53\u524d ACE \u751f\u6210 RVC",interactive=True))

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
        generation_timer = gr.Timer(2.0)
        ace_timer = gr.Timer(1.0)
        rvc_timer = gr.Timer(1.0)
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
        generate_song_button.click(generate_song, inputs=[input_audio, lyrics_text, run_name, caption_override, seed_plan], outputs=[song_status, generate_song_button])
        generation_timer.tick(poll_generation, outputs=[song, segment_index, *load_outputs, song_status, generate_song_button])
        generate_ace_button.click(generate_ace, inputs=[segment_index, seed, caption, lyrics, voice_gain_db], outputs=[status, generate_ace_button])
        ace_timer.tick(poll_ace_generation, outputs=[candidate, ace_audio, ace_original_audio, ace_generated_audio, rvc_result, rvc_audio, rvc_original_audio, rvc_vocal_only_audio, status, generate_ace_button])
        candidate.input(load_candidate, inputs=[segment_index, candidate, voice_gain_db], outputs=[ace_audio, ace_original_audio, ace_generated_audio, rvc_result, rvc_audio, rvc_original_audio, rvc_vocal_only_audio, status])
        generate_rvc_button.click(generate_rvc, inputs=[segment_index, candidate, f0_change, voice_gain_db], outputs=[status, generate_rvc_button])
        rvc_timer.tick(poll_rvc_generation, outputs=[rvc_result, rvc_audio, rvc_original_audio, rvc_vocal_only_audio, status, generate_rvc_button])
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

