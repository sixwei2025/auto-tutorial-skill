#!/usr/bin/env python3
"""Step E｜把 clip（轻录屏/动图）嵌进已渲染的帧里

用法：TV_PROJECT=/path python3 patch_frames.py

配置：scene 上加一个 clip 字段即可
{
  "id": "scroll",
  "shot": "assets/captured/01-home.png",
  "clip": {"file": "clips/scroll-demo.mp4", "fit": "cover"},
  ...
}

原理：不动整体版式，只把 clip 的每一帧缩放到左侧「画面区」(80,180,1200,675) 里，
贴在已渲染帧的同一位置 —— 标题、右侧面板、字幕、进度条全部保持原样。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, cfg, ffmpeg, ffprobe

from PIL import Image

# 与 make_render_html.py 保持一致
VX, VY, VW, VH = 80, 180, 1200, 675
FRAMES = os.path.join(PROJECT, "frames")

sop = json.load(open(os.path.join(PROJECT, "sop.json"), encoding="utf-8"))
C = cfg()
FPS = int(C.get("canvas", {}).get("fps", 30))
SCENES = {s["id"]: s for s in C.get("scenes", [])}

# 时间轴：scene → 起止帧
cursor = 0.0
ranges = {}
for st in sop["steps"]:
    start = cursor
    cursor += st["duration"]
    if st["id"] in SCENES and SCENES[st["id"]].get("clip"):
        ranges[st["id"]] = (round(start * FPS), round(cursor * FPS), SCENES[st["id"]]["clip"])

if not ranges:
    print("没有场景配置 clip，跳过")
    raise SystemExit(0)

tmp = tempfile.mkdtemp(prefix="clip_")
patched = 0

for sid, (f0, f1, clip) in ranges.items():
    src = clip.get("file", "") if isinstance(clip, dict) else clip
    src_path = src if os.path.isabs(src) else os.path.join(PROJECT, src)
    if not os.path.exists(src_path):
        print("⚠ %s 的 clip 不存在：%s" % (sid, src))
        continue

    n = f1 - f0
    clip_dur = float(subprocess.run([ffprobe(), "-v", "error", "-show_entries",
                                     "format=duration", "-of", "csv=p=0", src_path],
                                    capture_output=True, text=True).stdout.strip() or 0)
    print("▶ %-12s 帧 %d-%d（%d 帧 / %.2fs）← %s"
          % (sid, f0, f1, n, clip_dur, os.path.basename(src_path)))

    # clip → n 帧（不够就按 duration 循环，多了就截断）
    odir = os.path.join(tmp, sid)
    os.makedirs(odir, exist_ok=True)
    subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                    "-stream_loop", "-1", "-i", src_path,
                    "-t", "%.3f" % (n / FPS),
                    "-vf", "fps=%d,scale=%d:%d:flags=lanczos" % (FPS, VW * 2, VH * 2),
                    "-q:v", "2", os.path.join(odir, "%05d.jpg")],
                   check=True, capture_output=True)

    files = sorted(os.listdir(odir))
    if not files:
        print("  ⚠ 抽帧失败")
        continue

    fit = (clip or {}).get("fit", "cover") if isinstance(clip, dict) else "cover"
    pasted = 0
    for i in range(n):
        fpath = os.path.join(FRAMES, "%05d.jpg" % (f0 + i + 1))
        if not os.path.exists(fpath):
            continue
        cf = os.path.join(odir, files[i % len(files)])
        base = Image.open(fpath).convert("RGB")
        cimg = Image.open(cf).convert("RGB")

        if fit == "cover":                       # 铺满，超出裁掉
            ratio = max(VW / cimg.width, VH / cimg.height)
            nw, nh = int(cimg.width * ratio), int(cimg.height * ratio)
            cimg = cimg.resize((nw, nh), Image.LANCZOS)
            left, top = (nw - VW) // 2, (nh - VH) // 2
            cimg = cimg.crop((left, top, left + VW, top + VH))
        else:                                    # contain，留白
            ratio = min(VW / cimg.width, VH / cimg.height)
            nw, nh = int(cimg.width * ratio), int(cimg.height * ratio)
            cimg = cimg.resize((nw, nh), Image.LANCZOS)
            canvas = Image.new("RGB", (VW, VH), "#FAF6F4")
            canvas.paste(cimg, ((VW - nw) // 2, (VH - nh) // 2))
            cimg = canvas

        base.paste(cimg, (VX, VY))
        base.save(fpath, quality=92)
        pasted += 1

    patched += pasted
    print("  ✓ 替换 %d 帧" % pasted)

shutil.rmtree(tmp, ignore_errors=True)
print("\n✅ 共替换 %d 帧。重跑 mux 即可看到动图效果。" % patched)
