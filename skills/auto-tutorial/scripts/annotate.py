#!/usr/bin/env python3
"""Step｜截图标注：给任意截图画线框、编号、标签，用来「圈出重点」

用法：TV_PROJECT=/path python3 annotate.py [--force]

配置写在 project.json 的 annotations 段（键是源图路径，比例坐标 0–1）：
{
  "annotations": {
    "assets/raw/01.png": {
      "out": "assets/screenshots/settings-annotated.png",
      "color": "#C7352D", "width": 6, "radius": 18,
      "boxes": [
        {"box": [0.017, 0.568, 0.142, 0.609], "badge": "1"},
        {"box": [0.256, 0.495, 0.973, 0.940], "badge": "2", "label": "浏览器操控"}
      ],
      "arrow": {"from": [0.10, 0.60], "to": [0.40, 0.52]}
    }
  }
}
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, cfg, pil_font

from PIL import Image, ImageDraw

FORCE = "--force" in sys.argv
A = cfg().get("annotations", {})

if not A:
    print("没有 annotations 配置，跳过")
    raise SystemExit(0)


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


done = 0
for src, spec in A.items():
    src_p = src if os.path.isabs(src) else os.path.join(PROJECT, src)
    out = spec.get("out") or "assets/screenshots/%s-annotated.png" % os.path.splitext(
        os.path.basename(src))[0]
    out_p = out if os.path.isabs(out) else os.path.join(PROJECT, out)

    if not os.path.exists(src_p):
        print("  ⚠ 源图不存在：%s" % src)
        continue
    if os.path.exists(out_p) and not FORCE:
        print("  [skip] %s" % out)
        continue

    im = Image.open(src_p)
    if getattr(im, "is_animated", False):
        im.seek(0)
    im = im.convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    color = hex2rgb(spec.get("color", "#C7352D"))
    lw = max(2, int(spec.get("width", 6) * W / 1764))
    rad = int(spec.get("radius", 18) * W / 1764)

    for b in spec.get("boxes", []):
        x0, y0, x1, y1 = b["box"]
        d.rounded_rectangle([x0 * W, y0 * H, x1 * W, y1 * H],
                            radius=rad, outline=color, width=lw)
        if b.get("badge"):
            bh = (y1 - y0) * H
            r = int(min(13 * W / 1764 * 1.6, bh * 0.36))     # 细框就把徽标缩小
            if bh < max(72, r * 3.0):
                # 细框（圈一行字）：徽标放到框左外侧，避免压住第一个字
                cx, cy = x0 * W - r * 0.9, (y0 + y1) / 2 * H
            else:
                cx, cy = x0 * W + r * 0.45, y0 * H + r * 0.45  # 框内左上角
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
            f = pil_font(int(r * 1.25), True)
            tb = d.textbbox((0, 0), b["badge"], font=f)
            d.text((cx - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2 - tb[1]),
                   b["badge"], font=f, fill="white")
        if b.get("label"):
            f = pil_font(int(20 * W / 1764 * 1.6), True)
            tx, ty = x1 * W, y0 * H
            tb = d.textbbox((0, 0), b["label"], font=f)
            pad = int(8 * W / 1764 * 1.6)
            d.rounded_rectangle([tx - tb[2] - pad * 2, ty - pad,
                                 tx, ty + (tb[3] - tb[1]) + pad],
                                radius=int(6 * W / 1764 * 1.6), fill=color)
            d.text((tx - tb[2] - pad, ty), b["label"], font=f, fill="white")

    ar = spec.get("arrow")
    if ar:
        (ax, ay), (bx, by) = ar["from"], ar["to"]
        d.line([ax * W, ay * H, bx * W, by * H], fill=color, width=lw)
        import math
        ang = math.atan2((by - ay) * H, (bx - ax) * W)
        L = 26 * W / 1764 * 1.6
        for s in (0.5, -0.5):
            d.line([bx * W, by * H,
                    bx * W - L * math.cos(ang - s), by * H - L * math.sin(ang - s)],
                   fill=color, width=lw)

    os.makedirs(os.path.dirname(out_p), exist_ok=True)
    im.save(out_p)
    done += 1
    print("  [anno] %-34s %dx%d  %d 个框" % (out, W, H, len(spec.get("boxes", []))))

print("\n✅ 标注图 %d 张" % done)
