#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇芯视频封面工坊 (huixin-video-cover) · 6 套高审美视频封面渲染引擎

支持 6 套截然不同的视觉风格（融合小红书高赞知识博主美学，每种类型至少 2 套专属方案）：
  1. brand-red-editorial   : 汇芯红 · 杂志细体人像大字报（宣传片 / 口播）
  2. ink-dabin-sandbox     : 宣纸墨韵 · 大冰印章沙盘风（教程 / 宣传片 / 文哲）
  3. nyt-editorial-folio   : 纽约客 · 文艺留白刊风（心理科普 / 文哲 / 人物传记）
  4. xhs-kraft-bookcard    : 牛皮纸手账 · 书页大字报风（人物传记 / 文哲 / 心理科普 / 口播）
  5. xhs-apple-notes       : 小红书备忘录 · 荧光笔划重点+拍立得风（教程 / 口播 / 心理科普）
  6. xhs-vintage-newspaper : 复古报纸 · 手账纸胶带拼贴风（3D地图 / 心理科普 / 文哲 / 人物传记）

每次渲染同步产出：
  - <preset>_3x4.jpg (1080x1440)
  - <preset>_16x9_opening.png (1920x1080, 中央 810x1080 为 3:4 安全区)
"""
from __future__ import annotations

import argparse
import base64
import html
import os
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORTRAIT = ROOT / "assets" / "owner_cutout_hd.png"
BRUSH_FONT_PATH = ROOT / "assets" / "fonts" / "MaShanZheng-Regular.ttf"

PRESETS = [
    "watercolor-brush-editorial",
    "brand-red-editorial",
    "xhs-whitepaper-index",
    "ink-dabin-sandbox",
    "xhs-blue-metric-split",
    "nyt-editorial-folio",
    "xhs-vintage-newspaper",
    "vibe-obsidian-gold",
    "vibe-neon-data",
    "blueprint-schematic",
    "minimal-bigtype-red",
    "geo-topo-expedition",
    "literary-serif-quote",
    "ui-spotlight-zoom",
    "before-after-split",
    "biography-archive",
]

VIDEO_TYPE_MAP = {
    "Vibe知识": ["vibe-obsidian-gold", "vibe-neon-data", "blueprint-schematic", "xhs-whitepaper-index"],
    "宣传片": ["minimal-bigtype-red", "watercolor-brush-editorial", "before-after-split", "ui-spotlight-zoom", "brand-red-editorial"],
    "教程": ["watercolor-brush-editorial", "ui-spotlight-zoom", "before-after-split", "xhs-blue-metric-split", "blueprint-schematic"],
    "口播": ["watercolor-brush-editorial", "minimal-bigtype-red", "before-after-split", "xhs-blue-metric-split", "brand-red-editorial"],
    "心理科普": ["xhs-whitepaper-index", "vibe-obsidian-gold", "literary-serif-quote", "nyt-editorial-folio"],
    "3D地图": ["geo-topo-expedition", "ink-dabin-sandbox", "xhs-vintage-newspaper", "blueprint-schematic"],
    "人物传记": ["biography-archive", "literary-serif-quote", "xhs-vintage-newspaper", "nyt-editorial-folio"],
    "文哲": ["literary-serif-quote", "biography-archive", "xhs-whitepaper-index", "ink-dabin-sandbox"],
    "实验室": ["ui-spotlight-zoom", "blueprint-schematic", "vibe-neon-data", "vibe-obsidian-gold"],
    "其他": ["vibe-obsidian-gold", "before-after-split", "minimal-bigtype-red", "xhs-whitepaper-index"],
}


def ensure_cutout_portrait(path: str | Path | None) -> Path | None:
    """Enforce transparent cutout portrait: if input lacks alpha transparency, segment with macOS Vision or fallback to DEFAULT_PORTRAIT."""
    if not path:
        return DEFAULT_PORTRAIT if DEFAULT_PORTRAIT.exists() else None
    p = Path(path)
    if not p.exists():
        return DEFAULT_PORTRAIT if DEFAULT_PORTRAIT.exists() else None
    try:
        im = Image.open(p)
        if im.mode in ("RGBA", "LA") and im.getextrema()[-1][0] < 250:
            return p
        # Auto-segment person on macOS using Vision VNGeneratePersonSegmentationRequest
        import io, tempfile
        import Vision
        from Quartz import CIImage, CIContext
        from Foundation import NSURL
        req = Vision.VNGeneratePersonSegmentationRequest.alloc().init()
        req.setQualityLevel_(Vision.VNGeneratePersonSegmentationRequestQualityLevelAccurate)
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(p)), None)
        ok, _ = handler.performRequests_error_([req], None)
        if ok and req.results():
            mask_buf = req.results()[0].pixelBuffer()
            ci_mask = CIImage.imageWithCVPixelBuffer_(mask_buf)
            ctx = CIContext.context()
            from Quartz import kCIFormatRGBA8
            cg_mask = ctx.createCGImage_fromRect_(ci_mask, ci_mask.extent())
            import Quartz
            w_m = Quartz.CGImageGetWidth(cg_mask)
            h_m = Quartz.CGImageGetHeight(cg_mask)
            # Save mask via NSBitmapImageRep
            from AppKit import NSBitmapImageRep, NSPNGFileType
            rep = NSBitmapImageRep.alloc().initWithCGImage_(cg_mask)
            png_data = rep.representationUsingType_properties_(NSPNGFileType, None)
            mask_im = Image.open(io.BytesIO(bytes(png_data))).convert("L").resize(im.size, Image.Resampling.LANCZOS)
            rgba = im.convert("RGBA")
            rgba.putalpha(mask_im)
            out_tmp = Path(tempfile.gettempdir()) / f"{p.stem}_cutout.png"
            rgba.save(out_tmp)
            return out_tmp
    except Exception:
        pass
    return DEFAULT_PORTRAIT if DEFAULT_PORTRAIT.exists() else p


def img_to_data_uri(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    ext = p.suffix.lower().lstrip(".")
    mime = "image/png" if ext == "png" else "image/jpeg"
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def build_html(
    preset: str,
    title_top: str,
    title_accent: str,
    kicker: str,
    subtitle: str,
    metric: str,
    stamp: str,
    left_pain: str,
    right_gain: str,
    portrait_uri: str,
    screen_uri: str,
    subject_uri: str = "",
) -> str:
    t1 = esc(title_top)
    t2 = esc(title_accent)
    kick = esc(kicker)
    sub = esc(subtitle)
    met = esc(metric)
    stp = esc(stamp)
    pain = esc(left_pain)
    gain = esc(right_gain)

    base_css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body {
      width: 1080px; height: 1440px; overflow: hidden;
      font-family: "PingFang SC", "Noto Sans SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    .canvas { position: relative; width: 1080px; height: 1440px; overflow: hidden; }
    """

    if preset == "brand-red-editorial":
        body = f"""
        <div class="canvas p1">
          <div class="top-bar"></div>
          <div class="kicker"><span class="sq"></span>{kick}</div>
          <h1 class="h1-dark">{t1}</h1>
          <h1 class="h1-red">{t2}</h1>
          <div class="red-rule"></div>
          <div class="sub">{sub}</div>
          {f'<img class="portrait" src="{portrait_uri}"/>' if portrait_uri else ''}
          <div class="footer">
            <span>{stp} · 实战精选</span>
            <span>7000+ 学员 · 100+ 企业商单</span>
          </div>
        </div>
        """
        css = """
        .p1 { background: #FAF7F2; color: #16161A; }
        .top-bar { height: 16px; width: 100%; background: #C8102E; }
        .kicker { position: absolute; top: 82px; left: 72px; font-size: 28px; color: #52525B; font-weight: 500; display: flex; align-items: center; gap: 14px; }
        .kicker .sq { width: 14px; height: 14px; background: #C8102E; display: inline-block; }
        .h1-dark { position: absolute; top: 186px; left: 68px; right: 68px; font-size: 116px; font-weight: 300; line-height: 1.1; font-family: "Songti SC", "Noto Serif SC", serif; letter-spacing: -1px; }
        .h1-red { position: absolute; top: 326px; left: 68px; right: 68px; font-size: 116px; font-weight: 400; line-height: 1.1; font-family: "Songti SC", "Noto Serif SC", serif; color: #C8102E; letter-spacing: -1px; }
        .red-rule { position: absolute; top: 486px; left: 72px; width: 120px; height: 6px; background: #C8102E; }
        .sub { position: absolute; top: 520px; left: 72px; right: 440px; font-size: 32px; line-height: 1.45; color: #6B7280; font-weight: 400; }
        .portrait { position: absolute; right: 16px; bottom: 56px; height: 740px; width: auto; object-fit: contain; z-index: 2; }
        .footer { position: absolute; left: 72px; right: 72px; bottom: 0; height: 78px; border-top: 1.5px solid #E5DFD5; display: flex; align-items: center; justify-content: space-between; font-size: 24px; color: #6B7280; background: #FAF7F2; z-index: 3; }
        """

    elif preset == "ink-dabin-sandbox":
        body = f"""
        <div class="canvas p2">
          <div class="ink-wash"></div>
          <div class="header-row">
            <div class="seal">{stp}</div>
            <div class="kicker-ink">{kick}</div>
          </div>
          <h1 class="h1-ink">{t1}<br/><span class="red">{t2}</span></h1>
          <div class="card-3d">
            {f'<img src="{screen_uri}"/>' if screen_uri else '<div class="mock-ui">工作台实拍画面</div>'}
          </div>
          <div class="bottom-bar">
            {f'<img class="mini-ava" src="{portrait_uri}"/>' if portrait_uri else ''}
            <div class="bottom-txt">{sub}</div>
          </div>
        </div>
        """
        css = """
        .p2 { background: radial-gradient(circle at 50% 35%, #F5F1E9 0%, #EAE2D3 65%, #DDD3C0 100%); color: #16161A; }
        .ink-wash { position: absolute; top: -120px; right: -120px; width: 640px; height: 640px; border-radius: 50%; background: radial-gradient(circle, rgba(20,20,24,0.10) 0%, rgba(20,20,24,0) 70%); }
        .header-row { position: absolute; top: 78px; left: 72px; right: 72px; display: flex; align-items: center; gap: 22px; }
        .seal { background: #C8102E; color: #fff; font-size: 40px; font-weight: 900; padding: 12px 26px; border-radius: 12px; box-shadow: 0 12px 24px rgba(200,16,46,0.28); }
        .kicker-ink { font-size: 30px; font-weight: 700; color: #4A4A52; letter-spacing: 2px; }
        .h1-ink { position: absolute; top: 196px; left: 72px; right: 72px; font-size: 102px; font-weight: 900; line-height: 1.15; letter-spacing: 1px; }
        .h1-ink .red { color: #C8102E; }
        .card-3d { position: absolute; top: 486px; left: 72px; right: 72px; height: 630px; border-radius: 24px; border: 4px solid #18181D; overflow: hidden; background: #18181D; box-shadow: 0 36px 70px rgba(20,20,24,0.28); transform: perspective(1000px) rotateX(4deg) rotateY(-3deg); }
        .card-3d img { width: 100%; height: 100%; object-fit: cover; object-position: top center; }
        .mock-ui { color: #fff; font-size: 42px; display: flex; align-items: center; justify-content: center; height: 100%; }
        .bottom-bar { position: absolute; left: 72px; right: 72px; bottom: 72px; height: 148px; background: #18181D; border-radius: 22px; border-left: 10px solid #C8102E; display: flex; align-items: center; padding: 0 34px; gap: 26px; box-shadow: 0 24px 48px rgba(0,0,0,0.25); }
        .mini-ava { width: 104px; height: 104px; border-radius: 50%; object-fit: cover; object-position: top center; border: 3px solid #C8102E; background: #FAF7F2; }
        .bottom-txt { color: #FAF7F2; font-size: 34px; font-weight: 800; line-height: 1.35; }
        """

    elif preset == "xhs-whitepaper-index":
        body = f"""
        <div class="canvas p3">
          <div class="wp-top">COLLECTION · {met} WORKFLOWS · 2026</div>
          <div class="wp-kicker">{kick}</div>
          <h1 class="h1-wp">{t1}<br/><span>{t2}</span></h1>
          <div class="wp-italic">A field guide for building automated content pipelines.</div>
          <div class="wp-quote-box">{sub}</div>
          <div class="wp-index">
            <div class="wp-row"><span>01</span><b>全网热点抓取与撞题查重</b><em>01 / TOPIC</em></div>
            <div class="wp-row"><span>02</span><b>多端语气出稿与自动排版</b><em>02 / WRITE</em></div>
            <div class="wp-row"><span>03</span><b>封面校验与矩阵一键入队</b><em>03 / LAUNCH</em></div>
          </div>
          <div class="wp-foot"><span>COMPLETE SERIES</span><span>THINKING TOOLKIT</span></div>
        </div>
        """
        css = """
        .p3 { background: #FAFAF9; color: #1E1E1E; padding: 72px 80px; display: flex; flex-direction: column; justify-content: space-between; }
        .wp-top { text-align: center; font-size: 18px; letter-spacing: 3px; color: #A1A1AA; border-bottom: 1px solid #E4E4E7; padding-bottom: 18px; }
        .wp-kicker { text-align: center; font-size: 24px; color: #71717A; margin-top: 12px; font-weight: 500; }
        .h1-wp { text-align: center; font-family: "Songti SC", "Noto Serif SC", serif; font-size: 98px; font-weight: 900; line-height: 1.22; color: #18181B; margin: 18px 0; }
        .h1-wp span { color: #C8102E; }
        .wp-italic { text-align: center; font-family: Georgia, serif; font-style: italic; font-size: 24px; color: #71717A; }
        .wp-quote-box { margin: 26px auto; width: 82%; background: #F4F4F5; border-radius: 14px; padding: 26px 34px; text-align: center; font-size: 28px; color: #3F3F46; line-height: 1.5; font-weight: 600; }
        .wp-index { display: flex; flex-direction: column; gap: 20px; border-top: 1.5px solid #E4E4E7; padding-top: 28px; }
        .wp-row { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #F4F4F5; padding-bottom: 16px; font-size: 28px; }
        .wp-row span { font-family: Georgia, serif; color: #A1A1AA; font-size: 26px; width: 54px; }
        .wp-row b { flex: 1; font-weight: 700; color: #27272A; }
        .wp-row em { font-style: normal; font-size: 18px; letter-spacing: 2px; color: #A1A1AA; }
        .wp-foot { display: flex; justify-content: space-between; font-size: 18px; letter-spacing: 3px; color: #A1A1AA; border-top: 1px solid #E4E4E7; padding-top: 18px; }
        """

    elif preset == "xhs-blue-metric-split":
        body = f"""
        <div class="canvas p4">
          <div class="bm-head">
            <h1 class="h1-bm">{t1}<br/><span class="blue-hl">{met} 技能</span> {t2}</h1>
            <svg class="bm-underline" viewBox="0 0 600 40" fill="none">
              <path d="M10 28 Q 260 4 590 22" stroke="#1D4ED8" stroke-width="10" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="bm-card">
            <div class="bm-dots"><i></i><i></i><i></i><span>{stp} · {kick}</span></div>
            <div class="bm-screen">{f'<img src="{screen_uri}"/>' if screen_uri else ''}</div>
          </div>
          {f'<img class="bm-portrait" src="{portrait_uri}"/>' if portrait_uri else ''}
          <div class="bm-pill">{sub}</div>
        </div>
        """
        css = """
        .p4 { background: #FFFFFF; color: #09090B; }
        .bm-head { position: absolute; top: 82px; left: 68px; right: 68px; }
        .h1-bm { font-size: 98px; font-weight: 900; line-height: 1.18; letter-spacing: -1px; color: #09090B; }
        .blue-hl { color: #1D4ED8; }
        .bm-underline { width: 520px; height: 34px; margin-top: 8px; display: block; }
        .bm-card {
          position: absolute; left: 68px; bottom: 168px; width: 610px; height: 700px;
          background: #0F172A; border-radius: 30px; overflow: hidden;
          border: 4px solid #09090B; box-shadow: 0 28px 56px rgba(15,23,42,0.18);
          display: flex; flex-direction: column;
        }
        .bm-dots { height: 54px; background: #1E293B; display: flex; align-items: center; padding: 0 22px; gap: 10px; color: #94A3B8; font-size: 20px; font-weight: 700; }
        .bm-dots i { width: 12px; height: 12px; border-radius: 50%; background: #EF4444; display: inline-block; }
        .bm-dots i:nth-child(2) { background: #F59E0B; }
        .bm-dots i:nth-child(3) { background: #10B981; }
        .bm-screen { flex: 1; overflow: hidden; }
        .bm-screen img { width: 100%; height: 100%; object-fit: cover; object-position: top left; }
        .bm-portrait { position: absolute; right: -24px; bottom: 0; height: 790px; width: auto; object-fit: contain; z-index: 3; }
        .bm-pill {
          position: absolute; left: 68px; bottom: 64px; background: #EFF6FF; border: 2.5px solid #1D4ED8;
          color: #1E3A8A; font-size: 28px; font-weight: 800; padding: 16px 30px; border-radius: 18px; z-index: 4;
        }
        """

    elif preset == "xhs-vintage-newspaper":
        body = f"""
        <div class="canvas p5">
          <div class="news-bg">
            <div class="news-masthead">
              <span>THE HUIXIN DAILY</span>
              <span>VOL. 2026 · NO. 01</span>
              <span>{stp}特刊</span>
            </div>
            <div class="news-columns">
              <p>PRACTICAL AI AUTOMATION WORKFLOW · VERIFIED BY 7000+ STUDENTS AND 100+ ENTERPRISE CLIENTS ACROSS 20 INDUSTRIES.</p>
              <p>SOLO CREATOR TO FULL CONTENT TEAM · REAL SCREENSHOTS · ZERO PLASTIC AI TONE · HUMAN IN THE LOOP.</p>
            </div>
          </div>
          <div class="memo-card">
            <div class="washi-tape"></div>
            <div class="memo-kicker">{kick}</div>
            <h1 class="h1-news">{t1}<br/><span class="red-circle">{t2}</span></h1>
            <div class="memo-sub">{sub}</div>
            <div class="memo-foot">
              <div class="seal-ava">{f'<img src="{portrait_uri}"/>' if portrait_uri else ''}</div>
              <div class="foot-meta"><b>{stp} · 深度实测</b><span>{met} 实战验证</span></div>
            </div>
          </div>
        </div>
        """
        css = """
        .p5 { background: #EAE2D0; color: #292524; }
        .news-bg { position: absolute; inset: 48px; border-top: 5px solid #292524; border-bottom: 5px solid #292524; padding: 28px 0; opacity: 0.55; }
        .news-masthead { display: flex; justify-content: space-between; font-family: "Songti SC", "Noto Serif SC", serif; font-size: 28px; font-weight: 900; letter-spacing: 2px; border-bottom: 2px solid #292524; padding-bottom: 18px; }
        .news-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 36px; margin-top: 26px; font-size: 20px; line-height: 1.7; font-family: Georgia, serif; color: #57534E; }
        .memo-card {
          position: absolute; left: 84px; right: 84px; top: 260px; bottom: 110px;
          background-color: #FAF7F0;
          background-image: linear-gradient(to right, rgba(41,37,36,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(41,37,36,0.06) 1px, transparent 1px);
          background-size: 48px 48px;
          border: 2.5px solid #292524; border-radius: 6px; padding: 84px 64px 56px;
          box-shadow: 0 36px 72px rgba(41,37,36,0.22); transform: rotate(-1.2deg);
          display: flex; flex-direction: column; justify-content: space-between;
        }
        .washi-tape {
          position: absolute; top: -30px; left: 50%; transform: translateX(-50%) rotate(2deg);
          width: 260px; height: 58px; background: rgba(200,16,46,0.78);
          box-shadow: 0 6px 14px rgba(0,0,0,0.12);
        }
        .memo-kicker { font-size: 28px; font-weight: 700; color: #78716C; letter-spacing: 2px; }
        .h1-news { font-family: "Songti SC", "Noto Serif SC", serif; font-size: 98px; font-weight: 900; line-height: 1.18; color: #1C1917; }
        .red-circle { color: #C8102E; border-bottom: 6px solid #C8102E; padding-bottom: 4px; }
        .memo-sub { font-size: 34px; font-weight: 700; line-height: 1.5; color: #44403C; background: #EFE8D8; padding: 24px 30px; border-left: 8px solid #C8102E; }
        .memo-foot { display: flex; align-items: center; gap: 24px; border-top: 2px dashed #A8A29E; padding-top: 28px; }
        .seal-ava { width: 120px; height: 120px; border-radius: 50%; overflow: hidden; border: 3px solid #292524; background: #EDE6D9; display: flex; align-items: flex-end; justify-content: center; }
        .seal-ava img { height: 96%; width: auto; object-fit: contain; }
        .foot-meta { display: flex; flex-direction: column; gap: 8px; }
        .foot-meta b { font-size: 34px; font-weight: 900; }
        .foot-meta span { font-size: 26px; font-weight: 700; color: #C8102E; }
        """

    elif preset == "nyt-editorial-folio":
        body = f"""
        <div class="canvas p4">
          <div class="folio-frame">
            <div class="folio-top"><span>ISSUE · 2026</span><span>{kick}</span><span>{stp}</span></div>
            <h1 class="h1-nyt">{t1}<br/><span class="red">{t2}</span></h1>
            <div class="folio-mid">
              <div class="folio-img">
                {f'<img src="{portrait_uri}"/>' if portrait_uri else (f'<img src="{screen_uri}"/>' if screen_uri else '')}
              </div>
              <div class="folio-side">
                <div class="side-num">{met}</div>
                <div class="side-cap">HUIXIN<br/>EDITORIAL<br/>ARCHIVE</div>
              </div>
            </div>
            <div class="folio-quote">“{sub}”</div>
          </div>
        </div>
        """
        css = """
        .p4 { background: #F2EFE8; color: #18181B; padding: 48px; }
        .folio-frame { width: 100%; height: 100%; border: 2px solid #18181B; position: relative; padding: 44px; display: flex; flex-direction: column; justify-content: space-between; }
        .folio-top { display: flex; justify-content: space-between; font-size: 24px; font-weight: 700; letter-spacing: 3px; border-bottom: 1.5px solid #18181B; padding-bottom: 18px; }
        .h1-nyt { font-family: "Songti SC", "Noto Serif SC", serif; font-size: 96px; font-weight: 700; line-height: 1.15; margin-top: 12px; }
        .h1-nyt .red { color: #C8102E; }
        .folio-mid { display: flex; gap: 28px; height: 740px; align-items: stretch; }
        .folio-img { flex: 1; background: linear-gradient(180deg, #EDE6D9 0%, #DFD6C5 100%); border: 1.5px solid #18181B; overflow: hidden; display: flex; align-items: flex-end; justify-content: center; }
        .folio-img img { height: 96%; width: auto; object-fit: contain; filter: saturate(1.06) brightness(1.02); }
        .folio-side { width: 180px; border: 1.5px solid #18181B; padding: 24px 16px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; text-align: center; }
        .side-num { font-size: 46px; font-weight: 900; color: #C8102E; }
        .side-cap { font-size: 20px; font-weight: 700; letter-spacing: 3px; line-height: 1.8; color: #52525B; }
        .folio-quote { border-top: 1.5px solid #18181B; padding-top: 24px; font-size: 34px; font-weight: 600; font-family: "Songti SC", "Noto Serif SC", serif; color: #27272A; }
        """

    elif preset == "vibe-obsidian-gold":
        body = f"""
        <div class="canvas vibe-gold">
          <div class="vg-grid"></div>
          <div class="vg-glow"></div>
          <div class="vg-top">
            <span class="vg-pill"><span class="vg-dot"></span>{kick}</span>
            <span class="vg-tag">{stp}</span>
          </div>
          <div class="vg-main">
            <div class="vg-t1">{t1}</div>
            <div class="vg-t2">{t2}</div>
            <div class="vg-sub">{sub}</div>
          </div>
          <div class="vg-diagram">
            <div class="vg-node active"><span>01</span>直觉钩子</div>
            <div class="vg-line"></div>
            <div class="vg-node"><span>02</span>逻辑推导</div>
            <div class="vg-line"></div>
            <div class="vg-node accent"><span>{met}</span>结论破局</div>
          </div>
        </div>
        """
        css = """
        .vibe-gold { background: radial-gradient(circle at 50% 30%, #141722 0%, #07080B 100%); color: #F4F1EA; padding: 76px 68px; display: flex; flex-direction: column; justify-content: space-between; }
        .vg-grid { position: absolute; inset: 0; background-image: linear-gradient(to right, rgba(245,184,65,0.07) 1px, transparent 1px), linear-gradient(to bottom, rgba(245,184,65,0.07) 1px, transparent 1px); background-size: 64px 64px; }
        .vg-glow { position: absolute; top: 180px; left: 50%; transform: translateX(-50%); width: 780px; height: 520px; background: radial-gradient(circle, rgba(245,184,65,0.18), transparent 70%); pointer-events: none; }
        .vg-top { position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; }
        .vg-pill { display: inline-flex; align-items: center; gap: 12px; padding: 12px 24px; border-radius: 999px; border: 1.5px solid rgba(245,184,65,0.45); background: rgba(245,184,65,0.08); font-size: 24px; font-weight: 700; color: #F5B841; letter-spacing: 2px; }
        .vg-dot { width: 12px; height: 12px; border-radius: 50%; background: #F5B841; }
        .vg-tag { font-size: 24px; font-weight: 700; color: #8E95A5; letter-spacing: 3px; }
        .vg-main { position: relative; z-index: 2; margin-top: 40px; }
        .vg-t1 { font-size: 92px; font-weight: 900; line-height: 1.12; color: #F4F1EA; letter-spacing: -1px; }
        .vg-t2 { font-size: 98px; font-weight: 900; line-height: 1.14; color: #F5B841; margin-top: 16px; }
        .vg-sub { margin-top: 38px; font-size: 34px; line-height: 1.5; color: #9CA3AF; font-weight: 500; border-left: 5px solid #F5B841; padding-left: 24px; }
        .vg-diagram { position: relative; z-index: 2; display: flex; align-items: center; justify-content: space-between; padding: 34px 30px; border-radius: 24px; background: rgba(255,255,255,0.04); border: 1.5px solid rgba(245,184,65,0.3); }
        .vg-node { display: flex; flex-direction: column; align-items: center; gap: 10px; font-size: 24px; font-weight: 700; color: #D1D5DB; }
        .vg-node span { font-size: 32px; font-weight: 900; color: #F5B841; }
        .vg-node.accent span { color: #E85D4A; }
        .vg-line { flex: 1; height: 3px; background: linear-gradient(90deg, rgba(245,184,65,0.3), #F5B841, rgba(245,184,65,0.3)); margin: 0 18px; }
        """

    elif preset == "vibe-neon-data":
        dots = "".join(
            f'<span class="vn-d {"hot" if (i * 7) % 11 == 0 else ("cyan" if i % 3 == 0 else "")}"></span>'
            for i in range(96)
        )
        body = f"""
        <div class="canvas vibe-neon">
          <div class="vn-top">
            <span class="vn-kicker">{kick}</span>
            <span class="vn-metric">{met}</span>
          </div>
          <div class="vn-title">
            <div class="vn-t1">{t1}</div>
            <div class="vn-t2">{t2}</div>
          </div>
          <div class="vn-matrix">{dots}</div>
          <div class="vn-bottom">
            <div class="vn-pain">✕ {pain}</div>
            <div class="vn-gain">✓ {gain}</div>
          </div>
        </div>
        """
        css = """
        .vibe-neon { background: radial-gradient(circle at 30% 20%, #0D1B38 0%, #050914 100%); color: #EAF6FF; padding: 72px 68px; display: flex; flex-direction: column; justify-content: space-between; }
        .vn-top { display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid rgba(0,240,255,0.22); padding-bottom: 24px; }
        .vn-kicker { font-size: 26px; font-weight: 800; color: #00F0FF; letter-spacing: 3px; }
        .vn-metric { font-size: 40px; font-weight: 900; color: #FF3B5C; font-family: "SF Mono", monospace; }
        .vn-t1 { font-size: 86px; font-weight: 900; line-height: 1.12; color: #FFFFFF; }
        .vn-t2 { font-size: 90px; font-weight: 900; line-height: 1.15; color: #00F0FF; margin-top: 12px; }
        .vn-matrix { display: grid; grid-template-columns: repeat(12, 1fr); gap: 18px; padding: 34px; border-radius: 22px; background: rgba(0,240,255,0.04); border: 1.5px solid rgba(0,240,255,0.25); }
        .vn-d { width: 18px; height: 18px; border-radius: 50%; background: rgba(122,147,184,0.28); justify-self: center; }
        .vn-d.cyan { background: #00F0FF; box-shadow: 0 0 12px rgba(0,240,255,0.7); }
        .vn-d.hot { background: #FF3B5C; box-shadow: 0 0 14px rgba(255,59,92,0.85); transform: scale(1.25); }
        .vn-bottom { display: flex; flex-direction: column; gap: 14px; font-size: 28px; font-weight: 700; }
        .vn-pain { color: #FF7A90; }
        .vn-gain { color: #00F0FF; }
        """

    elif preset == "blueprint-schematic":
        body = f"""
        <div class="canvas bp-wrap">
          <div class="bp-frame">
            <div class="bp-head">
              <span>[ CAD · {stp} ]</span>
              <span>{kick}</span>
            </div>
            <div class="bp-title">
              <div class="bp-t1">{t1}</div>
              <div class="bp-t2">{t2}</div>
            </div>
            <div class="bp-box">
              {f'<img src="{screen_uri}" class="bp-screen" />' if screen_uri else '<div class="bp-wave"><svg viewBox="0 0 800 180" width="100%" height="180"><path d="M0,90 Q80,10 160,90 T320,90 T480,90 T640,90 T800,90" fill="none" stroke="#38BDF8" stroke-width="5"/><path d="M0,90 Q80,150 160,90 T320,90 T480,90 T640,90 T800,90" fill="none" stroke="#FBBF24" stroke-width="3" stroke-dasharray="10 8"/></svg></div>'}
            </div>
            <div class="bp-foot">
              <span>CORE: {met}</span>
              <span>{sub}</span>
            </div>
          </div>
        </div>
        """
        css = """
        .bp-wrap { background: #0A1628; background-image: linear-gradient(to right, rgba(56,189,248,0.12) 1px, transparent 1px), linear-gradient(to bottom, rgba(56,189,248,0.12) 1px, transparent 1px); background-size: 48px 48px; padding: 54px; color: #F0F7FF; }
        .bp-frame { height: 100%; border: 2.5px solid rgba(56,189,248,0.65); padding: 44px; display: flex; flex-direction: column; justify-content: space-between; background: rgba(10,22,40,0.72); }
        .bp-head { display: flex; justify-content: space-between; font-family: "SF Mono", monospace; font-size: 24px; font-weight: 700; color: #38BDF8; letter-spacing: 2px; }
        .bp-t1 { font-size: 86px; font-weight: 900; line-height: 1.12; color: #FFFFFF; }
        .bp-t2 { font-size: 86px; font-weight: 900; line-height: 1.15; color: #FBBF24; margin-top: 12px; }
        .bp-box { border: 2px dashed rgba(56,189,248,0.55); border-radius: 16px; padding: 28px; min-height: 360px; display: flex; align-items: center; justify-content: center; background: rgba(16,34,61,0.85); }
        .bp-screen { max-width: 100%; max-height: 340px; object-fit: contain; border-radius: 10px; }
        .bp-wave { width: 100%; }
        .bp-foot { display: flex; flex-direction: column; gap: 10px; font-size: 26px; color: #93C5FD; font-weight: 600; border-top: 1.5px solid rgba(56,189,248,0.35); padding-top: 24px; }
        """

    elif preset == "minimal-bigtype-red":
        body = f"""
        <div class="canvas mb-red">
          <div class="mb-top">
            <span class="mb-badge">{kick}</span>
            <span class="mb-num">{met}</span>
          </div>
          <div class="mb-hero">
            <div class="mb-t1">{t1}</div>
            <div class="mb-t2">{t2}</div>
          </div>
          <div class="mb-card">
            <div class="mb-row"><span class="mb-dot"></span>{sub}</div>
            <div class="mb-row"><span class="mb-dot"></span>{gain}</div>
          </div>
        </div>
        """
        css = """
        .mb-red { background: #101116; color: #FFFFFF; padding: 78px 68px; display: flex; flex-direction: column; justify-content: space-between; }
        .mb-top { display: flex; justify-content: space-between; align-items: center; }
        .mb-badge { background: #C8102E; color: #FFFFFF; padding: 12px 26px; border-radius: 8px; font-size: 26px; font-weight: 800; letter-spacing: 2px; }
        .mb-num { font-size: 52px; font-weight: 900; color: #C8102E; }
        .mb-t1 { font-size: 104px; font-weight: 900; line-height: 1.1; color: #FFFFFF; letter-spacing: -2px; }
        .mb-t2 { font-size: 108px; font-weight: 900; line-height: 1.12; color: #C8102E; margin-top: 18px; letter-spacing: -2px; }
        .mb-card { background: #1A1C24; border-left: 8px solid #C8102E; border-radius: 16px; padding: 34px 36px; display: flex; flex-direction: column; gap: 20px; }
        .mb-row { display: flex; align-items: center; gap: 16px; font-size: 30px; font-weight: 600; color: #E5E7EB; line-height: 1.4; }
        .mb-dot { width: 12px; height: 12px; border-radius: 50%; background: #C8102E; flex-shrink: 0; }
        """

    elif preset == "geo-topo-expedition":
        body = f"""
        <div class="canvas geo-topo">
          <svg class="gt-rings" viewBox="0 0 1080 1440"><circle cx="540" cy="820" r="210" fill="none" stroke="rgba(245,158,11,0.22)" stroke-width="2"/><circle cx="540" cy="820" r="340" fill="none" stroke="rgba(96,165,250,0.18)" stroke-width="2" stroke-dasharray="12 10"/><circle cx="540" cy="820" r="470" fill="none" stroke="rgba(245,158,11,0.14)" stroke-width="2"/></svg>
          <div class="gt-hud">
            <span>LAT 28.65°N · LON 121.42°E</span>
            <span>{stp}</span>
          </div>
          <div class="gt-center">
            <div class="gt-kicker">{kick}</div>
            <div class="gt-t1">{t1}</div>
            <div class="gt-t2">{t2}</div>
          </div>
          <div class="gt-bottom">
            <div class="gt-stat">{met}</div>
            <div class="gt-sub">{sub}</div>
          </div>
        </div>
        """
        css = """
        .geo-topo { background: radial-gradient(circle at 50% 60%, #0E1B33 0%, #04070E 100%); color: #F8FAFC; padding: 74px 68px; display: flex; flex-direction: column; justify-content: space-between; }
        .gt-rings { position: absolute; inset: 0; width: 1080px; height: 1440px; pointer-events: none; }
        .gt-hud { position: relative; z-index: 2; display: flex; justify-content: space-between; font-family: "SF Mono", monospace; font-size: 22px; color: #60A5FA; letter-spacing: 2px; border-bottom: 1px solid rgba(96,165,250,0.3); padding-bottom: 20px; }
        .gt-center { position: relative; z-index: 2; }
        .gt-kicker { font-size: 28px; font-weight: 700; color: #F59E0B; letter-spacing: 3px; margin-bottom: 22px; }
        .gt-t1 { font-size: 92px; font-weight: 900; line-height: 1.12; color: #FFFFFF; }
        .gt-t2 { font-size: 94px; font-weight: 900; line-height: 1.14; color: #60A5FA; margin-top: 14px; }
        .gt-bottom { position: relative; z-index: 2; padding: 30px 34px; border-radius: 20px; background: rgba(15,23,42,0.82); border: 1.5px solid rgba(245,158,11,0.45); display: flex; align-items: center; gap: 28px; }
        .gt-stat { font-size: 54px; font-weight: 900; color: #F59E0B; white-space: nowrap; }
        .gt-sub { font-size: 28px; color: #CBD5E1; line-height: 1.45; }
        """

    elif preset == "literary-serif-quote":
        body = f"""
        <div class="canvas lit-quote">
          <div class="lq-top">
            <span class="lq-kicker">{kick}</span>
            <span class="lq-seal">{stp}</span>
          </div>
          <div class="lq-body">
            <div class="lq-mark">“</div>
            <div class="lq-t1">{t1}</div>
            <div class="lq-t2">{t2}</div>
          </div>
          <div class="lq-foot">
            <div class="lq-line"></div>
            <div class="lq-sub">{sub}</div>
          </div>
        </div>
        """
        css = """
        .lit-quote { background: #F5F0E6; color: #1A1917; padding: 82px 74px; display: flex; flex-direction: column; justify-content: space-between; font-family: "Songti SC", "Noto Serif SC", serif; }
        .lq-top { display: flex; justify-content: space-between; align-items: center; }
        .lq-kicker { font-size: 26px; font-weight: 700; color: #6B655B; letter-spacing: 4px; font-family: "PingFang SC", sans-serif; }
        .lq-seal { width: 84px; height: 84px; border: 4px solid #C82829; color: #C82829; display: flex; align-items: center; justify-content: center; font-size: 30px; font-weight: 900; border-radius: 6px; }
        .lq-mark { font-size: 160px; line-height: 0.7; color: #C82829; font-weight: 900; margin-bottom: 18px; }
        .lq-t1 { font-size: 88px; font-weight: 900; line-height: 1.18; color: #1A1917; }
        .lq-t2 { font-size: 88px; font-weight: 900; line-height: 1.18; color: #C82829; margin-top: 14px; }
        .lq-line { width: 140px; height: 5px; background: #1A1917; margin-bottom: 24px; }
        .lq-sub { font-size: 32px; line-height: 1.5; color: #4B4740; font-family: "PingFang SC", sans-serif; font-weight: 500; }
        """

    elif preset == "ui-spotlight-zoom":
        body = f"""
        <div class="canvas ui-zoom">
          <div class="uz-top">
            <span class="uz-pill">{kick}</span>
            <span class="uz-badge">{stp}</span>
          </div>
          <div class="uz-title">
            <div class="uz-t1">{t1}</div>
            <div class="uz-t2">{t2}</div>
          </div>
          <div class="uz-stage">
            {f'<img src="{screen_uri}" class="uz-img" />' if screen_uri else '<div class="uz-mock"><div class="uz-mock-bar"><span></span><span></span><span></span></div><div class="uz-mock-body">WORKSPACE · LIVE DEMO</div></div>'}
            <div class="uz-reticle"><span>{met}</span></div>
          </div>
          <div class="uz-sub">{sub}</div>
        </div>
        """
        css = """
        .ui-zoom { background: radial-gradient(circle at 50% 25%, #161922 0%, #090A0F 100%); color: #FFFFFF; padding: 72px 64px; display: flex; flex-direction: column; justify-content: space-between; }
        .uz-top { display: flex; justify-content: space-between; align-items: center; }
        .uz-pill { background: rgba(200,16,46,0.18); border: 1.5px solid #C8102E; color: #FF6B81; padding: 10px 22px; border-radius: 999px; font-size: 24px; font-weight: 700; letter-spacing: 2px; }
        .uz-badge { font-size: 24px; font-weight: 800; color: #9CA3AF; letter-spacing: 3px; }
        .uz-t1 { font-size: 86px; font-weight: 900; line-height: 1.12; color: #FFFFFF; }
        .uz-t2 { font-size: 90px; font-weight: 900; line-height: 1.14; color: #FF4D6D; margin-top: 12px; }
        .uz-stage { position: relative; border-radius: 22px; overflow: hidden; border: 2px solid rgba(255,255,255,0.16); background: #131620; height: 500px; display: flex; align-items: center; justify-content: center; box-shadow: 0 30px 70px rgba(0,0,0,0.65); transform: perspective(1200px) rotateX(2deg); }
        .uz-img { width: 100%; height: 100%; object-fit: cover; filter: brightness(0.88); }
        .uz-mock { width: 90%; height: 82%; border-radius: 14px; border: 1px solid rgba(255,255,255,0.14); background: #1C202E; display: flex; flex-direction: column; }
        .uz-mock-bar { display: flex; gap: 10px; padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,0.08); }
        .uz-mock-bar span { width: 14px; height: 14px; border-radius: 50%; background: #4B5563; }
        .uz-mock-body { flex: 1; display: flex; align-items: center; justify-content: center; font-family: "SF Mono", monospace; font-size: 28px; color: #6B7280; letter-spacing: 4px; }
        .uz-reticle { position: absolute; right: 56px; bottom: 52px; width: 250px; height: 150px; border: 5px solid #C8102E; border-radius: 16px; background: rgba(200,16,46,0.18); box-shadow: 0 0 0 8px rgba(200,16,46,0.22), 0 18px 40px rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; }
        .uz-reticle span { font-size: 46px; font-weight: 900; color: #FFFFFF; text-shadow: 0 2px 10px rgba(0,0,0,0.6); }
        .uz-sub { font-size: 30px; color: #D1D5DB; font-weight: 500; border-left: 5px solid #C8102E; padding-left: 22px; line-height: 1.45; }
        """

    elif preset == "before-after-split":
        body = f"""
        <div class="canvas ba-wrap">
          <div class="ba-head">
            <span class="ba-kicker">{kick}</span>
            <div class="ba-title">{t1} <span>{t2}</span></div>
          </div>
          <div class="ba-cols">
            <div class="ba-col before">
              <div class="ba-tag">BEFORE · 过去</div>
              <div class="ba-text">{pain}</div>
            </div>
            <div class="ba-vs">{met}</div>
            <div class="ba-col after">
              <div class="ba-tag">AFTER · 现在</div>
              <div class="ba-text">{gain}</div>
            </div>
          </div>
          <div class="ba-foot">{sub}</div>
        </div>
        """
        css = """
        .ba-wrap { background: #0C0E14; color: #FFFFFF; padding: 72px 60px; display: flex; flex-direction: column; justify-content: space-between; }
        .ba-kicker { display: inline-block; font-size: 24px; font-weight: 800; color: #9CA3AF; letter-spacing: 3px; margin-bottom: 18px; }
        .ba-title { font-size: 82px; font-weight: 900; line-height: 1.15; color: #FFFFFF; }
        .ba-title span { color: #FF3B5C; display: block; margin-top: 8px; }
        .ba-cols { position: relative; display: grid; grid-template-columns: 1fr 1fr; gap: 22px; height: 580px; }
        .ba-col { border-radius: 24px; padding: 42px 34px; display: flex; flex-direction: column; justify-content: space-between; }
        .ba-col.before { background: #1A1D26; border: 2px solid #2E3342; color: #9CA3AF; }
        .ba-col.after { background: linear-gradient(160deg, #C8102E 0%, #7F091D 100%); border: 2px solid #FF5C77; color: #FFFFFF; }
        .ba-tag { font-size: 24px; font-weight: 800; letter-spacing: 2px; opacity: 0.9; }
        .ba-text { font-size: 46px; font-weight: 800; line-height: 1.32; }
        .ba-vs { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); background: #F5B841; color: #0A0A0C; padding: 18px 28px; border-radius: 999px; font-size: 36px; font-weight: 900; box-shadow: 0 12px 36px rgba(0,0,0,0.65); white-space: nowrap; border: 4px solid #0C0E14; }
        .ba-foot { font-size: 28px; color: #D1D5DB; text-align: center; font-weight: 600; padding-top: 12px; }
        """

    elif preset == "biography-archive":
        subj = subject_uri or screen_uri
        body = f"""
        <div class="canvas bio-arc">
          <div class="bio-top">
            <span>ARCHIVE · {stp}</span>
            <span>{met}</span>
          </div>
          <div class="bio-photo-box">
            {f'<img src="{subj}" class="bio-photo" />' if subj else '<div class="bio-monogram">人物档案</div>'}
          </div>
          <div class="bio-text">
            <div class="bio-kicker">{kick}</div>
            <div class="bio-t1">{t1}</div>
            <div class="bio-t2">{t2}</div>
            <div class="bio-sub">{sub}</div>
          </div>
        </div>
        """
        css = """
        .bio-arc { background: #141210; color: #F2ECE1; padding: 72px 68px; display: flex; flex-direction: column; justify-content: space-between; font-family: "Songti SC", "Noto Serif SC", serif; }
        .bio-top { display: flex; justify-content: space-between; font-family: "SF Mono", monospace; font-size: 24px; color: #C59B5F; letter-spacing: 3px; border-bottom: 1.5px solid rgba(197,155,95,0.35); padding-bottom: 20px; }
        .bio-photo-box { height: 500px; border: 2px solid rgba(197,155,95,0.4); border-radius: 14px; overflow: hidden; background: #1E1B18; display: flex; align-items: center; justify-content: center; }
        .bio-photo { width: 100%; height: 100%; object-fit: cover; filter: grayscale(0.85) contrast(1.12); }
        .bio-monogram { font-size: 64px; font-weight: 900; color: rgba(197,155,95,0.35); letter-spacing: 14px; }
        .bio-kicker { font-size: 24px; color: #C59B5F; letter-spacing: 4px; font-family: "PingFang SC", sans-serif; font-weight: 700; margin-bottom: 14px; }
        .bio-t1 { font-size: 82px; font-weight: 900; line-height: 1.14; color: #F7F3EA; }
        .bio-t2 { font-size: 82px; font-weight: 900; line-height: 1.14; color: #C59B5F; margin-top: 8px; }
        .bio-sub { margin-top: 22px; font-size: 28px; color: #B8B0A2; font-family: "PingFang SC", sans-serif; line-height: 1.45; }
        """

    elif preset == "watercolor-brush-editorial":
        import re as _re
        def _fmt_brush(s: str) -> str:
            return _re.sub(r"([A-Za-z0-9.+★%×/-]+)", r'<span class="wc-latin">\1</span>', s)

        t1_html = _fmt_brush(t1)
        t2_html = _fmt_brush(t2)
        font_file = BRUSH_FONT_PATH if BRUSH_FONT_PATH.exists() else Path.home() / ".agents/skills/huixin-video-cover/assets/fonts/MaShanZheng-Regular.ttf"
        font_uri = font_file.as_uri() if font_file.exists() else ""
        t1_len = len(title_top)
        t2_len = len(title_accent)
        t1_size = 138 if t1_len <= 7 else (120 if t1_len <= 10 else 98)
        t2_size = 118 if t2_len <= 7 else (102 if t2_len <= 10 else 84)

        if subject_uri:
            scene_html = f'<div class="wc-scene-custom"><img src="{subject_uri}" alt="scene"/></div>'
        elif screen_uri:
            scene_html = f"""
            <div class="wc-scene-tutorial">
              <div class="wc-screen-card">
                <div class="wc-screen-dots"><span></span><span></span><span></span></div>
                <img src="{screen_uri}" alt="screen"/>
              </div>
              <svg class="wc-arrow-svg" viewBox="0 0 180 120" fill="none">
                <path d="M18 92 C 55 32, 110 24, 152 46" stroke="#E55A17" stroke-width="8" stroke-linecap="round" stroke-dasharray="10 8"/>
                <path d="M132 28 L158 48 L130 62" stroke="#E55A17" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              {f'<img class="wc-portrait-side" src="{portrait_uri}" alt="portrait"/>' if portrait_uri else ''}
            </div>
            """
        else:
            scene_html = f"""
            <div class="wc-scene-portrait">
              <svg class="wc-metaphor-bg" viewBox="0 0 1080 860" fill="none">
                <!-- Soft watercolor skyline / enterprise silhouette in slate blue -->
                <g opacity="0.24" filter="url(#wcWash)">
                  <rect x="70" y="340" width="90" height="220" fill="#244B73"/>
                  <rect x="175" y="280" width="110" height="280" fill="#3B6B99"/>
                  <rect x="790" y="290" width="115" height="270" fill="#3B6B99"/>
                  <rect x="920" y="350" width="95" height="210" fill="#244B73"/>
                </g>
                <!-- Painterly watercolor arches & growth strokes behind shoulders -->
                <path d="M40 620 C 160 490, 260 470, 340 530" stroke="#E55A17" stroke-width="14" stroke-linecap="round" opacity="0.45" filter="url(#roughEdge)"/>
                <path d="M740 530 C 820 470, 920 490, 1040 620" stroke="#244B73" stroke-width="12" stroke-linecap="round" opacity="0.42" filter="url(#roughEdge)"/>
                <!-- Left & right sketch cards placed cleanly at shoulder/chest level -->
                <g transform="translate(55, 505) rotate(-5)">
                  <rect width="210" height="135" rx="14" fill="rgba(255,253,248,0.88)" stroke="#244B73" stroke-width="4.5"/>
                  <line x1="26" y1="42" x2="184" y2="42" stroke="#244B73" stroke-width="6" stroke-linecap="round"/>
                  <line x1="26" y1="74" x2="148" y2="74" stroke="#E55A17" stroke-width="6" stroke-linecap="round"/>
                  <line x1="26" y1="104" x2="115" y2="104" stroke="#244B73" stroke-width="5" stroke-linecap="round" opacity="0.5"/>
                </g>
                <g transform="translate(805, 495) rotate(4)">
                  <rect width="215" height="140" rx="14" fill="rgba(255,253,248,0.88)" stroke="#244B73" stroke-width="4.5"/>
                  <path d="M32 106 L78 68 L122 86 L180 34" stroke="#E55A17" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
                  <circle cx="180" cy="34" r="9" fill="#E55A17"/>
                </g>
              </svg>
              {f'<img class="wc-portrait-main" src="{portrait_uri}" alt="portrait"/>' if portrait_uri else ''}
            </div>
            """

        body = f"""
        <div class="canvas wc-cover">
          <!-- Watercolor paper texture + organic rough-edged washes -->
          <svg class="wc-bg-svg" viewBox="0 0 1080 1440" preserveAspectRatio="none">
            <defs>
              <filter id="roughEdge" x="-20%" y="-20%" width="140%" height="140%">
                <feTurbulence type="fractalNoise" baseFrequency="0.022" numOctaves="4" result="noise"/>
                <feDisplacementMap in="SourceGraphic" in2="noise" scale="24" xChannelSelector="R" yChannelSelector="G"/>
              </filter>
              <filter id="wcWash" x="-30%" y="-30%" width="160%" height="160%">
                <feTurbulence type="fractalNoise" baseFrequency="0.015" numOctaves="4" result="noise"/>
                <feDisplacementMap in="SourceGraphic" in2="noise" scale="48" xChannelSelector="R" yChannelSelector="G"/>
                <feGaussianBlur stdDeviation="22"/>
              </filter>
              <filter id="paperGrain">
                <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/>
                <feColorMatrix type="matrix" values="0 0 0 0 0.4  0 0 0 0 0.3  0 0 0 0 0.2  0 0 0 0.05 0"/>
              </filter>
            </defs>
            <!-- Organic watercolor blotches along margins -->
            <g filter="url(#wcWash)">
              <path d="M-40 -20 Q 220 20 180 180 Q 110 260 -40 210 Z" fill="#EB651E" opacity="0.45"/>
              <path d="M880 -30 Q 1120 -10 1110 220 Q 940 240 850 120 Z" fill="#244B73" opacity="0.40"/>
              <path d="M-50 740 Q 170 820 140 1120 Q 40 1240 -50 1160 Z" fill="#244B73" opacity="0.42"/>
              <path d="M930 780 Q 1130 820 1120 1240 Q 920 1280 880 1020 Z" fill="#EB651E" opacity="0.46"/>
              <path d="M40 1290 Q 340 1260 440 1470 L -40 1470 Z" fill="#EB651E" opacity="0.38"/>
              <path d="M640 1310 Q 920 1260 1120 1470 L 580 1470 Z" fill="#244B73" opacity="0.36"/>
            </g>
            <!-- Crisp dry-brush splatters -->
            <g filter="url(#roughEdge)" opacity="0.65">
              <circle cx="78" cy="220" r="10" fill="#E55A17"/>
              <circle cx="108" cy="248" r="5" fill="#244B73"/>
              <circle cx="990" cy="235" r="11" fill="#244B73"/>
              <circle cx="955" cy="268" r="6" fill="#E55A17"/>
              <path d="M35 310 L95 290" stroke="#E55A17" stroke-width="6" stroke-linecap="round"/>
              <path d="M995 340 L1045 325" stroke="#244B73" stroke-width="6" stroke-linecap="round"/>
            </g>
            <!-- Subtle cold-press paper texture overlay -->
            <rect width="1080" height="1440" filter="url(#paperGrain)"/>
          </svg>

          <!-- Top Title Zone -->
          <div class="wc-header">
            <div class="wc-sparks">
              <svg width="280" height="36" viewBox="0 0 280 36" fill="none">
                <path d="M36 28 L20 8 M140 24 L140 4 M244 28 L260 8" stroke="#E55A17" stroke-width="5.5" stroke-linecap="round"/>
                <path d="M76 30 L68 14 M204 30 L212 14" stroke="#244B73" stroke-width="4.5" stroke-linecap="round"/>
              </svg>
            </div>
            <h1 class="wc-t1" style="font-size:{t1_size}px;">{t1_html}</h1>
            <div class="wc-accent-wrap">
              <svg class="wc-brush-swipe" viewBox="0 0 920 185" preserveAspectRatio="none">
                <path d="M24 34 C 190 12, 720 10, 894 28 C 916 32, 918 134, 890 148 C 720 168, 210 170, 30 152 C 8 148, 6 38, 24 34 Z" fill="#E55A17" filter="url(#roughEdge)"/>
                <path d="M42 20 C 240 6, 680 8, 862 18" stroke="#F49342" stroke-width="6" stroke-linecap="round" opacity="0.55"/>
              </svg>
              <div class="wc-t2" style="font-size:{t2_size}px;">{t2_html}</div>
            </div>
          </div>

          <!-- Bottom Visual Scene -->
          {scene_html}
        </div>
        """
        font_face = f"""
        @font-face {{
          font-family: "HuixinBrush";
          src: url("{font_uri}") format("truetype");
          font-weight: normal;
          font-style: normal;
        }}
        """ if font_uri else ""
        css = font_face + """
        .wc-cover {
          background: #F6F0E4;
          position: relative;
        }
        .wc-bg-svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; }
        .wc-header {
          position: relative; z-index: 5;
          padding: 76px 52px 0;
          display: flex; flex-direction: column; align-items: center; text-align: center;
        }
        .wc-sparks { margin-bottom: 6px; }
        .wc-t1 {
          font-family: "HuixinBrush", "Songti SC", "Noto Serif SC", serif;
          color: #16202E;
          line-height: 1.1;
          letter-spacing: 3px;
          text-shadow: 0 3px 0 rgba(255,255,255,0.85);
          max-width: 970px;
          word-break: keep-all;
        }
        .wc-latin {
          font-family: "Noto Sans SC", "PingFang SC", "Arial Black", sans-serif;
          font-weight: 900;
          letter-spacing: 0px;
          font-size: 0.86em;
          display: inline-block;
          vertical-align: baseline;
          margin: 0 3px;
        }
        .wc-accent-wrap {
          position: relative;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          margin-top: 14px;
          padding: 20px 60px 24px;
          transform: rotate(-1.4deg);
        }
        .wc-brush-swipe {
          position: absolute;
          inset: -6px -22px;
          width: calc(100% + 44px);
          height: calc(100% + 12px);
          z-index: 1;
        }
        .wc-t2 {
          position: relative; z-index: 2;
          font-family: "HuixinBrush", "Songti SC", "Noto Serif SC", serif;
          color: #FFFDF9;
          line-height: 1.06;
          letter-spacing: 3px;
          text-shadow: 0 3px 10px rgba(120,30,0,0.38);
          white-space: nowrap;
        }
        .wc-scene-portrait {
          position: absolute; left: 0; right: 0; bottom: 0; height: 860px; z-index: 3;
          display: flex; align-items: flex-end; justify-content: center;
        }
        .wc-metaphor-bg {
          position: absolute; inset: 0; width: 100%; height: 100%; z-index: 1;
        }
        .wc-portrait-main {
          position: relative; z-index: 2;
          height: 820px; width: auto; object-fit: contain;
          filter: saturate(0.95) contrast(1.06) sepia(0.08);
          -webkit-mask-image: linear-gradient(to top, transparent 0%, black 14%, black 100%);
          mask-image: linear-gradient(to top, transparent 0%, black 14%, black 100%);
        }
        .wc-scene-tutorial {
          position: absolute; left: 0; right: 0; bottom: 0; height: 860px; z-index: 3;
        }
        .wc-screen-card {
          position: absolute; left: 52px; top: 100px; width: 700px; height: 470px;
          background: #FFFDF8;
          border: 5px solid #244B73;
          border-radius: 20px;
          box-shadow: 12px 16px 0 rgba(229,90,23,0.22), 0 18px 40px rgba(22,32,46,0.14);
          overflow: hidden;
          transform: rotate(-1.6deg);
          z-index: 2;
        }
        .wc-screen-dots {
          height: 36px; background: #244B73; display: flex; align-items: center; gap: 8px; padding: 0 16px;
        }
        .wc-screen-dots span { width: 11px; height: 11px; border-radius: 50%; background: rgba(255,253,248,0.65); }
        .wc-screen-dots span:first-child { background: #E55A17; }
        .wc-screen-card img { width: 100%; height: calc(100% - 36px); object-fit: cover; }
        .wc-arrow-svg { position: absolute; left: 480px; top: 36px; width: 180px; height: 120px; z-index: 4; }
        .wc-portrait-side {
          position: absolute; right: 10px; bottom: 0; height: 730px; width: auto; object-fit: contain; z-index: 3;
          filter: saturate(0.95) contrast(1.06) sepia(0.08);
          -webkit-mask-image: linear-gradient(to top, transparent 0%, black 14%, black 100%);
          mask-image: linear-gradient(to top, transparent 0%, black 14%, black 100%);
        }
        .wc-scene-custom {
          position: absolute; left: 20px; right: 20px; bottom: 16px; height: 870px; z-index: 3;
          display: flex; align-items: center; justify-content: center;
        }
        .wc-scene-custom img {
          width: 100%; height: 100%; object-fit: contain;
          -webkit-mask-image: radial-gradient(ellipse 90% 88% at 50% 54%, black 66%, transparent 99%);
          mask-image: radial-gradient(ellipse 90% 88% at 50% 54%, black 66%, transparent 99%);
        }
        """

    return f"<!doctype html><html><head><meta charset='utf-8'><style>{base_css}{css}</style></head><body>{body}</body></html>"


def render_preset(preset: str, out_dir: Path, args: argparse.Namespace) -> tuple[Path, Path]:
    cutout_p = ensure_cutout_portrait(args.portrait)
    portrait_uri = img_to_data_uri(cutout_p)
    screen_uri = img_to_data_uri(args.screen)
    subject_uri = img_to_data_uri(getattr(args, "subject", ""))
    html_doc = build_html(
        preset=preset,
        title_top=args.title_top,
        title_accent=args.title_accent,
        kicker=args.kicker,
        subtitle=args.subtitle,
        metric=args.metric,
        stamp=args.stamp,
        left_pain=args.pain,
        right_gain=args.gain,
        portrait_uri=portrait_uri,
        screen_uri=screen_uri,
        subject_uri=subject_uri,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    png_3x4 = out_dir / f"{preset}_3x4.png"
    jpg_3x4 = out_dir / f"{preset}_3x4.jpg"
    png_16x9 = out_dir / f"{preset}_16x9_opening.png"

    tmp_html = out_dir / f"._{preset}_render.html"
    tmp_html.write_text(html_doc, encoding="utf-8")
    try:
        with sync_playwright() as p:
            chrome_candidates = [
                "/Users/yuanliuwei/.cache/hypit/html-rasterizer/chrome/chrome-headless-shell/mac_arm-152.0.7928.2/chrome-headless-shell-mac-arm64/chrome-headless-shell",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ]
            exe = next((c for c in chrome_candidates if Path(c).exists()), None)
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": 1080, "height": 1440}, device_scale_factor=1)
            page.goto(tmp_html.as_uri(), wait_until="load")
            page.evaluate("() => document.fonts.ready")
            page.screenshot(path=str(png_3x4))
            browser.close()
    finally:
        if tmp_html.exists():
            tmp_html.unlink()

    # Convert to JPG + build 1920x1080 opening frame with central 810x1080 safe zone
    im = Image.open(png_3x4).convert("RGB")
    im.save(jpg_3x4, quality=93)

    bg_color = (10, 10, 12)
    canvas_16x9 = Image.new("RGB", (1920, 1080), bg_color)
    resized = im.resize((810, 1080), Image.Resampling.LANCZOS)
    canvas_16x9.paste(resized, ((1920 - 810) // 2, 0))
    canvas_16x9.save(png_16x9)
    return jpg_3x4, png_16x9


def main() -> None:
    parser = argparse.ArgumentParser(description="汇芯视频封面工坊 · 12 套赛道适配封面生成器（含无露脸视觉与人像）")
    parser.add_argument("--preset", choices=PRESETS, default="")
    parser.add_argument("--video-type", choices=list(VIDEO_TYPE_MAP.keys()), default="", help="按视频赛道自动选型")
    parser.add_argument("--variant", type=int, default=0, help="同赛道下的第 N 套封面方案 (0, 1, 2, ...)")
    parser.add_argument("--render-all", action="store_true", help="一次渲染全部风格（或指定 --video-type 下的全部方案）")
    parser.add_argument("--title-top", default="汇芯爆款工作台")
    parser.add_argument("--title-accent", default="全自动内容获客")
    parser.add_argument("--kicker", default="一人公司自动化引擎")
    parser.add_argument("--subtitle", default="50+ 实战技能 · 15 款 AI 工具 · 1 分钟跑通闭环")
    parser.add_argument("--metric", default="50+")
    parser.add_argument("--stamp", default="实战")
    parser.add_argument("--pain", default="17个AI工具乱成一锅粥，天天手动复制改排版")
    parser.add_argument("--gain", default="四字闭环直接一人成队")
    parser.add_argument("--portrait", default=str(DEFAULT_PORTRAIT))
    parser.add_argument("--screen", default="")
    parser.add_argument("--subject", default="", help="外部人物传记主角照片路径（不影响本人头像）")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out)
    if args.render_all:
        targets = VIDEO_TYPE_MAP[args.video_type] if args.video_type else PRESETS
    elif args.preset:
        targets = [args.preset]
    elif args.video_type:
        pool = VIDEO_TYPE_MAP[args.video_type]
        targets = [pool[args.variant % len(pool)]]
    else:
        targets = ["minimal-bigtype-red"]

    for p in targets:
        jpg, opening = render_preset(p, out_dir, args)
        print(f"OK [{p}] -> {jpg} | {opening}")


if __name__ == "__main__":
    main()
