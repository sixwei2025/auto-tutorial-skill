#!/usr/bin/env python3
"""渲染 16:9 说明卡（compare / list / steps 三种布局）

配置：cards/cards.json
用法：TV_PROJECT=/path/to/project python3 make_cards.py
"""
import json, os
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import launch_browser
from playwright.sync_api import sync_playwright

PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
CFG = json.load(open(os.path.join(PROJECT, "project.json")))
CC = CFG.get("cards", {})
CARDS = CC.get("items", [])
if not CARDS:
    print("无 cards 配置，跳过")
    raise SystemExit(0)

W = CC.get("width", 1080)
H = CC.get("height", 608)
ACCENT = CC.get("accent", "#C7352D")

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:__W__px;height:__H__px;background:#f5f4ef;overflow:hidden;
  font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif;-webkit-font-smoothing:antialiased;color:#111}
.card{width:__W__px;height:__H__px;padding:44px 56px;display:flex;flex-direction:column}
.head{display:flex;justify-content:space-between;align-items:baseline;
  padding-bottom:14px;border-bottom:2px solid #111;font-family:"SF Mono",Consolas,"JetBrains Mono",monospace;font-size:19px;letter-spacing:.14em}
.head .k{font-weight:600;color:__ACC__}
.head .i{color:#8a8681}
h2{font-size:44px;font-weight:600;line-height:1.22;margin:22px 0 26px;letter-spacing:-.01em}
h2 em{font-style:normal;color:__ACC__}
.body{flex:1;display:flex;gap:26px}
.col{flex:1;display:flex;flex-direction:column;gap:16px}
.slot{border:2px solid #111;background:#fff;overflow:hidden;line-height:0}
.slot img{width:100%;height:100%;object-fit:cover;display:block}
.tag{display:inline-block;font-size:20px;font-weight:600;padding:6px 14px 8px;color:#fff;background:#111;align-self:flex-start}
.tag.now{background:__ACC__}
.note{font-size:21px;line-height:1.5;color:#5a5750}
.note b{color:#111}
.item{display:flex;gap:16px;align-items:flex-start}
.num{flex:0 0 42px;height:42px;border-radius:50%;background:__ACC__;color:#fff;
  display:flex;align-items:center;justify-content:center;font-size:21px;font-weight:700}
.item .txt{font-size:24px;line-height:1.45;color:#2b2b2b}
.item .txt b{color:#111}
.item .sub{font-size:19px;color:#6b6762;margin-top:4px;line-height:1.45}
.steps{display:flex;gap:18px;flex:1}
.step{flex:1;border-top:3px solid #111;padding-top:16px;display:flex;flex-direction:column;gap:10px}
.step .n{font-family:"SF Mono",Consolas,"JetBrains Mono",monospace;font-size:15px;letter-spacing:.16em;color:__ACC__}
.step .t{font-size:25px;font-weight:600;line-height:1.32}
.step .d{font-size:19px;line-height:1.5;color:#6b6762}
.footline{margin-top:18px;padding-top:12px;border-top:1px solid #d2cfc4;font-size:19px;color:#7a7671}
"""


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build(card):
    typ = card.get("type", "list")
    body = ""

    if typ == "compare":
        left, right = card["left"], card["right"]
        body = (
            '<div class="body">'
            '<div class="col">'
            f'<span class="tag">{esc(left["tag"])}</span>'
            f'<div class="slot" style="height:248px"><img src="file://{left["img"]}"></div>'
            f'<div class="note">{left["note"]}</div>'
            '</div>'
            '<div class="col">'
            f'<span class="tag now">{esc(right["tag"])}</span>'
            f'<div class="slot" style="height:248px"><img src="file://{right["img"]}"></div>'
            f'<div class="note">{right["note"]}</div>'
            '</div></div>')

    elif typ == "steps":
        cells = "".join(
            f'<div class="step"><div class="n">{esc(s.get("n",""))}</div>'
            f'<div class="t">{s["t"]}</div><div class="d">{s["d"]}</div></div>'
            for s in card["steps"])
        body = f'<div class="steps">{cells}</div>'

    else:  # list
        items = "".join(
            f'<div class="item"><div class="num">{i+1}</div>'
            f'<div class="txt">{s["t"]}<div class="sub">{s.get("d","")}</div></div></div>'
            for i, s in enumerate(card["items"]))
        body = f'<div class="body"><div class="col">{items}</div></div>'

    foot = f'<div class="footline">{card["foot"]}</div>' if card.get("foot") else ""
    return (f'<div class="card"><div class="head"><span class="k">{esc(card.get("kicker",""))}</span>'
            f'<span class="i">{esc(card.get("index",""))}</span></div>'
            f'<h2>{card["title"]}</h2>{body}{foot}</div>')


css = CSS.replace("__W__", str(W)).replace("__H__", str(H)).replace("__ACC__", ACCENT)
os.makedirs(os.path.join(PROJECT, CC.get("outdir", "assets/screenshots")), exist_ok=True)

with sync_playwright() as p:
    b = launch_browser(p)
    pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=int(CC.get("dpr", 2)))
    for card in CARDS:
        # 相对路径转绝对
        for k in ("left", "right"):
            if k in card and "img" in card[k]:
                ip = card[k]["img"]
                card[k]["img"] = ip if os.path.isabs(ip) else os.path.join(PROJECT, ip)
        html = ("<!doctype html><html><head><meta charset='utf-8'><style>"
                + css + "</style></head><body>" + build(card) + "</body></html>")
        tmp = os.path.join(PROJECT, ".card.html")
        open(tmp, "w", encoding="utf-8").write(html)
        pg.goto("file://" + tmp)
        pg.wait_for_timeout(320)
        out = os.path.join(PROJECT, CC.get("outdir", "assets/screenshots"), card["id"] + ".png")
        pg.screenshot(path=out, full_page=True)
        print("  ✓", card["id"], W * 2, "x", H * 2)
    b.close()
os.remove(os.path.join(PROJECT, ".card.html"))
print("✅ %d 张说明卡" % len(CARDS))
