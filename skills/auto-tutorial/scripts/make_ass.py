#!/usr/bin/env python3
"""SRT → ASS（带样式，字体大小按 1080p 画布设定）"""
import json, os
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ass_font as _af
ASS_FONT = _af()

PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
d = json.load(open(os.path.join(PROJECT, "sop.json")))

def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

cues, cursor = [], 0.0
for st in d["steps"]:
    for c in st["captions"]:
        cues.append((cursor + c["start"], cursor + c["end"], c["text"]))
    cursor += st["duration"]

HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,__FONT__,42,&H00432A10,&H000000FF,&H00FFFFFF,&H00F2F7FD,0,0,0,0,100,100,0.5,0,4,14,0,2,150,150,52,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
HEAD = HEAD.replace("__FONT__", ASS_FONT)

lines = [HEAD]
for a, b, t in cues:
    txt = t.replace("\n", "\\N").replace("{", "(").replace("}", ")")
    lines.append(f"Dialogue: 0,{ts(a)},{ts(b)},Default,,0,0,0,,{txt}\n")

out = os.path.join(PROJECT, "delivery", "captions.ass")
open(out, "w").write("".join(lines))
print(f"✅ {out}  {len(cues)} 条")
