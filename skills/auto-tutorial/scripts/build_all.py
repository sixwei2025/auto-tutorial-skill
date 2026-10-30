#!/usr/bin/env python3
"""一键总控：抓文章 → 分镜 → 素材 → 封面 → 说明卡 → 配音 → 时间轴 → 音轨 → 字幕 → 逐帧 → 成片 → 标题

用法：
  # 从零开始（给一个文章链接）
  TV_PROJECT=/path python3 build_all.py --url https://mp.weixin.qq.com/s/xxxx

  # 已有 project.json，只出片
  TV_PROJECT=/path python3 build_all.py

  # 从某步续跑 / 只跑某步
  TV_PROJECT=/path python3 build_all.py --from voice
  TV_PROJECT=/path python3 build_all.py --only cover

步骤名：fetch storyboard assets cover cards voice manifest audio subs html frames mux titles
"""
import json
import os
import subprocess
import sys
import time

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL, "scripts")
PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))


def find_python():
    """找带 playwright + Pillow 的解释器（跨平台）。"""
    cands = [sys.executable,
             os.path.expanduser("~/.workbuddy/binaries/python/envs/default/bin/python3"),
             sys.executable.replace("python.exe", "pythonw.exe") if os.name == "nt" else None,
             "python" if os.name == "nt" else "python3",
             "py" if os.name == "nt" else None]
    for c in cands:
        if not c:
            continue
        if os.path.sep in c and not os.path.exists(c):
            continue
        try:
            r = subprocess.run([c, "-c", "import playwright, PIL"], capture_output=True)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    raise SystemExit("找不到同时装了 playwright 和 Pillow 的 Python。\n"
                     "请先执行：pip install playwright pillow && playwright install chrome")


PY = find_python()
_slug = "video"
try:
    _slug = json.load(open(os.path.join(PROJECT, "project.json"), encoding="utf-8")).get("slug", "video")
except Exception:
    pass

# Windows 控制台中文/emoji 输出保护
env = dict(os.environ, TV_PROJECT=PROJECT, SLUG=_slug,
           PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

STEPS = [
    ("fetch",      "抓文章 + 下载配图",   [PY, os.path.join(SCRIPTS, "fetch_article.py")]),
    ("storyboard", "自动分镜 + 写旁白",   [PY, os.path.join(SCRIPTS, "make_storyboard.py")]),
    ("capture",    "网页取画面（截图/动图）", [PY, os.path.join(SCRIPTS, "capture_web.py")]),
    ("assets",     "素材加工（放大/裁切）", [PY, os.path.join(SCRIPTS, "prep_assets.py")]),
    ("annotate",   "截图标注（圈重点）",    [PY, os.path.join(SCRIPTS, "annotate.py")]),
    ("cover",      "渲染 3:4 封面",        [PY, os.path.join(SCRIPTS, "make_cover.py")]),
    ("cards",      "渲染说明卡",           [PY, os.path.join(SCRIPTS, "make_cards.py")]),
    ("voice",      "VoiceBox 批量配音",    [PY, os.path.join(SCRIPTS, "make_voice.py")]),
    ("manifest",   "生成时间轴清单",        [PY, os.path.join(SCRIPTS, "make_manifest.py")]),
    ("audio",      "合成完整音轨",          [PY, os.path.join(SCRIPTS, "make_audio.py")]),
    ("subs",       "字幕 SRT/VTT/ASS",     [PY, os.path.join(SCRIPTS, "make_subs.py")]),
    ("html",       "生成渲染页",            [PY, os.path.join(SCRIPTS, "make_render_html.py")]),
    ("frames",     "逐帧渲染",              [PY, os.path.join(SCRIPTS, "render_frames.py")]),
    ("patch",      "把动图嵌进画面区",       [PY, os.path.join(SCRIPTS, "patch_frames.py")]),
    ("mux",        "合成 MP4 + 章节",       [PY, os.path.join(SCRIPTS, "render_mux.py")]),
    ("titles",     "标题 8 备选 + Top3",   [PY, os.path.join(SCRIPTS, "make_titles.py")]),
    ("library",    "同步到本地视频中心", [PY, os.path.join(SCRIPTS, "push_library.py")]),
]

argv = sys.argv[1:]
url = argv[argv.index("--url") + 1] if "--url" in argv else None
only = argv[argv.index("--only") + 1] if "--only" in argv else None
start_from = argv[argv.index("--from") + 1] if "--from" in argv else None

names = [s[0] for s in STEPS]
for v, label in ((only, "--only"), (start_from, "--from")):
    if v and v not in names:
        raise SystemExit("未知步骤「%s」。可选：%s" % (v, " ".join(names)))

# 没有 url 且没有 project.json 且要跑全流程 → 提示
has_cfg = os.path.exists(os.path.join(PROJECT, "project.json"))
if not url and not has_cfg and not only and not start_from:
    raise SystemExit("项目里还没有 project.json。\n"
                     "从零开始：python3 build_all.py --url <文章链接>\n"
                     "或先写一份 project.json 再来。")

skip = bool(start_from)
t0 = time.time()
for name, desc, cmd in STEPS:
    if skip:
        if name == start_from:
            skip = False
        else:
            print("⏭  跳过 %s" % desc)
            continue
    if only and name != only:
        continue
    if name == "fetch" and not only and not url:
        continue
    if name == "fetch":
        if not url:
            raise SystemExit("fetch 步骤需要 --url <文章链接>")
        cmd = cmd + [url]
    if name == "storyboard" and not only and not url and not start_from and has_cfg:
        continue        # 全流程且已有手写配置时，不覆盖分镜
    if name == "storyboard" and (url or start_from == "storyboard" or only == "storyboard"):
        cmd = cmd + ["--force"]   # 显式要重做分镜时才覆盖 project.json
    if name == "capture":
        try:
            _cap = json.load(open(os.path.join(PROJECT, "project.json"),
                                  encoding="utf-8")).get("capture", {})
        except Exception:
            _cap = {}
        if not _cap.get("url"):
            print("⏭  跳过网页取画面（project.json 里没有 capture.url）")
            continue
    if name == "storyboard" and not url and not os.path.exists(
            os.path.join(PROJECT, "article.json")):
        print("⏭  跳过自动分镜（无 article.json）")
        continue

    if name in {"assets", "voice", "manifest", "mux", "library"}:
        from check_evidence import validate
        evidence_errors = validate(PROJECT)
        if evidence_errors:
            raise SystemExit("实操证据未通过：\n- " + "\n- ".join(evidence_errors))

    print("\n▶ [%s] %s" % (name, desc), flush=True)
    ts = time.time()
    r = subprocess.run(cmd, cwd=PROJECT, env=env)
    if r.returncode != 0:
        raise SystemExit("❌ 步骤 %s 失败（exit %d）" % (name, r.returncode))
    print("   ✓ %.1fs" % (time.time() - ts))

print("\n🎬 全部完成，用时 %.1f 分钟" % ((time.time() - t0) / 60))
out = os.path.join(PROJECT, "delivery")
if os.path.isdir(out):
    for f in sorted(os.listdir(out)):
        p = os.path.join(out, f)
        print("   %-44s %6.2f MB" % (f, os.path.getsize(p) / 1048576))
