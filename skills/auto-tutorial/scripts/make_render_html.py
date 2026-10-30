#!/usr/bin/env python3
"""生成自包含渲染页 render.html（不依赖 HyperFrames 运行时）。
   暴露 window.renderAt(t) 供 Playwright 逐帧 seek。"""
import json, os

PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
d = json.load(open(os.path.join(PROJECT, "sop.json")))

# ---------------------------------------------------------------- 配色（品牌红为默认）
_pj = {}
try:
    _pj = json.load(open(os.path.join(PROJECT, "project.json"), encoding="utf-8"))
except Exception:
    pass
TH = _pj.get("theme", {})
ACCENT = TH.get("accent", "#C7352D")          # 品牌红
ACCENT_DEEP = TH.get("accent_deep", "#B92F27")
INK = TH.get("ink", "#1A1614")                # 正文墨色（暖黑，不带蓝）
INK_SOFT = TH.get("ink_soft", "#5C524D")
INK_MUTE = TH.get("ink_mute", "#8A7D77")
LINE = TH.get("line", "#EADCD9")
PANEL = TH.get("panel", "#FAF6F4")
SUB_FROM = TH.get("sub_from", "#B5A8A2")      # 字幕弹入初始色（暖浅灰）
SUB_TO = TH.get("sub_to", INK)                # 字幕稳定后颜色
SUB_BG = TH.get("sub_bg", "250,246,244")
SUB_LINE = TH.get("sub_line", "234,220,217")

# 老配色（蓝）→ 品牌配色；8 位色必须排在 6 位之前，否则替换不干净
COLOR_MAP = {
    "#1565D812": ACCENT + "12",
    "#1565D8": ACCENT,
    "#102A43": INK,
    "#D4E3F5": LINE,
    "#F5F8FC": PANEL,
    "#7A93AC": INK_MUTE,
    "#69809A": INK_MUTE,
    "#49657F": INK_SOFT,
    "#96B2C8": SUB_FROM,
    "rgba(242,247,253,": "rgba(%s," % SUB_BG,
    "rgba(212,227,245,": "rgba(%s," % SUB_LINE,
    "rgba(16,42,67,.30)": TH.get("shadow", "rgba(26,22,20,.30)"),
}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


SUB_FROM_RGB, SUB_TO_RGB = _rgb(SUB_FROM), _rgb(SUB_TO)

W, VW, VH = 1920, 1200, 675
cursor = 0.0
meta = []
for i, st in enumerate(d["steps"]):
    shot = next(s for s in d["screenshots"] if s["id"] == st["screenshot"])
    sc = min(VW / shot["width"], VH / shot["height"])
    fw, fh = shot["width"] * sc, shot["height"] * sc
    ox, oy = (VW - fw) / 2, (VH - fh) / 2
    tx, ty = st["target"]["x"], st["target"]["y"]
    tw, th = st["target"]["width"], st["target"]["height"]
    rx, ry = ox + tx * sc, oy + ty * sc
    rw, rh = tw * sc, th * sc
    zoom = st.get("zoom", 1.3)
    pan_x = min(0, max(VW * (1 - zoom), VW / 2 - (rx + rw / 2) * zoom))
    pan_y = min(0, max(VH * (1 - zoom), VH / 2 - (ry + rh / 2) * zoom))
    meta.append(dict(id=st["id"], start=cursor, dur=st["duration"], shot=shot["path"],
                     ox=ox, oy=oy, fw=fw, fh=fh, rx=rx, ry=ry, rw=rw, rh=rh,
                     zoom=zoom, panX=pan_x, panY=pan_y,
                     title=st["title"], instr=st["instruction"], aside=st.get("asideLabel", "这一步"),
                     tip=st.get("tip", ""), checks=st["checklist"], halo=st.get("halo", False), kind=st.get("kind",""),
                     source=shot.get("source") or shot.get("capturedAt", "")))
    cursor += st["duration"]

# 全局字幕（按时间轴展开）
CUES, _c = [], 0.0
for st in d["steps"]:
    for c in st["captions"]:
        CUES.append({"a": round(_c + c["start"], 3), "b": round(_c + c["end"], 3), "t": c["text"]})
    _c += st["duration"]

sections = []
CONTENT_TOTAL = sum(1 for x in meta if x.get("kind") != "cover")
sec_i = 0
for i, m in enumerate(meta):
    if m.get("kind") == "cover":
        sections.append(
            '<section id="sc-cover" class="scene">'
            '<div class="cover-bg" style="background-image:url(\'' + m["shot"] + '\')"></div>'
            '<div class="cover-wrap"><img class="cover-card" id="cover-card" src="' + m["shot"] + '"></div>'
            '</section>')
        continue
    sec_i += 1
    checks = "".join(
        '<li class="%s"><span class="mk">%s</span><span>%s</span></li>' % (
            c["state"],
            "✓" if c["state"] == "done" else ("→" if c["state"] == "current" else "○"),
            c["text"])
        for c in m["checks"])
    src = ("" if str(m["source"]).startswith("示意") else "真实截图 · ") + m["source"] if m["source"] else ""
    sections.append("""
<section id="sc-%(id)s" class="scene">
  <div class="eyebrow">%(series)s <span>%(idx)02d / %(total)02d</span></div>
  <h1>%(title)s</h1>
  <div class="viewport">
    <div id="cam-%(id)s" class="camera">
      <img class="shot" src="%(shot)s" style="left:%(ox).1fpx;top:%(oy).1fpx;width:%(fw).1fpx;height:%(fh).1fpx">
      <div class="halo" id="halo-%(id)s" style="left:%(hx).1fpx;top:%(hy).1fpx;width:%(hw).1fpx;height:%(hh).1fpx"></div>
      <svg class="cursor" id="cur-%(id)s" style="left:%(cx).1fpx;top:%(cy).1fpx" viewBox="0 0 36 44">
        <path d="M4 3L4 33L13 25L19 39L25 36L19 23L31 23Z" fill="#1565D8" stroke="#fff" stroke-width="3"/>
      </svg>
    </div>
  </div>
  <div class="capture-label">%(src)s</div>
  <aside>
    <div class="step-label">%(aside)s</div>
    <h2>%(instr)s</h2>
    <ul>%(checks)s</ul>
    <div class="tip">%(tip)s</div>
  </aside>
</section>""" % dict(
        id=m["id"], series=d["series"], idx=sec_i, total=CONTENT_TOTAL,
        title=m["title"], shot=m["shot"], ox=m["ox"], oy=m["oy"], fw=m["fw"], fh=m["fh"],
        hx=m["rx"] - 7, hy=m["ry"] - 7, hw=m["rw"] + 14, hh=m["rh"] + 14,
        cx=m["rx"] + m["rw"] * .62, cy=m["ry"] + m["rh"] * .55,
        src=src, aside=m["aside"], instr=m["instr"], checks=checks, tip=m["tip"]))

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:__W__px;height:1080px;overflow:hidden;background:#fff;
  font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif;color:#102A43}
#stage{position:relative;width:__W__px;height:1080px;background:#fff}
.scene{position:absolute;inset:0;opacity:0}
.eyebrow{position:absolute;left:80px;top:40px;right:80px;font-size:20px;font-weight:650;letter-spacing:2px;color:#1565D8}
.eyebrow span{float:right;color:#7A93AC}
h1{position:absolute;left:80px;top:84px;width:1760px;font-size:50px;font-weight:700;line-height:1.14;color:#1565D8}
.viewport{position:absolute;left:80px;top:180px;width:__VW__px;height:__VH__px;overflow:hidden;
  border:2px solid #D4E3F5;border-radius:18px;background:#F5F8FC}
.camera{position:absolute;left:0;top:0;width:__VW__px;height:__VH__px;transform-origin:0 0}
.shot{position:absolute;display:block}
.halo{position:absolute;border:5px solid #1565D8;background:#1565D812;border-radius:12px;opacity:0}
.cursor{position:absolute;width:36px;height:44px;opacity:0}
.capture-label{position:absolute;left:84px;top:872px;font-size:21px;color:#69809A}
aside{position:absolute;left:1340px;top:180px;width:500px;height:675px;padding:30px 32px;
  background:#F5F8FC;border:1px solid #D4E3F5;border-radius:18px}
.step-label{font-size:20px;font-weight:700;color:#1565D8;letter-spacing:2px}
h2{font-size:29px;line-height:1.32;margin:18px 0 30px;font-weight:650;color:#102A43;overflow-wrap:anywhere;word-break:break-word;width:100%}
ul{list-style:none;display:flex;flex-direction:column;gap:20px}
li{display:flex;gap:14px;font-size:26px;line-height:1.3;color:#49657F}
li.current{color:#1565D8;font-weight:650}
li.done{color:#102A43}
.mk{flex:0 0 26px}
.tip{position:absolute;left:32px;right:32px;bottom:28px;border-top:1px solid #D4E3F5;
  padding-top:20px;font-size:22px;line-height:1.35;color:#49657F}
#bar{position:absolute;left:0;top:1074px;height:6px;background:#1565D8;width:0;opacity:.85}
#subwrap{position:absolute;left:0;right:0;bottom:44px;display:flex;justify-content:center;pointer-events:none}
#sub{max-width:1720px;padding:15px 30px;border-radius:14px;white-space:nowrap;
  font-size:38px;line-height:1.28;text-align:center;opacity:0;
  transform-origin:center bottom;background:rgba(242,247,253,0);border:2px solid rgba(212,227,245,0);color:#96B2C8}
.cover-bg{position:absolute;inset:-90px;background-size:cover;background-position:center;
  filter:blur(50px) saturate(1.18) brightness(1.02);opacity:.62}
.cover-wrap{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.cover-card{height:1040px;width:auto;border-radius:20px;box-shadow:0 34px 100px rgba(16,42,67,.30)}
""".replace("__W__", str(W)).replace("__VW__", str(VW)).replace("__VH__", str(VH))

for _a, _b in COLOR_MAP.items():
    CSS = CSS.replace(_a, _b)

JS = """
const META = __META__;
const TOTAL = __TOTAL__;
const CUES = __CUES__;
const easeInOut = t => t<0.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2;
const clamp01 = v => Math.max(0, Math.min(1, v));
function fitSub(){
  var sub = document.getElementById('sub');
  var fs = 38;
  sub.style.fontSize = fs + 'px';
  var guard = 0;
  while(sub.scrollWidth > 1700 && fs > 24 && guard++ < 40){
    fs -= 1;
    sub.style.fontSize = fs + 'px';
  }
}
function renderAt(t){
  for(const m of META){
    const el = document.getElementById('sc-'+m.id);
    const local = t - m.start;
    if(m.kind === 'cover'){
      const fade = Math.max(0, 1 - Math.max(0, local - 0.08) / 0.32);
      el.style.opacity = fade;
      el.style.visibility = fade > 0.002 ? 'visible' : 'hidden';
      const cc = document.getElementById('cover-card');
      if(cc){ const cp = clamp01(local/2.6); cc.style.transform = 'scale(' + (1.045 - 0.045*easeInOut(cp)) + ')'; }
      continue;
    }
    let op = 0;
    if(local >= 0 && local <= m.dur){
      op = Math.min(clamp01(local/0.4), clamp01((m.dur-local)/0.35));
    }
    el.style.opacity = op;
    if(op <= 0.001){ el.style.visibility='hidden'; continue; }
    el.style.visibility='visible';
    const k = clamp01((local-0.85)/1.1);
    const e = easeInOut(k);
    const z = 1 + (m.zoom-1)*e;
    const cam = document.getElementById('cam-'+m.id);
    if(cam){ cam.style.transform = 'translate(' + (m.panX*e) + 'px,' + (m.panY*e) + 'px) scale(' + z + ')'; }
    const hEl = document.getElementById('halo-'+m.id), cEl = document.getElementById('cur-'+m.id);
    if(hEl && cEl){
      if(m.halo){
        hEl.style.opacity = clamp01((local-0.6)/0.3)*0.95;
        const ce = easeInOut(clamp01((local-0.7)/0.65));
        cEl.style.opacity = clamp01((local-0.7)/0.4);
        cEl.style.transform = 'translate(' + (34*(1-ce)) + 'px,' + (32*(1-ce)) + 'px)';
      } else {
        hEl.style.opacity = 0; cEl.style.opacity = 0;
      }
    }
  }
  document.getElementById('bar').style.width = (1920*clamp01(t/TOTAL)) + 'px';

  var cur = null;
  for (var i=0;i<CUES.length;i++){ if(t>=CUES[i].a && t<=CUES[i].b){ cur = CUES[i]; break; } }
  var sub = document.getElementById('sub');
  if(cur){
    if(sub.textContent !== cur.t){
      sub.textContent = cur.t;
      fitSub();
    }
    var lp = clamp01((t-cur.a)/0.30);
    var eb = 1 + 2.4*Math.pow(lp-1,3) + 1.4*Math.pow(lp-1,2);      // easeOutBack 弹入
    sub.style.transform = 'scale(' + (0.90 + 0.10*eb) + ')';
    sub.style.opacity = clamp01(lp*3.2) * clamp01((cur.b-t)/0.16);
    var cr = Math.round(__SF_R__ + (__ST_R__-__SF_R__)*lp),
        cg = Math.round(__SF_G__ + (__ST_G__-__SF_G__)*lp),
        cb2 = Math.round(__SF_B__ + (__ST_B__-__SF_B__)*lp);
    sub.style.color = 'rgb(' + cr + ',' + cg + ',' + cb2 + ')';       // 暖浅灰 → 墨色
    sub.style.backgroundColor = 'rgba(242,247,253,' + (0.96*lp).toFixed(3) + ')';
    sub.style.borderColor = 'rgba(212,227,245,' + lp.toFixed(3) + ')';
  } else { sub.style.opacity = 0; }
}
window.renderAt = renderAt;
window.TOTAL = TOTAL;
window.READY = true;
renderAt(0);
""".replace("__META__", json.dumps(meta, ensure_ascii=False)).replace("__TOTAL__", str(cursor)).replace("__CUES__", json.dumps(CUES, ensure_ascii=False))

for _a, _b in COLOR_MAP.items():
    JS = JS.replace(_a, _b)
JS = (JS.replace("__SF_R__", str(SUB_FROM_RGB[0])).replace("__ST_R__", str(SUB_TO_RGB[0]))
        .replace("__SF_G__", str(SUB_FROM_RGB[1])).replace("__ST_G__", str(SUB_TO_RGB[1]))
        .replace("__SF_B__", str(SUB_FROM_RGB[2])).replace("__ST_B__", str(SUB_TO_RGB[2])))

html = ("<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\"><style>"
        + CSS + "</style></head><body><div id=\"stage\">"
        + "".join(sections) + "<div id=\"subwrap\"><div id=\"sub\"></div></div><div id=\"bar\"></div></div><script>"
        + JS + "</script></body></html>")

for _a, _b in COLOR_MAP.items():      # 兜住 html 片段里残留的老配色（光标 icon 等）
    html = html.replace(_a, _b)

open(os.path.join(PROJECT, "render.html"), "w").write(html)
print("✅ render.html  %d 字符 · %d 段 · %.2fs · 主色 %s" % (len(html), len(meta), cursor, ACCENT))
