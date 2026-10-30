#!/usr/bin/env python3
"""Step B｜素材加工：放大 / 裁切 / 去白边 / 手机竖图合成卡片

用法：TV_PROJECT=/path python3 prep_assets.py [--force]

配置写在 project.json 的 assets 段：
{
  "assets": {
    "auto": true,            // assets/raw/* → assets/screenshots/*，2x 放大 + 去白边
    "target_width": 2160,
    "ops": [
      {"op": "crop",  "src": "assets/raw/02.png", "out": "assets/screenshots/phone.png",
       "box": [0, 0.03, 1, 0.31]},
      {"op": "phone", "src": "assets/raw/02.png", "out": "assets/screenshots/phone-card.png",
       "label": "第 10 步", "lines": ["微信收到文件", "选「用其他应用打开」", "小程序直接预览"]},
      {"op": "trim",  "src": "assets/raw/03.png", "out": "assets/screenshots/gesture.png"},
      {"op": "scale", "src": "x.png", "out": "y.png", "width": 2160}
    ]
  }
}
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, cfg, pil_font

from PIL import Image, ImageDraw, ImageFilter

FORCE = "--force" in sys.argv
A = cfg().get("assets", {})
SHOTS = os.path.join(PROJECT, "assets", "screenshots")
os.makedirs(SHOTS, exist_ok=True)


def abspath(p):
    return p if os.path.isabs(p) else os.path.join(PROJECT, p)


def load(path):
    try:
        im = Image.open(path)
        im.load()
    except Exception as e:
        # 公众号里偶尔有 0×0 的坏图/占位文件，不能让整条流水线挂掉
        print("   ⚠ 跳过无法识别的图：%s（%s）" % (os.path.basename(path), str(e)[:50]))
        return None
    if getattr(im, "is_animated", False):
        im.seek(0)
    return im.convert("RGB")


def trim(im, tol=6):
    """裁掉四周纯色（近白）边框。"""
    from PIL import ImageChops
    bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > tol else 0)
    box = diff.getbbox()
    return im.crop(box) if box else im


def scale_to(im, width):
    if im.width >= width:
        return im
    h = int(im.height * width / im.width)
    return im.resize((width, h), Image.LANCZOS)


def op_crop(im, box):
    """box 为相对比例 [x0,y0,x1,y1]。"""
    w, h = im.size
    x0, y0, x1, y1 = box
    return im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))


def op_phone(src, out_spec):
    """手机竖屏截图 → 「左文右机」16:9 卡片（2x 输出）。"""
    S = 2
    W = int(out_spec.get("width", 1080))
    H = int(out_spec.get("height", 608))
    accent = out_spec.get("accent", "#C7352D")
    ink = out_spec.get("ink", "#1A1614")
    grey = out_spec.get("grey", "#5a5750")
    label = out_spec.get("label", "")
    lines = out_spec.get("lines", [])

    canvas = Image.new("RGB", (W * S, H * S), "white")
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W * S, 6 * S], fill=accent)

    # 右：手机截图 + 阴影 + 圆角
    ph = int(H * 0.855) * S
    pw = int(src.width * ph / src.height)
    px = W * S - pw - int(0.122 * W) * S
    py = (H * S - ph) // 2

    pad = 30 * S
    shadow = Image.new("RGBA", (pw + pad * 2, ph + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [pad, pad + 4 * S, pad + pw, pad + ph + 4 * S], 26 * S // 2, fill=(16, 42, 67, 55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16 * S / 2))
    canvas.paste(shadow, (px - pad, py - pad), shadow)

    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw - 1, ph - 1], 13 * S, fill=255)
    canvas.paste(src.resize((pw, ph), Image.LANCZOS), (px, py), mask)
    d.rounded_rectangle([px, py, px + pw - 1, py + ph - 1], 13 * S, outline="#d4e3f5",
                        width=2 * S)

    # 左：标签 + 多行文字，整块垂直居中
    lx = int(0.089 * W) * S
    f_lab = pil_font(22 * S, False)
    f_head = pil_font(46 * S, True)
    f_body = pil_font(29 * S, False)
    rows = []
    if label:
        rows.append((label, f_lab, accent, 22))
    for i, t in enumerate(lines):
        rows.append((t, f_head if i == 0 else f_body,
                     ink if i == 0 else grey, 56 if i == 0 else 44))

    gap = 16 * S
    total = sum(r[3] * S for r in rows) + gap * (len(rows) - 1)
    y = (H * S - total) // 2
    for text, fnt, col, hh in rows:
        d.text((lx, y), text, font=fnt, fill=col)
        y += hh * S + gap

    return canvas


def save(im, out_path):
    p = abspath(out_path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    im.save(p, quality=95)
    return p


def main():
    done = []

    if A.get("auto", True):
        target = int(A.get("target_width", 2160))
        do_trim = A.get("trim_white", True)
        for f in sorted(glob.glob(os.path.join(PROJECT, "assets", "raw", "*"))):
            if not os.path.isfile(f) or f.lower().endswith(".json"):
                continue
            name = os.path.splitext(os.path.basename(f))[0] + ".png"
            out = os.path.join(SHOTS, name)
            if os.path.exists(out) and not FORCE:
                continue
            im = load(f)
            if im is None:
                continue
            if do_trim:
                im = trim(im)
            im = scale_to(im, target)
            done.append(save(im, out))
            print("  [auto] %-22s %dx%d" % (name, im.width, im.height))

    for i, op in enumerate(A.get("ops", []), 1):
        kind = op.get("op", "scale")
        src_p = abspath(op["src"])
        out_p = abspath(op["out"])
        if not os.path.exists(src_p):
            print("  ⚠ ops#%d 源文件不存在：%s" % (i, op["src"]))
            continue
        if os.path.exists(out_p) and not FORCE:
            print("  [skip] %s" % op["out"])
            continue

        im = load(src_p)
        if im is None:
            continue
        if kind == "crop":
            im = op_crop(im, op.get("box", [0, 0, 1, 1]))
        elif kind == "trim":
            im = trim(im)
        elif kind == "phone":
            im = op_phone(im, op)
        elif kind == "scale":
            im = scale_to(im, int(op.get("width", 2160)))
        else:
            print("  ⚠ 未知 op：%s" % kind)
            continue
        done.append(save(im, out_p))
        print("  [%s] %-22s %dx%d" % (kind, op["out"], im.width, im.height))

    print("\n✅ 素材 %d 个 → %s" % (len(done), os.path.relpath(SHOTS, PROJECT)))
    if not done:
        print("   （没有新素材；加 --force 强制重做）")


if __name__ == "__main__":
    main()
