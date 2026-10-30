#!/usr/bin/env python3
"""Step 0｜渲染 3:4 竖版封面（海报式模板 + 品牌色）

🔴 封面文案铁律（2026-10-30 袁总拍板）：
   封面**最多两行文字**。3:4 在列表里就那么一小格，字数一多谁也看不清。
   顶部小标 / 序号 / 副标 / 底部脚注默认全部不渲染，只有两行大字 + 主图。
   真需要附加文字，显式设 `cover.extra_text: true`，但要自己承担变难看的后果。

用法：TV_PROJECT=/path/to/project python3 make_cover.py
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import launch_browser
from playwright.sync_api import sync_playwright

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
CFG = json.load(open(os.path.join(PROJECT, "project.json")))
C = CFG.get("cover", {})

OUT = os.path.join(PROJECT, C.get("output", "cover/cover-3x4.png"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)

MAX_LINES = int(C.get("max_lines", 2))

# ---------------------------------------------------------------- 顶部红胶囊
# 视频号风格（2026-10-30）：品牌词进胶囊标，两行大字就能全部留给钩子，
# 不用再牺牲一行写 WorkBuddy。胶囊里的品牌词同样算「封面出现 WorkBuddy」。
BADGE = str(C.get("badge", "WorkBuddy实操")).strip()
if C.get("badge") is False or BADGE.lower() in ("", "none", "off", "false"):
    BADGE = ""
BADGE_BG = C.get("badge_bg", "#E5392F")
has_badge = bool(BADGE)
badge_has_brand = "workbuddy" in BADGE.lower()

# ---------------------------------------------------------------- 文案：硬压到 2 行
raw = C.get("title_lines") or ["WorkBuddy"]
lines = [str(t).strip() for t in raw if str(t).strip()]
if len(lines) > MAX_LINES:
    print("⚠  封面文案给了 %d 行，超过上限 %d 行，只留「品牌行 + 结论行」。丢掉：%s"
          % (len(lines), MAX_LINES, " / ".join(lines[1:-1]) or "（中间行）"))
    # 硬切前两行会留下半句（「别再传」），所以留最开头的品牌行 + 最后的结论行
    head, tail = lines[0], lines[-1]
    lines = [head, tail] if "workbuddy" in head.lower() else [tail]
if not lines:
    lines = ["WorkBuddy"]

# 品牌词必须露脸：胶囊里有 WorkBuddy 就算露了，不再额外吃掉一行
brand_idx = next((i for i, t in enumerate(lines) if "workbuddy" in t.lower()), None)
if brand_idx is None and badge_has_brand:
    pass                      # 品牌已在红胶囊里，两行都能写钩子
elif brand_idx is None:
    if C.get("enforce_brand", True):
        # 两行都没品牌词时，先把它们合并成一句完整的钩子，别把半句扔掉
        if len(lines) >= 2:
            merged = "".join(lines).strip()
            keep = merged if len(merged) <= 12 else lines[-1]
        else:
            keep = lines[0]
        print("⚠  两行文案里没有 WorkBuddy，已改成「WorkBuddy / %s」" % keep)
        lines = ["WorkBuddy", keep] if keep.lower().strip() != "workbuddy" else ["WorkBuddy"]
        brand_idx = 0
    else:
        print("⚠  两行文案里没有 WorkBuddy（enforce_brand 已关闭）")

# 强调行：默认落在钩子那行，不落在品牌行
accent_idx = C.get("title_accent_line")
if accent_idx is None or not (0 <= accent_idx < len(lines)) or accent_idx == brand_idx:
    accent_idx = 0 if (len(lines) == 1 or brand_idx == len(lines) - 1) else len(lines) - 1

# 行级配色（视频号模板用）：默认第 1 行白、其余柠檬金。
# 金色那行是视线落点 —— 就算关掉红胶囊也必须留着，否则两行全白、封面没了重心。
line_colors = C.get("line_colors") or ["white", "gold"]

# ---------------------------------------------------------------- 拼标题 HTML
# 每行独立成块且禁止折行：一旦让浏览器自己折，「两行」就会变成三四行
rows = []
for i, t in enumerate(lines):
    cls = ["line"]
    if i == brand_idx and len(lines) > 1:
        cls.append("brand")          # 品牌行缩小当引子
    if i == accent_idx and i != brand_idx:
        cls.append("accent")         # 钩子行上强调色
    if line_colors:
        cls.append(line_colors[i] if i < len(line_colors) else line_colors[-1])
    rows.append('<span class="%s">%s</span>' % (" ".join(cls), t))
title_html = "".join(rows)

# 只有一行时把字号顶上去，别在画布上留一块空
title_size = int(C.get("title_size", 300))
if len(lines) == 1:
    title_size = int(title_size * 1.15)

# ---------------------------------------------------------------- 附加文字：默认全砍
sub, mark = C.get("sub", ""), C.get("sub_mark", "")
kicker, index = C.get("kicker", ""), C.get("index", "")
foot_l, foot_r = C.get("foot_left", ""), C.get("foot_right", "")
extra_text = bool(C.get("extra_text", False))

extras = {"kicker": kicker, "index": index, "sub": sub, "sub_mark": mark,
          "foot_left": foot_l, "foot_right": foot_r}
filled = [k for k, v in extras.items() if str(v or "").strip()]
if filled and not extra_text:
    print("⚠  封面只允许两行大字，已丢弃这些附加文字：%s（确需保留请设 cover.extra_text=true）"
          % "、".join(filled))
if not extra_text:
    sub = mark = kicker = index = foot_l = foot_r = ""

sub_html = '%s <span class="mark">%s</span>' % (sub, mark) if mark else sub

# 空槽位整块剔除，避免留下空行和空分隔线
keep = set()
if has_badge:
    keep.add("badge")
if kicker or index:
    keep.add("top")
if sub:
    keep.add("sub")
if foot_l or foot_r:
    keep.add("foot")

# ---------------------------------------------------------------- 底部视觉：矢量图形 / 截图
# 2026-10-30 第 6 版：默认不再贴产品截图，改用 templates/motifs/ 下的纯 SVG 图形，
# 跟袁总视频号那批「发光图标」封面一致。老项目要贴图就把 cover.art 设成 "shot"。
FONT = os.path.join(SKILL, "assets", "fonts", "NotoSansSC-VF.ttf")
ART_MODE = str(C.get("art", "motif")).lower()
MOTIF = str(C.get("motif", "orbit")).strip() or "orbit"
MOTIF_DIR = os.path.join(SKILL, "templates", "motifs")
ART_BUILTIN = {os.path.splitext(f)[0] for f in os.listdir(MOTIF_DIR) if f.endswith(".svg")} \
    if os.path.isdir(MOTIF_DIR) else set()

shot_abs = ""
art_html = ""

if ART_MODE == "shot":
    shot = C.get("shot") or ""
    if not shot:
        raise SystemExit("cover.art=shot 时 cover.shot 必填（写 assets/screenshots/xx.png 这种相对项目根目录的路径）")
    shot_abs = shot if os.path.isabs(shot) else os.path.join(PROJECT, shot)
    if not os.path.exists(shot_abs):
        raise SystemExit("封面主图不存在：" + shot_abs)
    art_html = '<img src="file://%s" alt="">' % shot_abs
else:
    # 优先找项目自带的 assets/motifs/<名字>.svg，其次找 skill 内置图形
    custom = os.path.join(PROJECT, "assets", "motifs", MOTIF + ".svg")
    if os.path.exists(custom):
        art_html = open(custom, encoding="utf-8").read()
    elif MOTIF in ART_BUILTIN:
        art_html = open(os.path.join(MOTIF_DIR, MOTIF + ".svg"), encoding="utf-8").read()
    else:
        fallback = "orbit" if "orbit" in ART_BUILTIN else sorted(ART_BUILTIN or {"orbit"})[0]
        print("⚠  没有名为「%s」的矢量图形，已回退 %s。可选：%s"
              % (MOTIF, fallback, "、".join(sorted(ART_BUILTIN)) or "（未装）"))
        p = os.path.join(MOTIF_DIR, fallback + ".svg")
        art_html = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    # 给内联 SVG 打上统一的尺寸约束
    art_html = art_html.replace("<svg ", '<svg style="width:100%;height:100%" ', 1)

tpl_name = C.get("template", "cover-videohao.html")
if tpl_name in ("cover-poster.html", "cover-titleonly.html"):
    print("⚠  正在用旧封面模板 %s（红底白字）。视频号现用风格是 cover-videohao.html"
          "（深空黑底 + 红胶囊 + 金白大字），要切换就把 cover.template 删掉或改成新模板。" % tpl_name)
tpl = open(os.path.join(SKILL, "templates", tpl_name), encoding="utf-8").read()

repl = {
    "{{TITLE}}": CFG.get("title", ""),
    "{{BG}}": C.get("bg", "#05080F"),
    "{{INK}}": C.get("ink", "#FFFFFF"),
    "{{INK_SOFT}}": C.get("ink_soft", "#C8D4E8"),
    "{{LINE}}": C.get("line", "#1E3358"),
    "{{ACCENT}}": C.get("accent", "#FFD24A"),
    "{{ACCENT_DEEP}}": C.get("accent_deep", "#F0A81B"),
    "{{BADGE}}": BADGE,
    "{{BADGE_BG}}": BADGE_BG,
    "{{CV_W}}": str(C.get("width", 1080)),
    "{{CV_H}}": str(C.get("height", 1440)),
    "{{PAD_Y}}": str(C.get("pad_y", 74)),
    "{{PAD_X}}": str(C.get("pad_x", 62)),
    "{{TITLE_SIZE}}": str(title_size),
    "{{SUB_SIZE}}": str(C.get("sub_size", 54)),
    "{{KICKER}}": kicker,
    "{{INDEX}}": index,
    "{{TITLE_HTML}}": title_html,
    "{{SUB_HTML}}": sub_html,
    "{{SHOT}}": shot_abs,
    "{{ART}}": art_html,
    "{{FONT}}": FONT,
    "{{SHOT_FIT}}": C.get("shot_fit", "cover"),
    "{{FOOT_L}}": foot_l,
    "{{FOOT_R}}": foot_r,
    "{{TITLE_TOP}}": str(C.get("title_top", 96)),
    "{{SHOT_TOP}}": str(C.get("shot_top", 56)),
}

html = tpl
for k, v in repl.items():
    html = html.replace(k, v)


def drop_blocks(doc, keep_blocks):
    """按 <!--BLOCK:x--> 标记整块保留或整块删除。"""
    for name in ("badge", "top", "sub", "foot"):
        open_tag, close_tag = "<!--BLOCK:%s-->" % name, "<!--/BLOCK:%s-->" % name
        if name in keep_blocks:
            for tag in (open_tag, close_tag):
                doc = doc.replace("\n" + tag, "").replace(tag, "")
        else:
            pat = re.compile(r"[ \t]*%s.*?%s[ \t]*\n?" % (re.escape(open_tag), re.escape(close_tag)),
                             re.S)
            doc = pat.sub("", doc)
    return doc


html = drop_blocks(html, keep)

tmp = os.path.join(PROJECT, ".cover_render.html")
open(tmp, "w", encoding="utf-8").write(html)

W, H = C.get("width", 1080), C.get("height", 1440)
with sync_playwright() as p:
    b = launch_browser(p)
    pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=int(C.get("dpr", 2)))
    pg.goto("file://" + tmp)
    pg.wait_for_timeout(1400)   # 等 @font-face 加载 + 字体加载后重排字号
    pg.screenshot(path=OUT, full_page=True)
    b.close()
os.remove(tmp)

print("✅ 封面 %s  %dx%d ｜ 文案 %d 行：%s" % (OUT, W, H, len(lines), " / ".join(lines)))

# 顺手导一张 jpg 双胞胎：视频号/公众号上传封面时更认 jpg
try:
    from PIL import Image
    jpg = os.path.splitext(OUT)[0] + ".jpg"
    Image.open(OUT).convert("RGB").save(jpg, quality=94, subsampling=0)
    print("   ↳ %s" % os.path.basename(jpg))
except Exception as e:
    print("   ⚠ jpg 导出失败：%s" % e)
