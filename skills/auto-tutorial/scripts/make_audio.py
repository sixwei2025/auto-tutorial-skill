#!/usr/bin/env python3
"""按时间轴把 12 段旁白合成一条完整音轨。"""
import json, os, subprocess
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ffmpeg, ffprobe

PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
d = json.load(open(os.path.join(PROJECT, "sop.json")))
CFG = json.load(open(os.path.join(PROJECT, "project.json")))

inputs, filters = [], []
cursor, n = 0.0, 0
for st in d["steps"]:
    if not st.get("voice"):
        cursor += st["duration"]          # 片头封面：无旁白，只推进时间轴
        continue
    wav = os.path.join(PROJECT, st["voice"]["path"])
    assert os.path.exists(wav), wav
    ms = int((cursor + st["voice"].get("offset", 0.35)) * 1000)
    inputs += ["-i", wav]
    filters.append(f"[{n}:a]adelay={ms}|{ms}[a{n}]")
    n += 1
    cursor += st["duration"]

total = round(cursor, 3)
mix = "".join(f"[a{i}]" for i in range(n))
LN = CFG.get("voice", {}).get("loudnorm", "I=-15:TP=-1.2:LRA=9")
fc = (";".join(filters)
      + f";{mix}amix=inputs={n}:duration=longest:normalize=0[m]"
      + f";[m]loudnorm={LN}[ln]"
      + f";[ln]apad,atrim=0:{total}[out]")

out = os.path.join(PROJECT, "voice", "full.wav")
cmd = [ffmpeg(), "-y"] + inputs + ["-filter_complex", fc, "-map", "[out]",
                                   "-ar", "48000", "-ac", "2", out]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-1500:]); raise SystemExit(1)

dur = subprocess.run([ffprobe(), "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
print(f"✅ {out}  时长 {dur}s（视频 {total}s）")
