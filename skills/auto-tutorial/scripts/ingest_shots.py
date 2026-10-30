#!/usr/bin/env python3
"""Step｜外部截图入库：把浏览器插件截的图 / 系统截屏 / 拖进来的图，统一收进项目

用途：WorkBuddy 浏览器操控插件（tab_screenshot）只返回图像内容、不落盘；
     需要登录态才能看到的页面（飞书表格、后台、平台后台）只能走「截屏 → 裁切 → 入库」这条路。

用法：
  # 单张：整屏截图裁掉浏览器 UI，再入库
  TV_PROJECT=/path python3 ingest_shots.py --src /tmp/desk.png --name feishu-top50 \
      --crop 0,380,2940,1912 --scale 2160

  # 多张：直接入库（不裁）
  TV_PROJECT=/path python3 ingest_shots.py --src a.png b.png --scale 2160

  # 自动去掉四周纯色边
  TV_PROJECT=/path python3 ingest_shots.py --src x.png --name y --trim
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT

from PIL import Image, ImageChops

args = sys.argv[1:]
if not args:
    raise SystemExit(__doc__)


def opt(flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


srcs = []
if "--src" in args:
    i = args.index("--src") + 1
    while i < len(args) and not args[i].startswith("--"):
        srcs.append(args[i])
        i += 1
if not srcs:
    raise SystemExit("至少要给一个 --src")

name = opt("--name")
crop = opt("--crop")
scale = int(opt("--scale", "0"))
trim = "--trim" in args

SHOTS = os.path.join(PROJECT, "assets", "screenshots")
os.makedirs(SHOTS, exist_ok=True)
manifest_path = os.path.join(PROJECT, "capture.json")
manifest = {"shots": [], "clips": []}
if os.path.exists(manifest_path):
    try:
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        manifest.setdefault("shots", [])
    except Exception:
        pass

done = []
for n, s in enumerate(srcs):
    if not os.path.exists(s):
        print("  ⚠ 不存在：%s" % s)
        continue
    im = Image.open(s)
    if getattr(im, "is_animated", False):
        im.seek(0)
    im = im.convert("RGB")

    if crop:
        x0, y0, x1, y1 = [int(v) for v in crop.split(",")]
        x1 = min(x1, im.width)
        y1 = min(y1, im.height)
        im = im.crop((x0, y0, x1, y1))

    if trim:
        bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
        diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 6 else 0)
        box = diff.getbbox()
        if box:
            im = im.crop(box)

    if scale and im.width < scale:
        im = im.resize((scale, int(im.height * scale / im.width)), Image.LANCZOS)

    out_name = name if name and len(srcs) == 1 else (
        "%s-%02d" % (name, n + 1) if name else os.path.splitext(os.path.basename(s))[0])
    out = os.path.join(SHOTS, out_name + ".png")
    im.save(out)
    done.append(out_name)
    print("  [ingest] %-24s %dx%d → assets/screenshots/%s.png" % (out_name, im.width, im.height, out_name))
    manifest["shots"].append({"name": out_name, "file": "assets/screenshots/%s.png" % out_name,
                              "width": im.width, "height": im.height, "source": "ingest"})

json.dump(manifest, open(manifest_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n✅ 入库 %d 张。在 project.json 里把 scenes[].shot 指到 assets/screenshots/<名字>.png 即可。" % len(done))
