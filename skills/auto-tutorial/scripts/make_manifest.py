#!/usr/bin/env python3
"""Step 2｜读 project.json + 配音时长 → 生成 sop.json（时间轴清单）

用法：TV_PROJECT=/path/to/project python3 make_manifest.py
"""
import json, os, re

PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
CFG = json.load(open(os.path.join(PROJECT, "project.json")))
META = {m["id"]: m for m in json.load(open(os.path.join(PROJECT, "voice", "audio-meta.json")))}

LEAD = CFG.get("lead", 0.35)
TAIL = CFG.get("tail", 0.75)
COVER_DUR = CFG.get("cover", {}).get("cover_duration", 0.2)


def split_sentences(text):
    parts = re.split(r"(?<=[。！？!?])", text)
    return [p.strip() for p in parts if p.strip()]


cover = CFG.get("cover", {})
shots = [{
    "id": "cover", "path": cover.get("output", "cover/cover-3x4.png"),
    "width": 1080, "height": 1440, "kind": "cover",
    "source": "本片 3:4 竖版封面", "capturedAt": CFG.get("date", ""), "redacted": False,
}]
steps = [{
    "id": "cover", "kind": "cover", "title": "", "instruction": "",
    "chapter": "封面", "asideLabel": "", "halo": False, "checklist": [],
    "duration": COVER_DUR, "screenshot": "cover", "zoom": 1.0, "tip": "",
    "target": {"x": 0, "y": 0, "width": 1080, "height": 1440},
    "voice": None, "captions": [],
}]
cursor = COVER_DUR

for sc in CFG["scenes"]:
    sid = sc["id"]
    m = META.get(sid)
    if m is None:
        raise SystemExit("缺少配音：voice/audio-meta.json 里没有 " + sid)
    dur = round(m["duration"] + LEAD + TAIL, 3)

    shots.append({
        "id": sid, "path": sc["shot"], "width": 1, "height": 1,
        "kind": sc.get("kind", "real"),
        "source": sc.get("source", CFG.get("source", "")),
        "capturedAt": CFG.get("date", ""), "redacted": sc.get("redacted", True),
    })

    sents = split_sentences(m["text"])
    total_chars = sum(len(s) for s in sents) or 1
    caps, t = [], LEAD
    for s in sents:
        seg = m["duration"] * len(s) / total_chars
        caps.append({"start": round(t, 2), "end": round(t + seg, 2), "text": s})
        t += seg

    steps.append({
        "id": sid, "kind": sc.get("kind", ""),
        "title": sc["title"], "instruction": sc["instruction"],
        "chapter": sc.get("chapter", sc["title"]), "asideLabel": sc.get("aside", "这一步"),
        "target": sc.get("target"),
        "halo": sc.get("halo", False),
        "checklist": [{"text": a, "state": b} for a, b in sc["checklist"]],
        "duration": dur, "screenshot": sid, "zoom": sc.get("zoom", 1.06),
        "tip": sc.get("tip", ""),
        "voice": {"path": "voice/audio/" + sid + ".wav",
                  "duration": round(m["duration"] + 0.3, 3),
                  "offset": LEAD, "volume": 1.0},
        "captions": caps,
    })
    cursor += dur

manifest = {
    "version": 1,
    "title": CFG["title"], "language": CFG.get("language", "zh"),
    "series": CFG.get("series", ""),
    "canvas": CFG.get("canvas", {"width": 1920, "height": 1080, "fps": 30}),
    "narration": {"mode": "provided", "note": CFG.get("voice_note", "")},
    "screenshots": shots, "steps": steps,
}

from PIL import Image
for s in manifest["screenshots"]:
    p = os.path.join(PROJECT, s["path"])
    if not os.path.exists(p):
        raise SystemExit("缺素材：" + s["path"])
    im = Image.open(p)
    s["width"], s["height"] = im.width, im.height

for st in manifest["steps"]:
    sh = next(x for x in manifest["screenshots"] if x["id"] == st["screenshot"])
    tg = st["target"]
    if tg is None:
        st["target"] = {"x": 0, "y": 0, "width": sh["width"], "height": sh["height"]}
    elif max(tg.values()) <= 1.0:
        st["target"] = {"x": int(tg["x"] * sh["width"]), "y": int(tg["y"] * sh["height"]),
                        "width": int(tg["width"] * sh["width"]), "height": int(tg["height"] * sh["height"])}

json.dump(manifest, open(os.path.join(PROJECT, "sop.json"), "w"), ensure_ascii=False, indent=2)
print("✅ sop.json: %d 段，总时长 %.1fs (%.2f min)" % (len(steps), cursor, cursor/60))
for st in steps:
    print("   %-14s %6.2fs  %s" % (st["id"], st["duration"], st["title"]))
