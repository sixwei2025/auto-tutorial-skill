#!/usr/bin/env python3
"""从成片里截一帧 → 裁成 3:4 → 放大撑满，直接当封面用。

用途：不想单独设计封面时，用真实画面裁一张满幅 3:4，四边天然不会有白边。

用法：
  TV_PROJECT=/path python3 cover_from_frame.py --time 2.0
  TV_PROJECT=/path python3 cover_from_frame.py --time 12 --bias 0.35 --out cover/cover-frame.jpg
  TV_PROJECT=/path python3 cover_from_frame.py --video delivery/x.mp4 --time 0.3 --size 2160x2880

--bias 是横向取景重心：0=最左，0.5=居中，1=最右（默认 0.5）
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, cfg, ffmpeg


def opt(k, d=None):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d


SLUG = cfg().get("slug", "video")
VIDEO = opt("--video") or os.path.join(PROJECT, "delivery", "%s-16x9.mp4" % SLUG)
TIME = float(opt("--time", "2.0"))
BIAS = float(opt("--bias", "0.5"))
SIZE = opt("--size", "2160x2880")
OUT = opt("--out") or os.path.join(PROJECT, "cover", "cover-3x4.jpg")

if not os.path.exists(VIDEO):
    raise SystemExit("❌ 找不到成片：%s" % VIDEO)

tmp = os.path.join(PROJECT, "cover", "_frame.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

r = subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(TIME), "-i", VIDEO, "-frames:v", "1", tmp],
                   capture_output=True, text=True)
if r.returncode != 0:
    raise SystemExit("抽帧失败：%s" % r.stderr[-400:])

from PIL import Image, ImageFilter

im = Image.open(tmp).convert("RGB")
W, H = im.size
tw, th = [int(v) for v in SIZE.split("x")]

# 3:4 取景：以画幅高度为准，宽度 = 高 * 3/4
cw = int(round(H * 3 / 4))
cw = min(cw, W)
x0 = int(round((W - cw) * BIAS))
x0 = max(0, min(W - cw, x0))
box = im.crop((x0, 0, x0 + cw, H))

# 放大撑满（Lanczos + 轻微锐化，抵消放大变软）
big = box.resize((tw, th), Image.LANCZOS)
big = big.filter(ImageFilter.UnsharpMask(radius=2.2, percent=115, threshold=2))
big.save(OUT, quality=94, subsampling=0)
png = os.path.splitext(OUT)[0] + ".png"
big.save(png)

os.remove(tmp) if os.path.exists(tmp) else None

# ---------------------------------------------------------------- 叠字（可选）
TEXT = opt("--text")        # "第一行|第二行"
SUB = opt("--sub")          # 副标
SCRIM = float(opt("--scrim", "0"))   # 0~0.85，红色蒙层，让字压得住画面
TONE = opt("--tone", "#C7352D")

if TEXT and SCRIM > 0:
    from PIL import ImageDraw, ImageFont

    r_, g_, b_ = [int(TONE[i:i + 2], 16) for i in (1, 3, 5)]
    layer = Image.new("RGB", big.size, (r_, g_, b_))
    big = Image.blend(big, layer, SCRIM)

    d = ImageDraw.Draw(big)
    lines = [t for t in TEXT.split("|") if t]

    def font(sz, bold=True):
        for path, idx in (("/System/Library/Fonts/PingFang.ttc", 4 if bold else 2),
                          ("/System/Library/Fonts/STHeiti Medium.ttc", 0)):
            try:
                return ImageFont.truetype(path, sz, index=idx)
            except Exception:
                continue
        return ImageFont.load_default()

    pad = int(tw * 0.062)
    size = int(tw * 0.185)
    y = int(th * 0.30)
    for i, ln in enumerate(lines):
        f = font(size)
        while d.textlength(ln, font=f) > tw - pad * 2 and size > int(tw * 0.07):
            size -= 4
            f = font(size)
        # 轻微描边，压在画面上更清楚
        d.text((pad, y), ln, font=f, fill="#FFF6F0",
               stroke_width=max(2, size // 26), stroke_fill="#8E2018")
        y += int(size * 1.04)
        size = int(tw * 0.145) if i == 0 else size

    if SUB:
        fs = int(tw * 0.058)
        f = font(fs)
        d.text((pad, y + int(th * 0.02)), SUB, font=f, fill="#FFF6F0",
               stroke_width=3, stroke_fill="#8E2018")

    big.save(OUT, quality=94, subsampling=0)
    big.save(os.path.splitext(OUT)[0] + ".png")
    print("   已叠字：%s" % " / ".join(lines))

print("✅ %s  %dx%d（取自 %.2fs，横向重心 %.2f，裁切宽 %d/%d）"
      % (os.path.relpath(OUT, PROJECT), tw, th, TIME, BIAS, cw, W))
