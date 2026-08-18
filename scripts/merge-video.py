#!/usr/bin/env python3
"""视频合并 + 配音对齐（阶段 3 第 ③ 项：ffmpeg 合并脚本）。

按 LESSONS H1-H6 + N13 沉淀的链路：
  逐镜视频裁尾对齐旁白(H3) → 拼接视频 → 拼接旁白音频 → 混音(H6, amix normalize=0 防减半 N13)

用法：
  python merge-video.py --project <项目目录> [--shots shot-001,shot-002] [--out final.mp4]

约定：
  - 项目目录含 05-video/shot-NNN.mp4（Flow 已生成的镜头）
  - 逐镜旁白在 .work/audio-takes/shot-NNN.wav（synthesize-narration 产物）
  - 每镜权威时长 = 旁白音频 ffprobe 实测时长（与 design.json duration_seconds 一致）
  - 只合并「已存在视频」的镜头，按 shot 序号升序；缺视频的镜自动跳过（支持试点只生成部分镜）

时长统计（第 0 轮，2026-08-17）：合并时自动记录每镜「建议档位 vs Flow 实际成片时长」
到 .work/flow-duration-log.json——D1 矛盾（8s 档 7.23s vs 4/6/8/10 档整秒）未解前，
差值算术以实测为准，每期积累统计。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SHOT_RE = re.compile(r"^shot-(\d+)\.mp4$")
FLOW_SLOTS = (4, 6, 8, 10)


def flow_slot(seconds: float) -> int:
    """建议档位：与 voxvideo/handoff.py 口径一致（就近吸附，分界 5/7/9）。

    硬规律：自然时长 ≥ 3 秒时 |差值（档位 − 实测）| ≤ 1.0 秒；<3s 为短镜取 4 秒地板。
    """
    if seconds < 3.0:
        return 4
    return min(FLOW_SLOTS, key=lambda c: (abs(c - seconds), c))


def ffmpeg() -> str:
    import shutil
    p = shutil.which("ffmpeg")
    if p:
        return p
    candidates = [
        r"C:\Users\xx\ffmpeg\ffmpeg-8.1.2-essentials_build\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    raise RuntimeError("找不到 ffmpeg，请安装并加入 PATH")


def ffprobe() -> str:
    import shutil
    p = shutil.which("ffprobe")
    if p:
        return p
    candidates = [
        r"C:\Users\xx\ffmpeg\ffmpeg-8.1.2-essentials_build\bin\ffprobe.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    raise RuntimeError("找不到 ffprobe，请安装并加入 PATH")


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd)}\n{r.stderr[-2000:]}")


def probe_duration(path: Path) -> float:
    """ffprobe 取时长（秒）。"""
    r = subprocess.run(
        [ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return float(r.stdout.strip())


def has_audio(path: Path) -> bool:
    """探测视频是否带音轨（Flow 音效）。"""
    r = subprocess.run(
        [ffprobe(), "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.stdout.strip() == "audio"


def list_shots(video_dir: Path, shot_filter: list[str] | None) -> list[str]:
    """扫描已生成视频，返回按序号升序的 shot id 列表（如 ['shot-001','shot-002']）。"""
    found: list[tuple[int, str]] = []
    for p in video_dir.glob("shot-*.mp4"):
        m = SHOT_RE.match(p.name)
        if m:
            found.append((int(m.group(1)), p.name[: -len(".mp4")]))
    found.sort()
    ids = [sid for _, sid in found]
    if shot_filter:
        ids = [sid for sid in ids if sid in shot_filter]
    return ids


def trim_video(video: Path, target: float, out: Path) -> None:
    """裁尾对齐旁白时长（H3）：-t 裁前段，统一重编码便于 concat。"""
    cmd = [ffmpeg(), "-y", "-i", str(video), "-t", f"{target:.3f}",
           "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-r", "30",
           "-pix_fmt", "yuv420p"]
    if has_audio(video):
        cmd += ["-c:a", "aac", "-ar", "44100", "-ac", "2"]
    else:
        cmd += ["-an"]
    cmd += [str(out)]
    run(cmd)


def concat_demuxer(files: list[Path], out: Path) -> None:
    """concat demuxer 拼接（-c copy，要求片段编码一致——trim 时已统一）。"""
    list_file = out.with_suffix(".concat.txt")
    lines = [f"file '{p.as_posix()}'" for p in files]
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(out)])
    list_file.unlink(missing_ok=True)


def concat_audio(files: list[Path], out: Path) -> None:
    """拼接逐镜旁白 wav（narration.list.txt 同款做法）。"""
    concat_demuxer(files, out)


def mix(final_video: Path, narration: Path, out: Path,
        bgm_gain: float, nar_gain: float) -> None:
    """混音（H6）：视频音效原声 + 旁白，amix normalize=0（N13 防减半）。

    视频流直接 -map 0:v 复制（不过 filtergraph，避免 streamcopy 与 filter 冲突）；
    只有音频过 filtergraph 混音。
    """
    fc = (f"[0:a]volume={bgm_gain}[bgm];"
          f"[1:a]volume={nar_gain}[nar];"
          f"[bgm][nar]amix=inputs=2:duration=first:normalize=0[aout]")
    run([ffmpeg(), "-y", "-i", str(final_video), "-i", str(narration),
         "-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac", "-ar", "44100", str(out)])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="merge-video")
    ap.add_argument("--project", required=True, help="项目目录（含 05-video 与 .work/audio-takes）")
    ap.add_argument("--shots", default="", help="逗号分隔的镜头 id（shot-001,shot-002）；默认全部已生成")
    ap.add_argument("--out", default="final.mp4", help="输出文件名（写在 05-video/ 下）")
    ap.add_argument("--bgm-gain", type=float, default=0.6, help="视频音效增益（默认 0.6，H6）")
    ap.add_argument("--nar-gain", type=float, default=1.5, help="旁白增益（默认 1.5，H6）")
    args = ap.parse_args(argv)

    root = Path(args.project)
    video_dir = root / "05-video"
    audio_dir = root / ".work" / "audio-takes"
    design_path = root / ".work" / "design.json"
    if not video_dir.is_dir():
        print(f"[错误] 项目目录无 05-video：{video_dir}")
        return 1

    shot_filter = [s.strip() for s in args.shots.split(",") if s.strip()] or None
    shot_ids = list_shots(video_dir, shot_filter)
    if not shot_ids:
        print("[错误] 05-video 下没有已生成的 shot-*.mp4")
        return 1

    # 每镜旁白时长（ffprobe 实测）；缺失音频时 fallback design.json（shots 列表顺序 = shot 序号）
    durations: dict[str, float] = {}
    if design_path.exists():
        d = json.loads(design_path.read_text(encoding="utf-8"))
        for i, s in enumerate(d.get("shots", []), start=1):
            if isinstance(s, dict) and "duration_seconds" in s:
                durations[f"shot-{i:03d}"] = s["duration_seconds"]

    print(f"[合并] 镜头 {len(shot_ids)} 个：{', '.join(shot_ids)}")
    # 时长统计（第 0 轮）：档位 vs Flow 实际成片时长，累积到 .work/flow-duration-log.json
    log_path = root / ".work" / "flow-duration-log.json"
    if log_path.exists():
        try:
            log_data = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log_data = {"shots": {}, "note": "档位 vs 实测（D1 矛盾统计，2026-08-17 起）"}
    else:
        log_data = {"shots": {}, "note": "档位 vs 实测（D1 矛盾统计，2026-08-17 起）"}
    stats_rows: list[str] = []
    with tempfile.TemporaryDirectory(prefix="merge-video-") as td:
        tmp = Path(td)
        trim_videos: list[Path] = []
        narr_files: list[Path] = []
        for sid in shot_ids:
            video = video_dir / f"{sid}.mp4"
            wav = audio_dir / f"{sid}.wav"
            if not video.exists():
                continue
            if wav.exists():
                target = probe_duration(wav)
            elif sid in durations:
                target = durations[sid]
            else:
                print(f"[跳过] {sid}：无旁白 wav 且 design.json 无时长")
                continue
            actual = probe_duration(video)
            log_data["shots"][sid] = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "slot_advice": flow_slot(target),
                "narration": round(target, 3),
                "actual": round(actual, 3),
                "delta_actual_vs_narration": round(actual - target, 3),
                "shortfall": actual < target,
            }
            stats_rows.append(f"[时长统计] {sid}: 档位建议 {flow_slot(target)}s, "
                              f"旁白 {target:.2f}s, 实测 {actual:.2f}s, 差值 {actual - target:+.2f}s")
            if actual < target:
                print(f"[补差警告] {sid}: 视频 {actual:.2f}s 短于旁白 {target:.2f}s"
                      f"（短 {target - actual:.2f}s）——裁尾无法补足，"
                      f"需末帧定格延长或重新生成更长档；该镜差值走补差")
            vt = tmp / f"{sid}-trim.mp4"
            trim_video(video, target, vt)
            trim_videos.append(vt)
            if wav.exists():
                narr_files.append(wav)
            print(f"[裁尾] {sid} -> {target:.2f}s")
        for row in stats_rows:
            print(row)
        if stats_rows:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2),
                                encoding="utf-8")
            print(f"[时长统计] 已记录 -> {log_path}")

        if not trim_videos:
            print("[错误] 没有可合并的镜头")
            return 1

        merged_video = tmp / "merged-video.mp4"
        concat_demuxer(trim_videos, merged_video)
        print(f"[拼接] 视频 {len(trim_videos)} 段 -> merged-video.mp4")

        out = video_dir / args.out
        if narr_files:
            merged_narr = tmp / "merged-narration.wav"
            concat_audio(narr_files, merged_narr)
            print(f"[拼接] 旁白 {len(narr_files)} 段 -> merged-narration.wav")
            if has_audio(merged_video):
                mix(merged_video, merged_narr, out, args.bgm_gain, args.nar_gain)
                print(f"[混音] 视频音效 {args.bgm_gain} + 旁白 {args.nar_gain} -> {out}")
            else:
                run([ffmpeg(), "-y", "-i", str(merged_video), "-i", str(merged_narr),
                     "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                     "-ar", "44100", str(out)])
                print(f"[贴旁白] 视频无音轨，直接贴旁白 -> {out}")
        else:
            merged_video.replace(out)
            print(f"[无旁白] 直接输出视频 -> {out}")

    final_dur = probe_duration(out)
    print(f"[完成] {out}（{final_dur:.2f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
