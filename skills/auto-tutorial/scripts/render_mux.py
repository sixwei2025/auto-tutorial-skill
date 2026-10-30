#!/usr/bin/env python3
"""Step｜合成成片：帧序列 + 音轨 → MP4，再嵌入章节（跨平台，不依赖 bash）

用法：TV_PROJECT=/path python3 render_mux.py
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, cfg, ffmpeg, ffprobe

SLUG = cfg().get("slug", "video")
FPS = int(cfg().get("canvas", {}).get("fps", 30))
SRC = os.path.join(PROJECT, "frames", "%05d.jpg")
AUDIO = os.path.join(PROJECT, "voice", "full.wav")
CHAPTERS = os.path.join(PROJECT, "delivery", "chapters.ffmetadata")
OUT = os.path.join(PROJECT, "renders", "%s-16x9.mp4" % SLUG)
FINAL = os.path.join(PROJECT, "delivery", "%s-16x9.mp4" % SLUG)

os.makedirs(os.path.join(PROJECT, "renders"), exist_ok=True)
os.makedirs(os.path.join(PROJECT, "delivery"), exist_ok=True)


def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1600:])
        raise SystemExit("❌ %s 失败" % label)
    return r


print("▶ 1/2 合成视频 + 音轨")

# 按 sop.json 的时间轴锁死帧数，不依赖「音轨多长」或「目录里剩多少帧」。
# 少这一道，任何残留帧都会变成片尾的重复画面 + 静音留白。
_total_frames = None
try:
    _sop = json.load(open(os.path.join(PROJECT, "sop.json"), encoding="utf-8"))
    _dur = sum(s["duration"] for s in _sop["steps"])
    _total_frames = int(round(_dur * FPS))
    print("   时间轴 %.2fs → 锁定 %d 帧（%.2fs）" % (_dur, _total_frames, _total_frames / FPS))
except Exception as e:
    print("   ⚠ 读不到 sop.json 时间轴，退回 -shortest：%s" % e)

_cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "warning",
        "-framerate", str(FPS), "-i", SRC, "-i", AUDIO,
        "-vf", "format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
if _total_frames:
    _cmd += ["-frames:v", str(_total_frames)]
_cmd += ["-shortest", "-movflags", "+faststart", OUT]
run(_cmd, "视频合成")

if os.path.exists(CHAPTERS):
    print("▶ 2/2 嵌入章节")
    run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "warning",
         "-i", OUT, "-i", CHAPTERS,
         "-map", "0", "-map_metadata", "1", "-c", "copy",
         "-movflags", "+faststart", FINAL], "章节嵌入")
else:
    print("⚠ 无章节文件，输出未嵌章节版本")
    shutil.copy2(OUT, FINAL)

info = subprocess.run([ffprobe(), "-v", "error", "-show_entries", "format=duration,size",
                       "-show_entries", "stream=codec_name,width,height",
                       "-of", "default=noprint_wrappers=1", FINAL],
                      capture_output=True, text=True).stdout.strip()
print(info)
print("✅ %s" % FINAL)
