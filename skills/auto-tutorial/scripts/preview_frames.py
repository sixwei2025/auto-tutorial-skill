#!/usr/bin/env python3
"""关键帧预览：每段取中点截一帧，拼成 contact sheet 目检。"""
import json, os, sys
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import launch_browser
from playwright.sync_api import sync_playwright

PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
d = json.load(open(os.path.join(PROJECT, "sop.json")))
OUT = os.path.join(PROJECT, "preview")
os.makedirs(OUT, exist_ok=True)

# 每段中点 + 该段 2.5s 处（镜头刚推近，最能看出 halo/cursor 是否套准）
marks = []
cursor = 0.0
for st in d["steps"]:
    marks.append((st["id"], round(cursor + st["duration"] * 0.55, 2)))
    cursor += st["duration"]

url = "file://" + os.path.join(PROJECT, "render.html")
with sync_playwright() as p:
    b = launch_browser(p)
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.goto(url)
    pg.wait_for_function("window.READY === true", timeout=20000)
    pg.wait_for_timeout(600)
    for sid, t in marks:
        pg.evaluate("t => window.renderAt(t)", t)
        pg.wait_for_timeout(120)
        pg.screenshot(path=os.path.join(OUT, f"{sid}.png"))
        print(f"  {sid} @ {t}s")
    b.close()

print(f"\n✅ {len(marks)} 帧 → preview/")
