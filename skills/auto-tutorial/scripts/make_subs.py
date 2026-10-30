#!/usr/bin/env python3
"""从 sop.json 提取字幕（SRT/VTT）与章节。"""
import json, os

PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
d = json.load(open(os.path.join(PROJECT, "sop.json")))
OUT = os.path.join(PROJECT, "delivery")
os.makedirs(OUT, exist_ok=True)

def ts(t, sep=","):
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
    if ms == 1000: ms = 999
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"

cues, cursor = [], 0.0
chapters = []
for i, step in enumerate(d["steps"]):
    start = cursor
    chapters.append((start, step["chapter"]))
    for c in step["captions"]:
        cues.append((start + c["start"], start + c["end"], c["text"]))
    cursor += step["duration"]

with open(os.path.join(OUT, "captions.srt"), "w") as f:
    for i, (a, b, t) in enumerate(cues, 1):
        f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n")

with open(os.path.join(OUT, "captions.vtt"), "w") as f:
    f.write("WEBVTT\n\n")
    for a, b, t in cues:
        f.write(f"{ts(a,'.')} --> {ts(b,'.')}\n{t}\n\n")

with open(os.path.join(OUT, "chapters.txt"), "w") as f:
    for a, name in chapters:
        f.write(f"{ts(a)[:8]} {name}\n")

with open(os.path.join(OUT, "chapters.vtt"), "w") as f:
    f.write("WEBVTT\n\n")
    for i, (a, name) in enumerate(chapters):
        end = chapters[i + 1][0] if i + 1 < len(chapters) else cursor
        f.write(f"{ts(a,'.')} --> {ts(end,'.')}\n{name}\n\n")

# ffmetadata 供 embed 进 mp4
with open(os.path.join(OUT, "chapters.ffmetadata"), "w") as f:
    f.write(";FFMETADATA1\n")
    for i, (a, name) in enumerate(chapters):
        end = chapters[i + 1][0] if i + 1 < len(chapters) else cursor
        f.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(a*1000)}\nEND={int(end*1000)}\ntitle={name}\n")

print(f"✅ {len(cues)} 条字幕 / {len(chapters)} 个章节 / 总时长 {cursor:.2f}s")
for a, n in chapters:
    print(f"   {ts(a)[:8]}  {n}")
