#!/usr/bin/env python3
"""Step C｜自动分镜：article.json → project.json 草稿（场景 / 旁白 / 封面 / 说明卡）

用法：
  TV_PROJECT=/path python3 make_storyboard.py            # 已有 project.json 时输出 .draft.json
  TV_PROJECT=/path python3 make_storyboard.py --force    # 覆盖 project.json

思路：脚本负责「机械化」部分（切段、配图、排时长、填字段），
产出 70 分可跑的草稿；旁白和封面文案建议再过一遍人手润色到 90 分。
"""
import datetime
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT

FORCE = "--force" in sys.argv

art = json.load(open(os.path.join(PROJECT, "article.json"), encoding="utf-8"))
old = {}
if os.path.exists(os.path.join(PROJECT, "project.json")):
    old = json.load(open(os.path.join(PROJECT, "project.json"), encoding="utf-8"))
HINT = old
ST = HINT.get("storyboard", {})
TARGET = None   # 段数按正文体量在下面算，不写死
BRAND = ST.get("brand", "WorkBuddy")

# ----------------------------------------------------------------- 文本工具
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200b\u200c\u200d\ufeff]")


def clean(t):
    t = EMOJI.sub("", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)          # markdown 图片
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[*#>_`|]+", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" ·-—、")


def clauses(t):
    """按标点切成短句，顺手把超长分句按逗号再切。"""
    out = []
    for seg in re.split(r"[。！？!?；;]+", t):
        seg = seg.strip()
        if not seg:
            continue
        for part in re.split(r"[，,：:]", seg):
            part = clean(part).rstrip("：:，,、 ")
            if len(part) >= 4:
                out.append(part)
    return out


def to_narration(t, max_s=3, max_c=26):
    """原文 → 口播稿：短句、去书面语、控制总长。"""
    picked, total = [], 0
    for c in clauses(t):
        if len(c) > max_c:
            c = c[:max_c]
        if total + len(c) > max_s * max_c:
            break
        picked.append(c)
        total += len(c)
        if len(picked) >= max_s:
            break
    if not picked:
        return ""
    s = "，".join(picked) + "。"
    s = s.replace("，。", "。")
    s = re.sub(r"^(而且|另外|此外|同时|所以|因此|但是|不过)，?", "", s)
    return s


def short(t, n):
    t = clean(t).rstrip("：:，,、 ")
    if len(t) <= n:
        return t
    cut = t[:n - 1]
    while cut and len(cut) < len(t) and re.match(r"[A-Za-z0-9]", t[len(cut)]):
        cut = cut[:-1]                      # 别把 WorkBuddy 切成 WorkBud
    for i in range(len(cut) - 1, max(0, len(cut) - 5), -1):
        if cut[i] in "的了和与并把让给对从在是":
            cut = cut[:i + 1]
            break
    return cut.rstrip("，、的：和与并") + "…"


def three_points(narr):
    """把一句旁白拆成 3 条清单要点（按虚词切，尽量不出现省略号）。"""
    chunks = []
    for c in clauses(narr) or [narr]:
        for part in re.split(r"(?:而且|并且|然后|且|并|再|就|才|也)", c):
            part = clean(part).strip("的 了")
            if 2 <= len(part) <= 12:
                chunks.append(part)
    if len(chunks) < 3:
        chunks = [x for c in (clauses(narr) or [narr]) for x in [c]]
    while len(chunks) < 3:
        chunks.append(chunks[-1])
    def hard(t, n=14):
        t = clean(t).strip("的 了")
        if len(t) <= n:
            return t
        cut = t[:n]
        while cut and len(cut) < len(t) and re.match(r"[A-Za-z0-9]", t[len(cut)]):
            cut = cut[:-1]
        return cut.rstrip("，、的：和与并")

    return [hard(chunks[0]), hard(chunks[len(chunks) // 2]), hard(chunks[-1])]


def heading_like(t):
    t = clean(t)
    if len(t) > 22 or not t:
        return False
    if re.match(r"^(0?\d{1,2}|[一二三四五六七八九十]{1,2})[、.．\s）)]", t):
        return True
    return not re.search(r"[。！？；]$", t) and len(t) <= 14


def split_cover(title):
    """标题 → 封面双行大字（每行 ≤7 字）。"""
    t = clean(title)
    t = re.split(r"[：:｜|]", t)[-1].strip() or t
    t = re.sub(r"^WorkBuddy\s*", "", t)
    t = re.sub(r"[「」“”\"]", "", t)
    if len(t) <= 7:
        return [t, ""]
    for tail in ("上线", "发布", "来了", "更新", "免费", "就行", "也行", "能用",
                 "可用", "现成", "也能", "更好用", "更省事"):
        if t.endswith(tail) and len(t) - len(tail) >= 3:
            return [t[:-len(tail)], tail]
    for sep in ("，", "、", " "):
        if sep in t:
            a, b = t.split(sep, 1)
            if len(a) >= 3 and len(b) >= 2:
                return [a.strip(), b.strip()]
    n = (len(t) + 1) // 2
    cut = t[:n]
    for i in range(len(cut) - 1, max(0, n - 4), -1):
        if cut[i] in "，,、的和与把让给对从在":
            return [t[:i].strip("，,、"), t[i:].strip("，,、")]
    return [t[:n], t[n:]]


# ----------------------------------------------------------------- 组装场景
def is_junk_para(t):
    """结尾引流、纯域名、与标题重复的段落不进视频。"""
    c = clean(t)
    if not c:
        return True
    if re.search(r"(www\.|[a-z0-9-]+\.(cn|com|ai|io)\b)", c, re.I) or "扫码" in c:
        return True
    if any(k in c for k in ("感受更多", "立即体验", "欢迎体验", "点击体验", "预约演示",
                            "关注我们", "下期见", "本文作者", "版权")):
        return True
    title = clean(art["title"])
    if c and (c in title or (title and len(c) < 40 and title[:12] in c)):
        return True
    return False


items = []
for b in art["blocks"]:
    if b["type"] == "img":
        items.append(("img", b["src"]))
    elif not is_junk_para(b["text"]):
        items.append(("h" if heading_like(b["text"]) else "p", b["text"]))

# 按小标题切段
sections, cur = [], {"head": "", "paras": [], "imgs": []}
for kind, val in items:
    if kind == "h":
        if cur["paras"] or cur["imgs"]:
            sections.append(cur)
        cur = {"head": val, "paras": [], "imgs": []}
    elif kind == "img":
        cur["imgs"].append(val)
    else:
        cur["paras"].append(val)
if cur["paras"] or cur["imgs"]:
    sections.append(cur)

# 目标段数：不写死。按正文体量算 —— 一段旁白约 28 字（≈5 秒），长文自然切更多段。
# 3 分钟的稿子会切出 30+ 段，不会被硬压成 10 段。
_total_chars = sum(len(p) for s in sections for p in s["paras"])
if ST.get("target_scenes"):
    TARGET = int(ST["target_scenes"])
else:
    TARGET = max(6, min(60, round(_total_chars / 28)))
    print("[scene] 正文 %d 字 → 目标 %d 段（按内容体量算，非固定）" % (_total_chars, TARGET))

# 合并过短段落组，目标 TARGET 段
scenes_raw = []
for s in sections:
    narr = to_narration("。".join(s["paras"]), max_s=3, max_c=26) if s["paras"] else ""
    if len(narr) < 12 and scenes_raw:
        scenes_raw[-1]["paras"] += s["paras"]
        scenes_raw[-1]["imgs"] += s["imgs"]
        continue
    scenes_raw.append({"head": s["head"], "paras": s["paras"], "imgs": s["imgs"]})

while len(scenes_raw) > TARGET:
    i = min(range(len(scenes_raw) - 1),
            key=lambda k: sum(len(p) for p in scenes_raw[k]["paras"]))
    scenes_raw[i]["paras"] += scenes_raw[i + 1]["paras"]
    scenes_raw[i]["imgs"] += scenes_raw[i + 1]["imgs"]
    scenes_raw[i]["head"] = scenes_raw[i]["head"] or scenes_raw[i + 1]["head"]
    scenes_raw.pop(i + 1)

URL2FILE = {im["src"]: im["file"] for im in art.get("images", [])}
img_pool = [im["src"] for im in art.get("images", [])] or [i for k, i in items if k == "img"]
used = set()


DIMS = {im["src"]: (im.get("width") or 0, im.get("height") or 0) for im in art.get("images", [])}
_stat_cache = {}


def img_stat(src):
    """读原始图的 (宽, 高, 灰度标准差)，用来识别空白图。"""
    if src in _stat_cache:
        return _stat_cache[src]
    w, h = DIMS.get(src, (0, 0))
    std = 999.0
    local = URL2FILE.get(src)
    p = os.path.join(PROJECT, local) if local else None
    if p and os.path.exists(p):
        try:
            from PIL import Image, ImageStat
            im = Image.open(p)
            if getattr(im, "is_animated", False):
                im.seek(0)
            std = ImageStat.Stat(im.convert("L")).stddev[0]
        except Exception:
            pass
    _stat_cache[src] = (w, h, std)
    return _stat_cache[src]


def usable(src):
    """空白图（纯色/极低对比）和细长条不适合当主画面。"""
    w, h, std = img_stat(src)
    if std < 8:
        return False                     # 纯色/空白帧（公众号常见占位 GIF）
    if w and h and w / h > 2.6:
        return False                     # 细长 banner
    return True


def pick_image(scene, idx):
    for src in scene["imgs"]:
        if src not in used and usable(src):
            used.add(src)
            return src
    if not img_pool:
        return None                      # 纯文本稿（无配图）→ 走说明卡
    order = img_pool[idx % len(img_pool):] + img_pool[:idx % len(img_pool)]
    for src in order:
        if src not in used and usable(src):
            used.add(src)
            return src
    return None


def cover_shot():
    """封面主图：挑宽高比接近 0.6 的图，跳过细长 banner 和超长竖图。"""
    best, best_d = None, 9
    for im in art.get("images", []):
        w, h = im.get("width") or 0, im.get("height") or 0
        if not w or not h:
            continue
        r = h / w
        if not (0.32 <= r <= 1.15):
            continue
        d = abs(r - 0.62)
        if d < best_d:
            best, best_d = im, d
    if best:
        return shot_path(best["file"])
    return shot_path((art.get("images") or [{}])[0].get("file"))


def shot_path(src):
    """raw 图（可能是 URL）→ screenshots 下的加工产物。"""
    if not src:
        return None
    local = URL2FILE.get(src, src)
    name = os.path.splitext(os.path.basename(local))[0] + ".png"
    cand = "assets/screenshots/%s" % name
    return cand if os.path.exists(os.path.join(PROJECT, cand)) else None


scenes, cards, missing = [], [], []
for i, sc in enumerate(scenes_raw):
    narr = to_narration("。".join(sc["paras"]), max_s=3, max_c=26)
    if not narr:
        continue
    sid = re.sub(r"[^a-z0-9]+", "", (HINT.get("slug") or "s"))[:6] or "s"
    sid = "s%02d" % (i + 1)
    src = pick_image(sc, i)
    shot = shot_path(src)
    if not src:
        missing.append((sid, narr))
        shot = "assets/screenshots/%s-card.png" % sid
        pts = three_points(narr)
        cards.append({
            "id": "%s-card" % sid, "type": "list",
            "kicker": short(sc["head"] or "重点", 12), "index": "%02d" % (len(cards) + 1),
            "title": short(sc["head"] or narr, 18),
            "items": [{"t": p, "d": ""} for p in pts],
            "foot": "",
        })

    title = short(sc["head"] or clauses(narr)[0], 22)
    cs = clauses(narr)
    instruction = short(min(cs, key=len) if cs else title, 16)
    pts = three_points(narr)
    scenes.append({
        "id": sid, "shot": shot, "title": title, "instruction": instruction,
        "aside": "为什么" if i == 0 else "第 %d 步" % max(1, i),
        "checklist": [[pts[0], "done"], [pts[1], "current"], [pts[2], "todo"]],
        "tip": short("录像里这一步最容易卡住，暂停一下照做。" if i else "", 24),
        "voice": narr,
        "zoom": 1.06,
    })

# ------------------------------------------------------------------- 封面
# 🔴 封面只放两行（2026-10-30 袁总拍板）：第 1 行品牌词 WorkBuddy，第 2 行钩子。
#    顶部小标 / 序号 / 副标 / 底部脚注一律不生成 —— 3:4 在列表里就一小格，字多了没人看。
cover_title = ST.get("title") or art["title"]
feature = ST.get("feature") or ""
if not feature:
    m = re.search(r"[「“]([^」”]{2,10})[」”]", art["title"])
    feature = m.group(1) if m else ""
sub_mark = ST.get("benefit", "")
if not sub_mark:
    cand = clean(re.sub(r"[「」“”\"]|WorkBuddy", "", art["title"]))
    tail = re.split(r"[：:，,]", cand)[-1].strip()
    sub_mark = feature or (tail if 2 <= len(tail) <= 8 else "一键搞定")

# 钩子：把拆开的两半合回一行，太长就退后半句，保证第 2 行能一口读完
_half = split_cover(cover_title)
hook = (_half[0] + _half[1]).strip()
if not hook:
    hook = feature or "一键搞定"
if len(hook) > 10:
    hook = (_half[1] or _half[0]).strip()[:10]
title_lines = ["WorkBuddy", hook]

slug = HINT.get("slug") or ("tv-" + hashlib.md5(
    (art.get("url", "") + art["title"]).encode()).hexdigest()[:6])

cover_old = HINT.get("cover", {})
cover = {
    # 2026-10-30 起默认走视频号风格：深空黑底 + 红胶囊「WorkBuddy实操」+ 金白大字
    "template": cover_old.get("template", "cover-videohao.html"),
    "bg": cover_old.get("bg", "#05080F"), "ink": cover_old.get("ink", "#FFFFFF"),
    "ink_soft": cover_old.get("ink_soft", "#C8D4E8"), "line": cover_old.get("line", "#1E3358"),
    "accent": cover_old.get("accent", "#FFD24A"),
    "accent_deep": cover_old.get("accent_deep", "#F0A81B"),
    "badge": cover_old.get("badge", "WorkBuddy实操"),
    "badge_bg": cover_old.get("badge_bg", "#E5392F"),
    "line_colors": cover_old.get("line_colors", ["white", "gold"]),
    "width": 1080, "height": 1440,
    "pad_y": cover_old.get("pad_y", 74), "pad_x": cover_old.get("pad_x", 62),
    "title_size": cover_old.get("title_size", 260),
    "sub_size": cover_old.get("sub_size", 54),
    "max_lines": 2,
    "title_lines": cover_old.get("title_lines") or title_lines,
    "title_accent_line": 1,
    # 以下附加槽位全部留空：封面只允许「红胶囊 + 两行大字」
    "kicker": "", "index": "", "sub": "", "sub_mark": "",
    "foot_left": "", "foot_right": "",
    "benefit": short(sub_mark, 8),   # 不渲染，只留给备选标题用
    # 下半部分用矢量图形，不贴截图（第 6 版）；motif 草稿默认 orbit，人工按题材改
    "art": cover_old.get("art", "motif"),
    "motif": cover_old.get("motif", "orbit"),
    "output": "cover/cover-3x4.png", "cover_duration": 0.1,
}
# 只有显式回到老路（art=shot）时才带截图字段，默认的矢量图形版不带，免得 project.json 里
# 躺着一个 art=motif 时根本不用的 shot 路径，后人误以为封面还在用截图
if cover["art"] == "shot":
    cover["shot"] = cover_old.get("shot") or cover_shot() or (scenes[0]["shot"] if scenes else "")
    cover["shot_fit"] = cover_old.get("shot_fit", "cover")

out = {
    "title": cover_title, "slug": slug, "language": "zh",
    "series": "WORKBUDDY · %s" % (feature or "教程"),
    "date": datetime.date.today().isoformat(),
    "source": "%s · %s" % (art.get("account") or "官方", art.get("url", "")),
    "canvas": HINT.get("canvas", {"width": 1920, "height": 1080, "fps": 30}),
    "lead": HINT.get("lead", 0.35), "tail": HINT.get("tail", 0.75),
    "voice": HINT.get("voice", {
        "profile_name": os.environ.get("VOICEBOX_PROFILE", "YourVoice"),
        "engine": None, "model_size": "1.7B",
        "speed": 1.5, "loudnorm": "I=-14:TP=-1.0:LRA=9"}),
    "voice_note": "VoiceBox 本机声纹（请在 voice.profile_name 填你的音色名），语速 1.5x，响度 -14 LUFS",
    "assets": HINT.get("assets", {"auto": True, "target_width": 2160, "trim_white": True}),
    "cover": cover,
    # 说明卡主色固定品牌红：封面强调色是金色，不能把它带到正文/卡片里
    "cards": {"accent": HINT.get("cards", {}).get("accent", "#C7352D"),
              "width": 1080, "height": 608, "dpr": 2, "items": cards},
    "scenes": scenes,
}

dst = os.path.join(PROJECT, "project.json" if FORCE or not old else "project.draft.json")
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("✅ %s" % os.path.basename(dst))
print("   场景 %d 个 / 说明卡 %d 张 / 旁白合计 %d 字"
      % (len(scenes), len(cards), sum(len(s["voice"]) for s in scenes)))
print("   封面文案（两行）：%s ｜ %s" % tuple((cover["title_lines"] + ["—"])[:2]))
if not FORCE and old:
    print("   （原 project.json 未改动；确认草稿后加 --force 覆盖）")
print("\n   建议人工润色：封面大字、每段 instruction（≤16 字）、旁白口语化")
for s in scenes:
    print("   %-5s %-22s %s" % (s["id"], short(s["title"], 20), s["voice"][:34]))
