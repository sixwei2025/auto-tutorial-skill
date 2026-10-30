#!/usr/bin/env python3
"""逐帧渲染：Playwright seek + 截图 → frames/"""
import json, os, sys, time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import launch_browser
from playwright.sync_api import sync_playwright

PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
d = json.load(open(os.path.join(PROJECT, "sop.json")))
FPS = d["canvas"]["fps"]
OUT = os.path.join(PROJECT, "frames")

total_dur = sum(st["duration"] for st in d["steps"])
total_frames = int(total_dur * FPS)

# 旧帧处理：**不自动删**（批量删文件会被安全钩子拦，还会中断渲染）。
# 真正防「片尾重复 + 静音留白」的是 render_mux.py 里按 sop.json 锁死帧数，
# 多出来的旧帧编号都在尾部，会被 -frames:v 直接忽略。
# 想彻底清干净：设 TV_PRUNE_FRAMES=1 再跑一次，或自己删 frames/ 目录。
if os.path.isdir(OUT):
    _stale = len([f for f in os.listdir(OUT) if f.endswith(".jpg")])
else:
    _stale = 0
os.makedirs(OUT, exist_ok=True)

if _stale > total_frames:
    print("  ⚠ frames/ 里还有 %d 张旧帧（本片只需 %d 张）。mux 会按帧数截断，不影响成片；"
          "要清理请设 TV_PRUNE_FRAMES=1" % (_stale, total_frames))
    if os.environ.get("TV_PRUNE_FRAMES") == "1":
        for _f in [f for f in os.listdir(OUT) if f.endswith(".jpg")]:
            os.remove(os.path.join(OUT, _f))
        print("  🧹 已按 TV_PRUNE_FRAMES=1 清空旧帧")

url = "file://" + os.path.join(PROJECT, "render.html")

t0 = time.time()
with sync_playwright() as p:
    b = launch_browser(p)
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.goto(url)
    pg.wait_for_function("window.READY === true", timeout=30000)
    pg.wait_for_timeout(800)

    for f in range(total_frames):
        t = f / FPS
        pg.evaluate("t => window.renderAt(t)", t)
        pg.screenshot(path=os.path.join(OUT, f"{f:05d}.jpg"), type="jpeg", quality=93)
        if f % 300 == 0:
            el = time.time() - t0
            eta = el / (f + 1) * (total_frames - f - 1)
            print(f"  frame {f}/{total_frames}  {el:.0f}s  ETA {eta:.0f}s", flush=True)
    b.close()

print(f"\n✅ {total_frames} 帧 → frames/  总耗时 {time.time()-t0:.0f}s")
