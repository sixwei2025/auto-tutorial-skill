#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 0｜渲染 3:4 竖版封面 + 16:9 横屏视频 0.01s 首帧

2026-11-13 审美全面升级：
  - 默认启用 `render_video_cover.py`（Editorial 杂志风 + Swiss 瑞士网格风 6+1 套主题 × 4 大版式），
    彻底淘汰 2010 年代电商五段金色渐变 + 3D 发光球旧模板。
  - 同时生成：
    1. `cover/cover-3x4.png` & `cover/cover-3x4.jpg`（1080×1440 / 2160×2880 竖版 3:4 独立封面）
    2. `cover/cover-opening.png` & `cover/cover-opening.jpg`（1920×1080 横版 16:9 成片 0.01s 首帧）
  - 100% 兼容原有 `project.json` 的 `cover` 字段（`title_lines`、`badge`/`kicker`、`sub`、`shot`、`theme`、`layout`、`metric`）。
  - 若极少数旧工程显式指定 `cover.legacy_template: true`，仍可回退旧 HTML 模板。

用法：
  TV_PROJECT=/path/to/project python3 make_cover.py
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_video_cover import render_cover_pair

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
CFG_PATH = os.path.join(PROJECT, "project.json")
CFG = json.load(open(CFG_PATH, encoding="utf-8")) if os.path.exists(CFG_PATH) else {}
C = CFG.get("cover", {})

OUT = os.path.join(PROJECT, C.get("output", "cover/cover-3x4.png"))
OPENING_OUT = os.path.join(PROJECT, C.get("opening_output", "cover/cover-opening.png"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)


def run_modern_cover():
    raw_lines = C.get("title_lines") or [CFG.get("title", "AI 自动化工作流")]
    lines = [str(t).strip() for t in raw_lines if str(t).strip()]
    max_lines = int(C.get("max_lines", 3))
    if len(lines) > max_lines:
        lines = [lines[0], lines[-1]] if max_lines == 2 else lines[:max_lines]
    if not lines:
        lines = ["AI 自动化工作流"]

    kicker = str(C.get("kicker") or C.get("badge") or "HUIXIN · AI STUDIO").strip()
    brand = str(C.get("brand") or "").strip()
    sub = str(C.get("subtitle") or C.get("sub") or "").strip()
    metric = str(C.get("metric") or C.get("index") or "").strip()
    metric_label = str(C.get("metric_label") or "").strip()

    # 若第 1 行纯英文/品牌短词且有多行，自动提拔为 brand 引子行，把视觉重心留给中文钩子
    if not brand and len(lines) >= 2 and re.match(r"^[A-Za-z0-9 _.\-+]{2,18}$", lines[0]):
        brand = lines[0]
        lines = lines[1:]

    shot_rel = C.get("shot") or ""
    shot_abs = ""
    if shot_rel:
        cand = shot_rel if os.path.isabs(shot_rel) else os.path.join(PROJECT, shot_rel)
        if os.path.isfile(cand):
            shot_abs = cand

    # 智能路由版式与主题
    theme = str(C.get("theme") or "swiss_dark").strip().lower()
    layout = str(C.get("layout") or "").strip().lower()
    if not layout:
        if C.get("art") == "shot" and shot_abs:
            layout = "ui-showcase"
        elif metric:
            layout = "swiss-metric"
        elif C.get("portrait") is True:
            layout = "editorial-portrait"
        elif C.get("portrait") is False:
            layout = "manifesto-poster"
        else:
            # 默认用杂志人像或瑞士网格
            layout = "editorial-portrait"

    brief = {
        "kicker": kicker,
        "brand": brand,
        "title_lines": lines,
        "subtitle": sub,
        "metric": metric,
        "metric_label": metric_label,
        "shot": shot_abs,
        "theme": theme,
        "layout": layout,
        "strip_left": str(C.get("foot_left") or C.get("strip_left") or "袁六伟 · 台州汇芯").strip(),
        "strip_right": str(C.get("foot_right") or C.get("strip_right") or "AI WORKFLOW").strip(),
    }

    dpr = int(C.get("dpr", 2))
    out_dir = Path(os.path.dirname(OUT))
    out_3x4_name = os.path.basename(OUT)
    out_16x9_name = os.path.basename(OPENING_OUT)

    res = render_cover_pair(
        brief,
        out_dir=out_dir,
        theme_key=theme,
        layout=layout,
        out_3x4_name=out_3x4_name,
        out_16x9_name=out_16x9_name,
        dpr=dpr,
        center_safe_16x9=bool(C.get("center_safe_16x9", False)),
    )

    print(
        "✅ 封面渲染完成 [%s / %s]\n   ↳ 3:4 竖版封面: %s (%s)\n   ↳ 16:9 视频首帧: %s"
        % (res["theme"], res["layout"], res["cover_3x4_png"], res["cover_3x4_jpg"], res["cover_16x9_png"])
    )
    for w in res.get("warns", []):
        print("   ⚠ " + w)
    for e in res.get("errors", []):
        print("   ❌ " + e)


if __name__ == "__main__":
    run_modern_cover()
