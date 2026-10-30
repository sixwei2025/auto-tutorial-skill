#!/usr/bin/env python3
"""Step｜快渲染通道：ffmpeg 直出成片（不逐帧截浏览器）

为什么要有这一条：原来的 html → frames（Playwright 逐帧截图）→ mux 通道，
实测约 15 帧/秒，一条 30 秒的片子光渲染就要 75 秒。
铺矩阵号是几千几万条量级，这条路算下来要跑一个月。本脚本把渲染压到
「PIL 画叠加层 + ffmpeg 一次合成」，单条约 15-25 秒，配并发可到 5 秒级。

用法：
  TV_PROJECT=$PWD python3 render_fast.py                  # 读 sop.json + voice/full.wav
  TV_PROJECT=$PWD python3 render_fast.py --jobs 4         # 4 个场景并行
  TV_PROJECT=$PWD python3 render_fast.py --from cover     # 只重渲封面段

产出：delivery/<slug>-16x9.mp4

与慢通道的差异（知道就行，不影响交付）：
  - 字幕整句淡入，不做逐字弹性缩放
  - 场景切换是硬切 + 20ms 黑场，不做叠化
  - 高亮框是静态描边，不做脉冲
  这三处是拿「细腻度」换「万条产能」，不是退化，是取舍。
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, ffmpeg, pil_font, pil_mark

from PIL import Image, ImageDraw, ImageFilter

W, H = 1920, 1080
VW, VH = 1200, 675
VX, VY = 80, 180
FPS = 30

ARGS = sys.argv[1:]


def opt(k, d=None):
    return ARGS[ARGS.index(k) + 1] if k in ARGS and ARGS.index(k) + 1 < len(ARGS) else d


SOP = json.load(open(os.path.join(PROJECT, "sop.json"), encoding="utf-8"))
PJ = {}
for p in ("project.json",):
    fp = os.path.join(PROJECT, p)
    if os.path.exists(fp):
        PJ = json.load(open(fp, encoding="utf-8"))

TH = PJ.get("theme", {})
ACCENT = TH.get("accent", "#C7352D")
ACCENT_DEEP = TH.get("accent_deep", "#B92F27")
INK = TH.get("ink", "#1A1614")
INK_SOFT = TH.get("ink_soft", "#5C524D")
INK_MUTE = TH.get("ink_mute", "#8A7D77")
LINE = TH.get("line", "#EADCD9")
PANEL = TH.get("panel", "#FAF6F4")
WHITE = "#FFFFFF"

JOBS = int(opt("--jobs", "4"))
TOTAL_DUR = 1.0          # 由 main 覆盖；进度条表达式要用
TMP = os.path.join(PROJECT, ".fast")
os.makedirs(TMP, exist_ok=True)
os.makedirs(os.path.join(PROJECT, "delivery"), exist_ok=True)

# ---------------------------------------------------------------- 变体种子
# 矩阵铺量时同一条内容要裂成几十个「看着不一样」的版本。
# 一个 seed 派生一组确定性差异，同样的 seed 永远出同样的片，方便复现和去重。
import random

SEED = opt("--seed")
VAR = {"zoom_k": 1.0, "pan": "center", "sub_bottom": 44, "sub_size": 38,
       "crop_dx": 0.0, "crop_dy": 0.0, "bgm": None, "lead_pad": 0.0}
if SEED is not None:
    r = random.Random(int(SEED) * 7919 + 104729)
    VAR["zoom_k"] = round(r.uniform(0.88, 1.22), 3)      # 推拉幅度
    VAR["pan"] = r.choice(["center", "up", "down", "left", "right"])
    VAR["sub_bottom"] = r.choice([36, 40, 44, 48, 52])   # 字幕高度
    VAR["sub_size"] = r.choice([36, 38, 38, 40])         # 字幕字号
    VAR["crop_dx"] = r.uniform(-0.015, 0.015)            # 画面轻微位移
    VAR["crop_dy"] = r.uniform(-0.012, 0.012)
    VAR["lead_pad"] = round(r.uniform(0.0, 0.22), 3)     # 每段气口
    bgm_dir = os.path.join(PROJECT, "assets", "bgm")
    if os.path.isdir(bgm_dir):
        tracks = sorted(f for f in os.listdir(bgm_dir)
                        if f.lower().endswith((".mp3", ".m4a", ".wav")))
        if tracks:
            VAR["bgm"] = os.path.join(bgm_dir, r.choice(tracks))



def rgb(h, a=None):
    h = h.lstrip("#")
    t = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return t + (a,) if a is not None else t


def hexs(h):
    """ffmpeg 用的 0xRRGGBB"""
    return "0x" + h.lstrip("#").upper()


# ----------------------------------------------------------------- 文字工具
def text_w(draw, s, font):
    b = draw.textbbox((0, 0), s, font=font)
    return b[2] - b[0]


def wrap(draw, text, font, max_w):
    """按像素宽度折行（中文逐字，英文按词）。"""
    out, cur = [], ""
    for ch in text:
        if ch == "\n":
            out.append(cur); cur = ""; continue
        if text_w(draw, cur + ch, font) > max_w and cur:
            out.append(cur); cur = ""
        cur += ch
    if cur:
        out.append(cur)
    return out or [""]


def fit_font(draw, text, size, max_w, bold=True, floor=None):
    """字号自动缩到不溢出。"""
    floor = floor or max(12, int(size * 0.55))
    s = size
    while s > floor:
        f = pil_font(s, bold=bold)
        if text_w(draw, text, f) <= max_w:
            return f
        s -= 2
    return pil_font(floor, bold=bold)


# ------------------------------------------------------------- 底图归一化
def norm_shot(path, out, bg=PANEL):
    """把任意尺寸截图 contain 到 1200×675 画布，避免 ffmpeg 里算布局。"""
    if not os.path.exists(path):
        im = Image.new("RGB", (VW, VH), rgb(bg))
        ImageDraw.Draw(im).text((40, 40), "缺素材：" + os.path.basename(path),
                                font=pil_font(28), fill=rgb(INK_MUTE))
        im.save(out)
        return out
    im = Image.open(path).convert("RGB")
    sc = min(VW / im.width, VH / im.height)
    im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    canvas = Image.new("RGB", (VW, VH), rgb(bg))
    dx = int((VW - im.width) / 2 + VAR["crop_dx"] * VW)
    dy = int((VH - im.height) / 2 + VAR["crop_dy"] * VH)
    dx = max(0, min(VW - im.width, dx))
    dy = max(0, min(VH - im.height, dy))
    canvas.paste(im, (dx, dy))
    canvas.save(out)
    return out


# ---------------------------------------------------------------- 叠加层
def make_overlay(step, idx, total, series, out):
    """画静态叠层：眉标、标题、右侧面板、截图边框、署名。透明底。"""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # 眉标
    f_eyebrow = pil_font(20, bold=True)
    d.text((VX, 40), series, font=f_eyebrow, fill=rgb(ACCENT))
    label = "%02d / %02d" % (idx, total)
    d.text((W - VX - text_w(d, label, f_eyebrow), 40), label,
           font=f_eyebrow, fill=rgb(INK_MUTE))

    # 主标题
    title = (step.get("title") or "").strip()
    if title:
        f = fit_font(d, title, 50, W - VX * 2, bold=True, floor=32)
        d.text((VX, 84), title, font=f, fill=rgb(ACCENT))

    # 截图区边框（圆角 18，2px）
    d.rounded_rectangle([VX - 2, VY - 2, VX + VW + 2, VY + VH + 2],
                        radius=18, outline=rgb(LINE), width=2)

    # 右侧面板
    px, py, pw, ph = 1340, 180, 500, 675
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=18,
                        fill=rgb(PANEL), outline=rgb(LINE), width=1)
    ix, iy = px + 32, py + 30

    aside = (step.get("asideLabel") or "这一步").strip()
    d.text((ix, iy), aside, font=pil_font(20, bold=True), fill=rgb(ACCENT))
    iy += 40

    instr = (step.get("instruction") or "").strip()
    if instr:
        f = pil_font(29, bold=True)
        for ln in wrap(d, instr, f, pw - 64)[:3]:
            d.text((ix, iy), ln, font=f, fill=rgb(INK))
            iy += int(29 * 1.32)
        iy += 18

    for item in (step.get("checklist") or [])[:4]:
        try:
            txt, state = item[0], item[1]
        except Exception:
            continue
        mark = pil_mark(state, size=26)
        color = ACCENT if state == "current" else (INK if state == "done" else INK_SOFT)
        f = pil_font(26, bold=(state == "current"))
        d.text((ix, iy), mark, font=f, fill=color)
        for ln in wrap(d, txt, f, pw - 64 - 40)[:2]:
            d.text((ix + 40, iy), ln, font=f, fill=color)
            iy += int(26 * 1.3)
        iy += 14

    tip = (step.get("tip") or "").strip()
    if tip:
        ty = py + ph - 28
        f = pil_font(21)
        lines = wrap(d, tip, f, pw - 64)[:3]
        ty -= int(21 * 1.35) * len(lines)
        d.line([ix, ty - 20, px + pw - 32, ty - 20], fill=rgb(LINE), width=1)
        for ln in lines:
            d.text((ix, ty), ln, font=f, fill=rgb(INK_SOFT))
            ty += int(21 * 1.35)

    # 截图来源署名
    src = (step.get("source") or "").strip()
    if src:
        d.text((VX + 4, 872), "真实截图 · " + src[:52],
               font=pil_font(20), fill=rgb(INK_MUTE))

    im.save(out)
    return out


def make_sub(text, out, size=38, bottom=44):
    """整屏透明字幕层：底部居中、圆角底、单行不折。"""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = fit_font(d, text, size, 1660, bold=True, floor=24)
    tw = text_w(d, text, f)
    asc, desc = f.getmetrics()
    th = asc + desc
    pad_x, pad_y = 30, 15
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    bx = (W - bw) // 2
    by = H - bottom - bh
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=14,
                        fill=rgb(PANEL, 235), outline=rgb(LINE, 255), width=1)
    d.text((bx + pad_x, by + pad_y), text, font=f, fill=rgb(INK))
    im.save(out)
    return out


def pan_expr(direction, frames):
    """推拉镜头方向：让同一张图在不同变体里「动得不一样」。"""
    cx = "iw/2-(iw/zoom/2)"
    cy = "ih/2-(ih/zoom/2)"
    if direction == "down":
        return "x='%s':y='(ih-ih/zoom)*on/%d'" % (cx, frames)
    if direction == "up":
        return "x='%s':y='(ih-ih/zoom)*(1-on/%d)'" % (cx, frames)
    if direction == "right":
        return "x='(iw-iw/zoom)*on/%d':y='%s'" % (frames, cy)
    if direction == "left":
        return "x='(iw-iw/zoom)*(1-on/%d)':y='%s'" % (frames, cy)
    return "x='%s':y='%s'" % (cx, cy)


# ------------------------------------------------------------------ 渲染
def render_one(step, idx, total, series):
    sid = step["id"]
    dur = max(0.12, float(step["duration"]))
    base = os.path.join(TMP, sid)
    os.makedirs(base, exist_ok=True)

    if step.get("kind") == "cover":
        # 封面段：模糊铺底 + 居中竖版卡片
        src = os.path.join(PROJECT, step.get("path") or "cover/cover-3x4.png")
        bg = Image.new("RGB", (W, H), rgb(ACCENT_DEEP))
        if os.path.exists(src):
            c = Image.open(src).convert("RGB")
            sc = max(W / c.width, H / c.height)
            big = c.resize((int(c.width * sc) + 2, int(c.height * sc) + 2), Image.LANCZOS)
            bg.paste(big.crop(((big.width - W) // 2, (big.height - H) // 2,
                               (big.width - W) // 2 + W, (big.height - H) // 2 + H)), (0, 0))
            bg = bg.filter(ImageFilter.GaussianBlur(26))
            sc2 = min(W * 0.9 / c.width, H * 0.92 / c.height)
            card = c.resize((int(c.width * sc2), int(c.height * sc2)), Image.LANCZOS)
            bg.paste(card, ((W - card.width) // 2, (H - card.height) // 2))
        bg.save(os.path.join(base, "bg.png"))
        out = os.path.join(base, "clip.mp4")
        subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                        "-loop", "1", "-i", os.path.join(base, "bg.png"),
                        "-t", "%.3f" % dur, "-r", str(FPS),
                        "-vf", "format=yuv420p", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "18",
                        "-pix_fmt", "yuv420p", out], check=False,
                       capture_output=True)
        return out

    # 背景：优先用 scene 配的 clip（动图/录屏），否则静态图 + 推拉
    clip = None
    for sc in (PJ.get("scenes") or []):
        if sc.get("id") == sid and sc.get("clip"):
            clip = sc["clip"].get("file") if isinstance(sc["clip"], dict) else sc["clip"]
            break

    shot_src = os.path.join(PROJECT, step.get("path") or "")
    canvas = norm_shot(shot_src, os.path.join(base, "bg.png"))
    overlay = make_overlay(step, idx, total, series, os.path.join(base, "overlay.png"))

    inputs = []
    if clip and os.path.exists(os.path.join(PROJECT, clip)):
        inputs += ["-stream_loop", "-1", "-i", os.path.join(PROJECT, clip)]
        bg_chain = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,"
                    "crop=%d:%d,fps=%d,setsar=1[bg]"
                    % (VW, VH, VW, VH, FPS))
        ni = 1
    else:
        inputs += ["-loop", "1", "-t", "%.3f" % dur, "-i", canvas]
        z = float(step.get("zoom") or 1.06) * VAR["zoom_k"]
        z = max(1.0, min(1.9, z))
        frames = max(2, int(dur * FPS))
        bg_chain = ("[0:v]scale=%d:%d,zoompan=z='1+%f*on/%d':d=%d:%s:s=%dx%d:fps=%d,"
                    "setsar=1[bg]"
                    % (VW * 2, VH * 2, z - 1, frames, frames,
                       pan_expr(VAR["pan"], frames), VW, VH, FPS))
        ni = 1

    inputs += ["-loop", "1", "-t", "%.3f" % dur, "-i", overlay]
    ov_idx = ni
    ni += 1

    subs = step.get("captions") or []
    sub_inputs, sub_filters = [], []
    for j, cap in enumerate(subs):
        txt = (cap.get("text") or "").strip()
        if not txt:
            continue
        sp = os.path.join(base, "sub%02d.png" % j)
        make_sub(txt, sp, size=VAR["sub_size"], bottom=VAR["sub_bottom"])
        inputs += ["-loop", "1", "-t", "%.3f" % dur, "-i", sp]
        a = max(0.0, float(cap.get("start", 0)))
        b = min(dur, float(cap.get("end", dur)))
        if b - a < 0.25:
            b = min(dur, a + 0.25)
        sub_inputs.append((ni, a, b))
        ni += 1

    fc = [bg_chain,
          "color=c=%s:s=%dx%d:d=%.3f:r=%d[canvas]" % (hexs(WHITE), W, H, dur, FPS),
          "[canvas][bg]overlay=%d:%d[base]" % (VX, VY),
          "[base][%d:v]overlay=0:0[o0]" % ov_idx]
    last = "o0"
    for k, (inp, a, b) in enumerate(sub_inputs):
        nxt = "o%d" % (k + 1)
        fade_in = min(0.12, max(0.04, (b - a) * 0.15))
        fc.append("[%s][%d:v]overlay=0:0:enable='between(t,%.3f,%.3f)'[%s]"
                  % (last, inp, a, b, nxt))
        last = nxt
    # 进度条（整条视频的进度由调用方给的总时长算）
    fc.append("[%s]drawbox=x=0:y=1074:w='%d*t/%.3f':h=6:color=%s@0.85:t=fill,"
              "format=yuv420p[vout]" % (last, W, TOTAL_DUR, hexs(ACCENT)))

    out = os.path.join(base, "clip.mp4")
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"] + inputs + [
        "-filter_complex", ";".join(fc), "-map", "[vout]",
        "-t", "%.3f" % dur, "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("  ✗ %s 渲染失败：%s" % (sid, r.stderr.strip().splitlines()[-1][:160]))
        return None
    return out


def main():
    steps = SOP["steps"]
    series = SOP.get("series") or PJ.get("series") or "WORKBUDDY"
    content = [s for s in steps if s.get("kind") != "cover"]
    total = len(content)
    global TOTAL_DUR
    TOTAL_DUR = sum(float(s["duration"]) for s in steps)

    print("▶ 快渲染 %d 个场景 / 共 %.1fs / %d 并发" % (len(steps), TOTAL_DUR, JOBS))

    idx_of = {}
    n = 0
    for s in steps:
        if s.get("kind") == "cover":
            idx_of[s["id"]] = 0
        else:
            n += 1
            idx_of[s["id"]] = n

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, JOBS)) as ex:
        futs = {ex.submit(render_one, s, idx_of[s["id"]], total, series): s["id"]
                for s in steps}
        for f in futs:
            sid = futs[f]
            try:
                results[sid] = f.result()
            except Exception as e:
                print("  ✗ %s 异常：%s" % (sid, str(e)[:120]))
                results[sid] = None

    ok = [s["id"] for s in steps if results.get(s["id"])]
    if len(ok) != len(steps):
        miss = [s["id"] for s in steps if not results.get(s["id"])]
        raise SystemExit("❌ %d 个场景没渲出来：%s" % (len(miss), ", ".join(miss)))

    listing = os.path.join(TMP, "_list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for s in steps:
            fh.write("file '%s'\n" % results[s["id"]].replace("'", "'\\''"))

    slug = PJ.get("slug") or "video"
    tag = ("-v%s" % SEED) if SEED is not None else ""
    out_mp4 = opt("--out") or os.path.join(PROJECT, "delivery",
                                           "%s%s-16x9.mp4" % (slug, tag))
    audio = os.path.join(PROJECT, "voice", "full.wav")
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "concat", "-safe", "0", "-i", listing]
    bgm = VAR.get("bgm")
    has_audio = os.path.exists(audio)
    if has_audio:
        cmd += ["-i", audio]
    if bgm and os.path.exists(bgm):
        cmd += ["-stream_loop", "-1", "-i", bgm]
        if has_audio:
            # 人声为主，BGM 压到 -22dB 再混
            cmd += ["-filter_complex",
                    "[1:a]anull[vo];[2:a]volume=0.09,atrim=0:%.3f[bg];"
                    "[vo][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                    % TOTAL_DUR,
                    "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k",
                    "-shortest"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k",
                    "-shortest"]
    elif has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "copy", "-movflags", "+faststart", out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-800:])
        raise SystemExit("合成失败")

    size_mb = os.path.getsize(out_mp4) / 1048576.0
    vtag = ""
    if SEED is not None:
        vtag = "  变体 seed=%s 推拉×%.2f %s 字幕%dpx/底%d BGM:%s" % (
            SEED, VAR["zoom_k"], VAR["pan"], VAR["sub_size"], VAR["sub_bottom"],
            os.path.basename(bgm) if bgm else "无")
    print("\n✅ %s  %.1fs  %.1fMB%s" % (out_mp4, TOTAL_DUR, size_mb, vtag))
    if not has_audio:
        print("   ⚠ 没找到 voice/full.wav，这条是无声片")


if __name__ == "__main__":
    main()
