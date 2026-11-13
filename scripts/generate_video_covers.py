#!/usr/bin/env python3
"""
汇芯系列视频 Skill · 六套高格调 3:4 视频封面通用生成器（1080x1440）
灵感源自 GitHub 开源设计系统：
- 01 swiss      : 瑞士国际主义 12 栏网格构成主义
- 02 magazine   : 商业人物杂志刊头（Monocle / Wired 景深风）
- 03 bento      : 暗黑 Bento 便当盒极客风
- 04 split      : 上白下汇芯红撞色对开
- 05 brutalist  : 新粗野主义黑黄大字报
- 06 gallery    : 美术馆画廊拱门极简风

硬标准：
1. 必须露出袁六伟高清个人形象照
2. 上部大字报风格短标题（建议 ≤ 10 字，复用 NotoSansCJKsc-Black.otf）
3. 支持 --theme 指定单套或 all 全部六套输出
"""
import argparse
import subprocess
from pathlib import Path
from typing import Optional
from PIL import Image

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_FONT = "/Users/yuanliuwei/.agents/skills/wechat-autopilot/skills/wechat-cover-skill/assets/fonts/NotoSansCJKsc-Black.otf"
DEFAULT_PORTRAIT = "/Users/yuanliuwei/.agents/skills/wechat-autopilot/skills/wechat-cover-skill/assets/owner_cutout_hd.png"
FALLBACK_PORTRAITS = [
    "/Users/yuanliuwei/汇芯公众号自动化宣传片/film/assets/shots/owner_cutout_hd.png",
    "/Users/yuanliuwei/Workbuddy/github-skills-14/ai-tool-review-wechat-skill/drafts/2026-11-12-local-video-hub/assets/portrait_lit.png",
]


def resolve_portrait(custom_path: Optional[str]) -> str:
    if custom_path and Path(custom_path).exists():
        return str(Path(custom_path).resolve())
    for p in FALLBACK_PORTRAITS + [DEFAULT_PORTRAIT]:
        if Path(p).exists():
            return str(Path(p).resolve())
    raise FileNotFoundError("未找到高清人像文件，请通过 --portrait 指定")


def common_head(font_path: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  @font-face {{
    font-family: "CoverBlack";
    src: url("file://{font_path}");
    font-weight: 900;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: 1080px; height: 1440px; overflow: hidden;
    font-family: "CoverBlack", "PingFang SC", "Hiragino Sans GB", sans-serif;
  }}
</style>
"""


def build_swiss(cfg: dict) -> str:
    return common_head(cfg["font"]) + f"""
<style>
  body {{ background: #F4F4F0; color: #111111; }}
  .canvas {{ position: relative; width: 1080px; height: 1440px; padding: 52px 58px; overflow: hidden; }}
  .grid-lines {{
    position: absolute; inset: 0; padding: 0 58px;
    display: grid; grid-template-columns: repeat(12, 1fr); pointer-events: none; z-index: 1;
  }}
  .grid-lines span {{ border-right: 1px solid rgba(0,0,0,0.06); }}
  .grid-lines span:first-child {{ border-left: 1px solid rgba(0,0,0,0.06); }}
  .header {{
    position: relative; z-index: 4;
    display: flex; justify-content: space-between; align-items: center;
    border-top: 4px solid #111111; border-bottom: 2px solid #111111;
    padding: 14px 0; font-size: 22px; letter-spacing: 2px;
  }}
  .hero {{
    position: relative; z-index: 4; margin-top: 38px;
    display: grid; grid-template-columns: 7fr 5fr; gap: 28px; align-items: start;
  }}
  .title {{ font-size: 164px; line-height: 0.98; letter-spacing: 2px; }}
  .title .red {{ color: #E02418; display: block; margin-top: 6px; }}
  .spec-col {{
    border-left: 3px solid #111111; padding-left: 22px; padding-top: 8px;
    display: flex; flex-direction: column; gap: 18px;
  }}
  .spec-tag {{
    display: inline-block; width: fit-content; background: #111111; color: #F4F4F0;
    padding: 6px 14px; font-size: 21px; letter-spacing: 1px;
  }}
  .spec-copy {{ font-size: 26px; line-height: 1.5; color: #262626; }}
  .geo-circle {{
    position: absolute; left: 74px; top: 610px; width: 420px; height: 420px;
    border-radius: 50%; background: #E02418; z-index: 2;
  }}
  .geo-ring {{
    position: absolute; left: 160px; top: 690px; width: 520px; height: 520px;
    border-radius: 50%; border: 3px solid #111111; z-index: 2;
  }}
  .left-data {{
    position: absolute; left: 58px; bottom: 118px; z-index: 5;
    display: flex; flex-direction: column; gap: 12px;
  }}
  .data-pill {{
    background: rgba(244,244,240,0.94); border: 2px solid #111111;
    padding: 12px 22px; font-size: 28px; width: fit-content;
    box-shadow: 6px 6px 0 #111111;
  }}
  .portrait {{
    position: absolute; right: 20px; bottom: 0; width: 760px; height: 840px; z-index: 3;
    display: flex; align-items: flex-end; justify-content: flex-end;
  }}
  .portrait img {{
    width: 100%; height: 100%; object-fit: contain; object-position: bottom right;
    filter: contrast(1.06) brightness(0.95) saturate(0.90) drop-shadow(-10px 8px 26px rgba(0,0,0,0.18));
  }}
  .footer {{
    position: absolute; left: 58px; right: 58px; bottom: 34px; z-index: 6;
    border-top: 2px solid #111111; padding-top: 12px;
    display: flex; justify-content: space-between; font-size: 22px; letter-spacing: 1px;
    background: rgba(244,244,240,0.92);
  }}
</style>
<body>
<div class="canvas">
  <div class="grid-lines"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
  <div class="header">
    <span>{cfg['issue']} // HUIXIN AI LAB</span>
    <span>SWISS GRID EDITION</span>
    <span>2026</span>
  </div>
  <div class="hero">
    <div class="title">{cfg['line1']}<span class="red">{cfg['line2']}</span></div>
    <div class="spec-col">
      <div class="spec-tag">{cfg['kicker']}</div>
      <div class="spec-copy">{cfg['sub']}</div>
    </div>
  </div>
  <div class="geo-circle"></div>
  <div class="geo-ring"></div>
  <div class="left-data">
    <div class="data-pill">{cfg['stat1']}</div>
    <div class="data-pill">{cfg['author']}</div>
  </div>
  <div class="portrait"><img src="file://{cfg['portrait']}"></div>
  <div class="footer">
    <span>{cfg['repo_tag']}</span>
    <span>{cfg['channel']}</span>
  </div>
</div>
</body></html>"""


def build_magazine(cfg: dict) -> str:
    full_title = f"{cfg['line1']}{cfg['line2']}"
    return common_head(cfg["font"]) + f"""
<style>
  body {{ background: #141210; color: #F7F2E8; }}
  .canvas {{
    position: relative; width: 1080px; height: 1440px; overflow: hidden;
    background:
      radial-gradient(ellipse 900px 700px at 540px 920px, rgba(196, 150, 74, 0.25) 0%, rgba(20, 18, 16, 0) 74%),
      linear-gradient(180deg, #171411 0%, #0D0C0A 100%);
  }}
  .masthead {{
    position: relative; z-index: 4; margin: 44px 58px 0;
    border-bottom: 2px solid rgba(247,242,232,0.28); padding-bottom: 14px;
    display: flex; justify-content: space-between; align-items: baseline;
  }}
  .brand-name {{ font-size: 56px; letter-spacing: 6px; color: #E5BA68; }}
  .issue-meta {{ font-size: 22px; letter-spacing: 2px; color: rgba(247,242,232,0.68); }}
  .headline-wrap {{ position: relative; z-index: 5; margin: 28px 58px 0; text-align: center; }}
  .kicker {{
    display: inline-block; border: 1.5px solid #E5BA68; color: #E5BA68;
    padding: 6px 22px; border-radius: 999px; font-size: 24px; letter-spacing: 2px; margin-bottom: 18px;
  }}
  .big-title {{
    font-size: 142px; line-height: 1.05; letter-spacing: 4px; white-space: nowrap;
    background: linear-gradient(180deg, #FFFFFF 0%, #F7DFAB 58%, #D49E3D 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 12px 26px rgba(0,0,0,0.85));
  }}
  .bg-watermark {{
    position: absolute; left: 50%; top: 500px; transform: translateX(-50%); z-index: 2;
    font-size: 200px; letter-spacing: 14px; color: rgba(255,255,255,0.05); white-space: nowrap;
  }}
  .portrait {{
    position: absolute; left: 50%; bottom: 0; transform: translateX(-50%);
    width: 820px; height: 830px; z-index: 3;
    display: flex; align-items: flex-end; justify-content: center;
  }}
  .portrait img {{
    width: 100%; height: 100%; object-fit: contain; object-position: bottom center;
    filter: contrast(1.06) brightness(0.95) drop-shadow(0 -12px 44px rgba(0,0,0,0.9));
  }}
  .callout-left {{
    position: absolute; left: 58px; top: 690px; z-index: 5; width: 250px;
    border-top: 3px solid #E5BA68; padding-top: 12px;
  }}
  .callout-right {{
    position: absolute; right: 58px; top: 690px; z-index: 5; width: 250px; text-align: right;
    border-top: 3px solid #E5BA68; padding-top: 12px;
  }}
  .c-num {{ font-size: 50px; color: #E5BA68; line-height: 1.1; }}
  .c-lbl {{ font-size: 23px; color: rgba(247,242,232,0.82); margin-top: 4px; line-height: 1.35; }}
  .bottom-fade {{
    position: absolute; left: 0; right: 0; bottom: 0; height: 180px; z-index: 4;
    background: linear-gradient(180deg, rgba(13,12,10,0) 0%, rgba(13,12,10,0.95) 100%);
  }}
  .footer-bar {{
    position: absolute; left: 58px; right: 58px; bottom: 36px; z-index: 6;
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid rgba(229,186,104,0.45); padding-top: 14px;
    font-size: 24px; color: #E5BA68; letter-spacing: 1px;
  }}
</style>
<body>
<div class="canvas">
  <div class="masthead">
    <div class="brand-name">HUIXIN · 汇芯</div>
    <div class="issue-meta">AI 实战人物封面 · {cfg['issue']}</div>
  </div>
  <div class="headline-wrap">
    <div class="kicker">{cfg['kicker']}</div>
    <div class="big-title">{full_title}</div>
  </div>
  <div class="bg-watermark">HUIXIN</div>
  <div class="callout-left">
    <div class="c-num">{cfg['stat1_val']}</div>
    <div class="c-lbl">{cfg['stat1_lbl']}</div>
  </div>
  <div class="callout-right">
    <div class="c-num">{cfg['stat2_val']}</div>
    <div class="c-lbl">{cfg['stat2_lbl']}</div>
  </div>
  <div class="portrait"><img src="file://{cfg['portrait']}"></div>
  <div class="bottom-fade"></div>
  <div class="footer-bar">
    <span>{cfg['author']}（学员 7000+ · 服务企业 100+）</span>
    <span>GitHub 开源</span>
  </div>
</div>
</body></html>"""


def build_bento(cfg: dict) -> str:
    return common_head(cfg["font"]) + f"""
<style>
  body {{ background: #07090D; color: #F8FAFC; }}
  .canvas {{
    position: relative; width: 1080px; height: 1440px; padding: 52px; overflow: hidden;
    background:
      radial-gradient(ellipse 700px 600px at 760px 980px, rgba(56, 189, 248, 0.22) 0%, rgba(7,9,13,0) 75%),
      linear-gradient(180deg, #07090D 0%, #0C1018 100%);
  }}
  .top-bento {{ display: grid; grid-template-columns: 1fr auto; gap: 16px; margin-bottom: 26px; }}
  .cmd-box {{
    background: rgba(255,255,255,0.04); border: 1.5px solid rgba(148,163,184,0.22);
    border-radius: 18px; padding: 16px 26px; font-size: 26px; color: #38BDF8;
    display: flex; align-items: center; gap: 14px;
  }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; background: #22C55E; }}
  .ver-box {{
    background: rgba(56,189,248,0.12); border: 1.5px solid rgba(56,189,248,0.45);
    border-radius: 18px; padding: 16px 26px; font-size: 24px; color: #BAE6FD;
  }}
  .title-card {{
    background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
    border: 1.5px solid rgba(255,255,255,0.14); border-radius: 28px;
    padding: 36px 40px; margin-bottom: 24px;
  }}
  .t-line1 {{ font-size: 134px; line-height: 1.05; color: #FFFFFF; letter-spacing: 3px; }}
  .t-line2 {{
    font-size: 134px; line-height: 1.05; letter-spacing: 3px;
    background: linear-gradient(90deg, #38BDF8 0%, #818CF8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }}
  .bottom-grid {{ position: relative; display: grid; grid-template-columns: 420px 1fr; gap: 22px; height: 760px; }}
  .stat-col {{ display: flex; flex-direction: column; gap: 18px; z-index: 4; }}
  .stat-card {{
    flex: 1; background: rgba(255,255,255,0.04); border: 1.5px solid rgba(148,163,184,0.20);
    border-radius: 24px; padding: 26px 28px; display: flex; flex-direction: column; justify-content: center;
  }}
  .s-val {{ font-size: 54px; color: #38BDF8; line-height: 1.1; }}
  .s-lbl {{ font-size: 25px; color: #CBD5E1; margin-top: 8px; }}
  .portrait-card {{
    position: relative; background: linear-gradient(180deg, rgba(56,189,248,0.10) 0%, rgba(15,23,42,0.6) 100%);
    border: 1.5px solid rgba(56,189,248,0.35); border-radius: 28px; overflow: hidden;
  }}
  .portrait-card img {{
    position: absolute; bottom: 0; left: 50%; transform: translateX(-50%);
    width: 112%; height: 100%; object-fit: contain; object-position: bottom center;
    filter: contrast(1.05) brightness(0.97) drop-shadow(0 -8px 30px rgba(0,0,0,0.85));
  }}
  .name-badge {{
    position: absolute; left: 22px; right: 22px; bottom: 20px; z-index: 5;
    background: rgba(7,9,13,0.86); border: 1px solid rgba(56,189,248,0.45);
    border-radius: 14px; padding: 12px 18px; text-align: center;
    font-size: 24px; color: #E0F2FE;
  }}
</style>
<body>
<div class="canvas">
  <div class="top-bento">
    <div class="cmd-box"><span class="dot"></span><span>&gt; {cfg['repo_tag']}</span></div>
    <div class="ver-box">GitHub 免费</div>
  </div>
  <div class="title-card">
    <div class="t-line1">{cfg['line1']}</div>
    <div class="t-line2">{cfg['line2']}</div>
  </div>
  <div class="bottom-grid">
    <div class="stat-col">
      <div class="stat-card"><div class="s-val">{cfg['stat1_val']}</div><div class="s-lbl">{cfg['stat1_lbl']}</div></div>
      <div class="stat-card"><div class="s-val">{cfg['stat2_val']}</div><div class="s-lbl">{cfg['stat2_lbl']}</div></div>
      <div class="stat-card"><div class="s-val">{cfg['stat3_val']}</div><div class="s-lbl">{cfg['stat3_lbl']}</div></div>
    </div>
    <div class="portrait-card">
      <img src="file://{cfg['portrait']}">
      <div class="name-badge">{cfg['author']}</div>
    </div>
  </div>
</div>
</body></html>"""


def build_split(cfg: dict) -> str:
    return common_head(cfg["font"]) + f"""
<style>
  body {{ background: #FAF9F6; color: #111111; }}
  .canvas {{ position: relative; width: 1080px; height: 1440px; overflow: hidden; }}
  .top-half {{ position: relative; height: 590px; background: #FAF9F6; padding: 54px 66px 0; }}
  .top-tag-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
  .pill-red {{
    background: #C8102E; color: #FFFFFF; padding: 9px 24px; border-radius: 6px;
    font-size: 26px; letter-spacing: 1px;
  }}
  .top-sub {{ font-size: 25px; color: #525252; }}
  .headline {{ font-size: 162px; line-height: 1.02; color: #111111; letter-spacing: 3px; }}
  .headline .accent {{ color: #C8102E; }}
  .bottom-half {{
    position: relative; height: 850px;
    background: radial-gradient(ellipse 840px 620px at 540px 560px, #C8102E 0%, #5B0613 55%, #160306 100%);
    border-top: 10px solid #C8102E;
  }}
  .portrait {{
    position: absolute; left: 50%; bottom: 0; transform: translateX(-50%);
    width: 820px; height: 820px; z-index: 3;
    display: flex; align-items: flex-end; justify-content: center;
  }}
  .portrait img {{
    width: 100%; height: 100%; object-fit: contain; object-position: bottom center;
    filter: contrast(1.04) brightness(0.98) drop-shadow(0 -12px 38px rgba(0,0,0,0.65));
  }}
  .quote-strip {{
    position: absolute; left: 66px; right: 66px; bottom: 38px; z-index: 5;
    background: rgba(15, 4, 6, 0.88); border: 2px solid rgba(255,215,130,0.55);
    border-radius: 16px; padding: 16px 28px;
    display: flex; justify-content: space-between; align-items: center;
    color: #FFFFFF; font-size: 27px;
  }}
  .quote-strip .gold {{ color: #F6CF71; }}
</style>
<body>
<div class="canvas">
  <div class="top-half">
    <div class="top-tag-row">
      <div class="pill-red">{cfg['kicker']}</div>
      <div class="top-sub">{cfg['channel']}</div>
    </div>
    <div class="headline">{cfg['line1']}<br><span class="accent">{cfg['line2']}</span></div>
  </div>
  <div class="bottom-half">
    <div class="portrait"><img src="file://{cfg['portrait']}"></div>
    <div class="quote-strip">
      <span>{cfg['author']}</span>
      <span class="gold">{cfg['stat1']}</span>
    </div>
  </div>
</div>
</body></html>"""


def build_brutalist(cfg: dict) -> str:
    return common_head(cfg["font"]) + f"""
<style>
  body {{ background: #0A0A0A; color: #FFFFFF; }}
  .canvas {{ position: relative; width: 1080px; height: 1440px; overflow: hidden; background: #0A0A0A; }}
  .warn-tape {{
    position: absolute; top: 0; left: 0; right: 0; height: 54px;
    background: #F5C518; color: #0A0A0A;
    display: flex; align-items: center; justify-content: space-between; padding: 0 46px;
    font-size: 24px; letter-spacing: 2px; z-index: 6;
  }}
  .header {{ position: relative; z-index: 5; padding: 92px 62px 0; }}
  .title-box {{ font-size: 164px; line-height: 1.02; letter-spacing: 3px; color: #FFFFFF; }}
  .hl-yellow {{
    display: inline-block; background: #F5C518; color: #0A0A0A;
    padding: 4px 24px 10px; margin-top: 12px; border-radius: 10px;
    box-shadow: 10px 10px 0 #FFFFFF;
  }}
  .sticker {{
    position: absolute; right: 56px; top: 470px; z-index: 6;
    background: #E11D48; color: #FFFFFF; padding: 14px 26px;
    font-size: 30px; border: 3px solid #FFFFFF; transform: rotate(-4deg);
    box-shadow: 8px 8px 0 #F5C518;
  }}
  .bg-stripe {{
    position: absolute; left: -60px; right: -60px; top: 760px; height: 240px;
    background: rgba(245,197,24,0.12); border-top: 2px solid #F5C518; border-bottom: 2px solid #F5C518;
    transform: rotate(-3deg); z-index: 1;
  }}
  .portrait {{
    position: absolute; left: 50%; bottom: 0; transform: translateX(-50%);
    width: 820px; height: 800px; z-index: 3;
    display: flex; align-items: flex-end; justify-content: center;
  }}
  .portrait img {{
    width: 100%; height: 100%; object-fit: contain; object-position: bottom center;
    filter: contrast(1.08) brightness(0.96) drop-shadow(0 -10px 38px rgba(245,197,24,0.22));
  }}
  .footer {{
    position: absolute; left: 54px; right: 54px; bottom: 34px; z-index: 6;
    background: #141414; border: 2px solid #F5C518; padding: 14px 28px;
    display: flex; justify-content: space-between; font-size: 26px; color: #F5C518;
  }}
</style>
<body>
<div class="canvas">
  <div class="warn-tape">
    <span>AI AUTOMATION SKILL</span>
    <span>GITHUB 开源</span>
    <span>HUIXIN</span>
  </div>
  <div class="header">
    <div class="title-box">
      <div>{cfg['line1']}</div>
      <div class="hl-yellow">{cfg['line2']}</div>
    </div>
  </div>
  <div class="sticker">{cfg['stat1']}</div>
  <div class="bg-stripe"></div>
  <div class="portrait"><img src="file://{cfg['portrait']}"></div>
  <div class="footer">
    <span>{cfg['author']}</span>
    <span>学员 7000+ · 免费开源</span>
  </div>
</div>
</body></html>"""


def build_gallery(cfg: dict) -> str:
    return common_head(cfg["font"]) + f"""
<style>
  body {{ background: #FAF8F5; color: #1A1D20; }}
  .canvas {{ position: relative; width: 1080px; height: 1440px; padding: 48px; overflow: hidden; }}
  .frame {{
    position: relative; width: 100%; height: 100%;
    border: 2px solid #1A1D20; padding: 48px 52px 0;
    display: flex; flex-direction: column; align-items: center;
    background: linear-gradient(180deg, #FAF8F5 0%, #EFECE6 100%);
  }}
  .top-label {{ font-size: 22px; letter-spacing: 5px; color: #6B7280; margin-bottom: 22px; }}
  .title {{ font-size: 148px; line-height: 1.05; text-align: center; color: #1A1D20; letter-spacing: 6px; }}
  .title .accent {{ color: #1E3A8A; }}
  .sub-rule {{ width: 140px; height: 4px; background: #1E3A8A; margin: 26px auto 18px; }}
  .sub-text {{ font-size: 28px; color: #374151; letter-spacing: 2px; }}
  .inner-arch {{
    position: absolute; bottom: 0; left: 60px; right: 60px; height: 730px;
    background: linear-gradient(180deg, #1E3A8A 0%, #0F172A 100%);
    border-radius: 360px 360px 0 0; overflow: hidden;
  }}
  .inner-arch img {{
    position: absolute; bottom: 0; left: 50%; transform: translateX(-50%);
    width: 780px; height: 730px; object-fit: contain; object-position: bottom center;
    filter: contrast(1.04) brightness(0.98) drop-shadow(0 -8px 34px rgba(0,0,0,0.45));
  }}
  .gallery-plaque {{
    position: absolute; bottom: 32px; left: 50%; transform: translateX(-50%); z-index: 6;
    background: #FAF8F5; border: 2px solid #1A1D20; padding: 12px 34px;
    font-size: 25px; color: #1A1D20; white-space: nowrap; letter-spacing: 1px;
  }}
</style>
<body>
<div class="canvas">
  <div class="frame">
    <div class="top-label">HUIXIN · YUAN LIUWEI · SKILL SERIES</div>
    <div class="title">{cfg['line1']}<br><span class="accent">{cfg['line2']}</span></div>
    <div class="sub-rule"></div>
    <div class="sub-text">{cfg['stat1']}</div>
    <div class="inner-arch"><img src="file://{cfg['portrait']}"></div>
    <div class="gallery-plaque">{cfg['author']}（GitHub 开源）</div>
  </div>
</div>
</body></html>"""


BUILDERS = {
    "swiss": ("01-swiss-grid", build_swiss),
    "magazine": ("02-magazine-masthead", build_magazine),
    "bento": ("03-bento-tech", build_bento),
    "split": ("04-editorial-split", build_split),
    "brutalist": ("05-brutalist-poster", build_brutalist),
    "gallery": ("06-minimal-gallery", build_gallery),
}


def render_one(file_stem: str, html: str, out_dir: Path, width: int = 1080, height: int = 1440, save_png: bool = False) -> Path:
    html_path = out_dir / f"{file_stem}.html"
    png_path = out_dir / f"{file_stem}.png"
    jpg_path = out_dir / f"{file_stem}.jpg"
    html_path.write_text(html, encoding="utf-8")
    subprocess.run(
        [
            CHROME_BIN,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--user-data-dir=/tmp/chrome-headless-profile",
            f"--window-size={width},{height}",
            "--force-device-scale-factor=1",
            "--hide-scrollbars",
            f"--screenshot={png_path}",
            f"file://{html_path}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Image.open(png_path).convert("RGB").save(jpg_path, quality=95)
    if not save_png:
        png_path.unlink(missing_ok=True)
    return jpg_path


THEMES_16X9 = {
    "swiss": {"bg": "#F4F4F0", "fg": "#111111", "accent": "#E02418", "pill_bg": "#111111", "pill_fg": "#F4F4F0", "bar": "#111111", "grid": "rgba(0,0,0,0.06)"},
    "magazine": {"bg": "linear-gradient(135deg, #171411 0%, #0D0C0A 100%)", "fg": "#F7F2E8", "accent": "#E5BA68", "pill_bg": "#E5BA68", "pill_fg": "#141210", "bar": "#E5BA68", "grid": "rgba(229,186,104,0.08)"},
    "bento": {"bg": "linear-gradient(135deg, #07090D 0%, #0C1018 100%)", "fg": "#F8FAFC", "accent": "#38BDF8", "pill_bg": "rgba(56,189,248,0.18)", "pill_fg": "#BAE6FD", "bar": "#38BDF8", "grid": "rgba(56,189,248,0.07)"},
    "split": {"bg": "linear-gradient(90deg, #FAF9F6 0%, #FAF9F6 54%, #6D0818 54%, #1A0307 100%)", "fg": "#111111", "accent": "#C8102E", "pill_bg": "#C8102E", "pill_fg": "#FFFFFF", "bar": "#C8102E", "grid": "rgba(0,0,0,0.04)"},
    "brutalist": {"bg": "#0A0A0A", "fg": "#FFFFFF", "accent": "#F5C518", "pill_bg": "#F5C518", "pill_fg": "#0A0A0A", "bar": "#F5C518", "grid": "rgba(245,197,24,0.07)"},
    "gallery": {"bg": "#FAF8F5", "fg": "#1A1D20", "accent": "#1E3A8A", "pill_bg": "#1E3A8A", "pill_fg": "#FFFFFF", "bar": "#1E3A8A", "grid": "rgba(30,58,138,0.05)"},
}


def build_16x9(theme_key: str, cfg: dict) -> str:
    st = THEMES_16X9[theme_key]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  @font-face {{
    font-family: "CoverBlack";
    src: url("file://{cfg['font']}");
    font-weight: 900;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: 1920px; height: 1080px; overflow: hidden;
    background: {st['bg']}; color: {st['fg']};
    font-family: "CoverBlack", "PingFang SC", "Hiragino Sans GB", sans-serif;
  }}
  .canvas {{ position: relative; width: 1920px; height: 1080px; overflow: hidden; }}
  .grid-bg {{
    position: absolute; inset: 0;
    background-image: linear-gradient({st['grid']} 1px, transparent 1px), linear-gradient(90deg, {st['grid']} 1px, transparent 1px);
    background-size: 72px 72px;
  }}
  .left {{
    position: absolute; left: 96px; top: 108px; width: 960px; z-index: 4;
    display: flex; flex-direction: column; align-items: flex-start;
  }}
  .kicker {{
    padding: 12px 28px; border-radius: 999px;
    background: {st['pill_bg']}; color: {st['pill_fg']};
    font-size: 30px; letter-spacing: 1.5px; margin-bottom: 34px;
  }}
  .line1 {{ font-size: 168px; line-height: 1.04; letter-spacing: 4px; }}
  .line2 {{ font-size: 176px; line-height: 1.04; letter-spacing: 4px; color: {st['accent']}; }}
  .rule {{ width: 680px; height: 5px; background: {st['bar']}; margin: 34px 0 24px; }}
  .meta {{ font-size: 34px; opacity: 0.9; margin-bottom: 30px; }}
  .badge-row {{
    padding: 14px 32px; border-radius: 12px; border: 2px solid {st['accent']};
    font-size: 30px;
  }}
  .portrait {{
    position: absolute; right: 60px; bottom: 0; width: 820px; height: 960px; z-index: 3;
    display: flex; align-items: flex-end; justify-content: center;
  }}
  .portrait img {{
    width: 100%; height: 100%; object-fit: contain; object-position: bottom center;
    filter: contrast(1.05) brightness(0.97) drop-shadow(-12px 0 36px rgba(0,0,0,0.35));
  }}
</style>
</head>
<body>
<div class="canvas">
  <div class="grid-bg"></div>
  <div class="left">
    <div class="kicker">{cfg['kicker']} · {cfg['issue']}</div>
    <div class="line1">{cfg['line1']}</div>
    <div class="line2">{cfg['line2']}</div>
    <div class="rule"></div>
    <div class="meta">{cfg['author']} · {cfg['stat1']}</div>
    <div class="badge-row">{cfg['channel']}</div>
  </div>
  <div class="portrait"><img src="file://{cfg['portrait']}"></div>
</div>
</body></html>"""


def main():
    p = argparse.ArgumentParser(description="汇芯系列视频 Skill 六套高格调 3:4 封面生成器")
    p.add_argument("--theme", default="all", choices=list(BUILDERS.keys()) + ["all"])
    p.add_argument("--line1", default="公众号")
    p.add_argument("--line2", default="全自动")
    p.add_argument("--kicker", default="开源 AI SKILL")
    p.add_argument("--issue", default="NO. 01")
    p.add_argument("--sub", default="把规矩写进代码<br>一个人就是编辑部")
    p.add_argument("--stat1", default="20+ 篇过万爆文")
    p.add_argument("--stat1-val", default="20+ 篇")
    p.add_argument("--stat1-lbl", default="过万与 10 万+ 爆文")
    p.add_argument("--stat2-val", default="9 步")
    p.add_argument("--stat2-lbl", default="选题到草稿箱闭环")
    p.add_argument("--stat3-val", default="1 个人")
    p.add_argument("--stat3-lbl", default="就是一支编辑部")
    p.add_argument("--author", default="袁六伟 · 台州汇芯")
    p.add_argument("--channel", default="公众号 / 视频号：袁六伟")
    p.add_argument("--repo-tag", default="wechat-autopilot · 开源系列")
    p.add_argument("--portrait", default=None)
    p.add_argument("--font", default=DEFAULT_FONT)
    p.add_argument("--out-dir", default="/Users/yuanliuwei/汇芯公众号自动化宣传片/out/cover-layouts")
    p.add_argument("--ratio", default="3:4", choices=["3:4", "16:9", "both"], help="输出画幅：3:4 独立封面 / 16:9 横屏首帧 / both")
    p.add_argument("--grid", action="store_true", help="生成 3x2 对比拼图")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "line1": args.line1,
        "line2": args.line2,
        "kicker": args.kicker,
        "issue": args.issue,
        "sub": args.sub,
        "stat1": args.stat1,
        "stat1_val": args.stat1_val,
        "stat1_lbl": args.stat1_lbl,
        "stat2_val": args.stat2_val,
        "stat2_lbl": args.stat2_lbl,
        "stat3_val": args.stat3_val,
        "stat3_lbl": args.stat3_lbl,
        "author": args.author,
        "channel": args.channel,
        "repo_tag": args.repo_tag,
        "portrait": resolve_portrait(args.portrait),
        "font": args.font,
    }

    keys = list(BUILDERS.keys()) if args.theme == "all" else [args.theme]
    rendered = []
    for k in keys:
        stem, fn = BUILDERS[k]
        if args.ratio in ("3:4", "both"):
            jpg = render_one(stem, fn(cfg), out_dir, 1080, 1440, save_png=False)
            print(f"Rendered 3:4: {jpg}")
            rendered.append(jpg)
        if args.ratio in ("16:9", "both"):
            jpg16 = render_one(f"{stem}-16x9", build_16x9(k, cfg), out_dir, 1920, 1080, save_png=True)
            print(f"Rendered 16:9: {jpg16}")

    if (args.grid or args.theme == "all") and rendered:
        cols, rows = 3, 2
        thumb_w, thumb_h = 540, 720
        pad = 24
        grid = Image.new("RGB", (cols * thumb_w + (cols + 1) * pad, rows * thumb_h + (rows + 1) * pad), (18, 18, 20))
        for idx, img_p in enumerate(rendered[:6]):
            r, c = divmod(idx, cols)
            im = Image.open(img_p).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            grid.paste(im, (pad + c * (thumb_w + pad), pad + r * (thumb_h + pad)))
        grid_path = out_dir / "00-six-layouts-grid.jpg"
        grid.save(grid_path, quality=92)
        print(f"Grid saved: {grid_path}")


if __name__ == "__main__":
    main()
