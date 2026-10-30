#!/usr/bin/env python3
"""Step｜把静态长图做成「动态素材」（缓慢推拉 / 平移），当录屏的降级方案

优先级：真录屏 > 滚动动图 > 本脚本的推拉 > 纯静态图。
当真滚动拿不到（系统辅助功能权限没开、CUA 超时），用它让画面「活」起来。

用法：
  TV_PROJECT=/path python3 kenburns_clip.py --src assets/screenshots/x.png \
      --name x-pan --seconds 6 --zoom 1.14 [--dir down]

产出：clips/<name>.mp4（1200×675 不成比例时按比例缩放）
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, ffmpeg

args = sys.argv[1:]


def opt(flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


src = opt("--src")
name = opt("--name")
if not src or not name:
    raise SystemExit(__doc__)

seconds = float(opt("--seconds", "6"))
zoom = float(opt("--zoom", "1.14"))
direction = opt("--dir", "down")
W, H = 1200, 676      # 偶数高度，libx264 要求

src_p = src if os.path.isabs(src) else os.path.join(PROJECT, src)
out = os.path.join(PROJECT, "clips", "%s.mp4" % name)
os.makedirs(os.path.dirname(out), exist_ok=True)

# zoompan：以 30fps 生成，z 从 1 线性到 zoom，x/y 随之平移（实现缓慢推近）
frames = int(seconds * 30)
if direction == "down":
    expr_xy = "x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/%d'" % frames
elif direction == "up":
    expr_xy = "x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/%d)'" % frames
elif direction == "right":
    expr_xy = "x='(iw-iw/zoom)*on/%d':y='ih/2-(ih/zoom/2)'" % frames
else:
    expr_xy = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"

vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
      "zoompan=z='1+%f*on/%d':d=%d:%s:s=%dx%d:fps=30,format=yuv420p"
      % (W * 2, H * 2, W * 2, H * 2, zoom - 1, frames, frames, expr_xy, W, H))

cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
       "-loop", "1", "-i", src_p, "-t", "%.2f" % seconds,
       "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", "30",
       "-pix_fmt", "yuv420p", out]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-800:])
    raise SystemExit("生成失败")

print("✅ clips/%s.mp4  %.1fs  推近 %.0f%%  方向 %s" % (name, seconds, (zoom - 1) * 100, direction))
print('   在 scene 上加 "clip": {"file": "clips/%s.mp4"}，跑 --from frames' % name)
