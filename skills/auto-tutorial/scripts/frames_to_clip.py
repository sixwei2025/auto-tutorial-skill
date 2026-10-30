#!/usr/bin/env python3
"""把一串真实截图（CUA 操作后逐张 screencapture 下来的）拼成 mp4。

用途：computer use 驱动真实界面时，「系统录屏」经常抓不到前台窗口，
但「每做一步截一张」一定拿得到。这套脚本把那批截图变成可用的动效素材。

用法：
  TV_PROJECT=/path python3 frames_to_clip.py --dir .cua/frames --name step1 --fps 3
  TV_PROJECT=/path python3 frames_to_clip.py --dir .cua/frames --name step1 --fps 3 --crop 0,380,2940,1532
  TV_PROJECT=/path python3 frames_to_clip.py --dir .cua/frames --name step1 --hold 1.2   # 每张停留 1.2s
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, ffmpeg

def opt(k, d=None):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d


SRC = os.path.abspath(opt("--dir", os.path.join(PROJECT, ".cua", "frames")))
NAME = opt("--name", "cua")
FPS = float(opt("--fps", "2"))
HOLD = opt("--hold")
CROP = opt("--crop")
W, H = opt("--size", "1200x676").split("x")

OUT_DIR = os.path.join(PROJECT, "clips")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "%s.mp4" % NAME)

imgs = sorted(f for f in os.listdir(SRC) if f.lower().endswith((".png", ".jpg", ".jpeg")))
if len(imgs) < 2:
    raise SystemExit("❌ %s 里只有 %d 张图，至少要 2 张" % (SRC, len(imgs)))

# 用 concat demuxer：每张图按 fps 停留，尺寸不一致也能各自缩放
listf = os.path.join(SRC, "_concat.txt")
with open(listf, "w", encoding="utf-8") as fh:
    dur = float(HOLD) if HOLD else 1.0 / FPS
    for f in imgs:
        p = os.path.join(SRC, f).replace("'", "'\\''")
        fh.write("file '%s'\nduration %.3f\n" % (p, dur))
    fh.write("file '%s'\n" % os.path.join(SRC, imgs[-1]).replace("'", "'\\''"))

vf = []
if CROP:
    x0, y0, x1, y1 = [int(v) for v in CROP.split(",")]
    vf.append("crop=%d:%d:%d:%d" % (x1 - x0, y1 - y0, x0, y0))
vf.append("scale=%s:%s:force_original_aspect_ratio=decrease" % (W, H))
vf.append("pad=%s:%s:(ow-iw)/2:(oh-ih)/2:color=0xF6F4F1" % (W, H))
vf.append("format=yuv420p")

cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
       "-f", "concat", "-safe", "0", "-i", listf,
       "-vf", ",".join(vf), "-r", "30",
       "-c:v", "libx264", "-preset", "medium", "-crf", "19", OUT]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-900:])
    raise SystemExit("合成失败")

dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", OUT], capture_output=True, text=True).stdout.strip()
print("✅ clips/%s.mp4  %d 张 → %ss" % (NAME, len(imgs), dur))
print('   用：scene 上加 "clip": {"file": "clips/%s.mp4"}，跑 --from frames' % NAME)
