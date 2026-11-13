#!/usr/bin/env python3
"""ScreenForge / OpenScreen style Auto-Zoom Keyframe Generator from UI interaction telemetry.

Converts raw click / hover / bounding-box events into smooth, connected-pan camera keyframes
for `interface_renderer.py` or `zoom_pan.py`.

Core Rules (OpenScreen `zoom-transitions.ts` + Cap `zoom_spring.rs`):
1. Pre-Action Anticipation: Start pushing in 0.35s before the click/focus timestamp so the
   camera arrives right as the narration or action hits the target.
2. Connected Pan (No Yo-Yo): When two consecutive actions are within 3.2s of each other in the
   same window, glide directly from Center A to Center B at zoom level (1.6x ~ 2.0x) instead
   of zooming out to 1.0x and back in.
3. Context Pull-Out: Return to 1.0x full window view at the end of the scene (or when a gap > 3.5s occurs).

Usage:
  /opt/homebrew/bin/python3.11 auto_zoom_planner.py \
    --duration 6.2 \
    --window-size 1920,1080 \
    --events '[{"time":0.8,"box":[120,240,360,80],"zoom":1.85},{"time":3.1,"box":[980,420,420,160],"zoom":1.85}]'
"""
import argparse
import json
import sys


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def plan_keyframes(
    duration: float,
    window_size: tuple[int, int],
    events: list[dict],
    default_zoom: float = 1.8,
    push_dur: float = 0.48,
    pan_dur: float = 0.55,
    pull_dur: float = 0.52,
    connect_threshold: float = 3.2,
) -> list[dict]:
    sw, sh = window_size
    if not events:
        return [{"time": 0.0, "center": [0.5, 0.5], "zoom": 1.0}]

    norm_events = []
    for ev in sorted(events, key=lambda x: float(x["time"])):
        t = clamp(float(ev["time"]), 0.2, max(0.3, duration - 0.4))
        if "center" in ev:
            cx, cy = float(ev["center"][0]), float(ev["center"][1])
        elif "box" in ev:
            bx, by, bw, bh = [float(v) for v in ev["box"]]
            cx = clamp((bx + bw / 2.0) / sw, 0.08, 0.92)
            cy = clamp((by + bh / 2.0) / sh, 0.08, 0.92)
        else:
            cx, cy = 0.5, 0.5
        z = clamp(float(ev.get("zoom", default_zoom)), 1.15, 3.2)
        hold = float(ev.get("hold", 1.15))
        norm_events.append({"time": round(t, 3), "center": [round(cx, 4), round(cy, 4)], "zoom": round(z, 2), "hold": hold})

    keys: list[dict] = [{"time": 0.0, "center": [0.5, 0.5], "zoom": 1.0}]

    for i, ev in enumerate(norm_events):
        t_focus = ev["time"]
        c = ev["center"]
        z = ev["zoom"]
        t_start = max(keys[-1]["time"] + 0.05, round(t_focus - push_dur * 0.75, 3))
        t_arrive = max(t_start + 0.25, round(t_focus + push_dur * 0.25, 3))
        t_leave = min(round(duration - pull_dur - 0.1, 3), round(t_arrive + ev["hold"], 3))
        t_leave = max(t_arrive + 0.15, t_leave)

        prev = keys[-1]
        if prev["zoom"] == 1.0:
            if t_start > prev["time"] + 0.08:
                keys.append({"time": t_start, "center": [0.5, 0.5], "zoom": 1.0})
            keys.append({"time": t_arrive, "center": c, "zoom": z})
            keys.append({"time": t_leave, "center": c, "zoom": z})
        else:
            # Connected Pan from previous zoomed focus
            t_pan_end = max(prev["time"] + pan_dur, t_arrive)
            keys.append({"time": round(t_pan_end, 3), "center": c, "zoom": z})
            keys.append({"time": max(round(t_pan_end + 0.2, 3), t_leave), "center": c, "zoom": z})

        # Check if next event is far away in time -> pull out to 1.0x in between
        if i + 1 < len(norm_events):
            gap = norm_events[i + 1]["time"] - keys[-1]["time"]
            if gap > connect_threshold:
                t_reset = round(keys[-1]["time"] + pull_dur, 3)
                keys.append({"time": t_reset, "center": [0.5, 0.5], "zoom": 1.0})
        else:
            # Final pull out to full view at end of scene
            if keys[-1]["time"] < duration - 0.25:
                t_end = round(min(duration, keys[-1]["time"] + pull_dur), 3)
                keys.append({"time": t_end, "center": [0.5, 0.5], "zoom": 1.0})

    return keys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duration", type=float, required=True, help="Scene duration in seconds")
    ap.add_argument("--window-size", default="1920,1080", help="Source pixel width,height (default 1920,1080)")
    ap.add_argument("--events", required=True, help="JSON array of focus events")
    ap.add_argument("--default-zoom", type=float, default=1.8)
    args = ap.parse_args()

    w, h = [int(x.strip()) for x in args.window_size.split(",")]
    events = json.loads(args.events)
    keys = plan_keyframes(args.duration, (w, h), events, default_zoom=args.default_zoom)
    print(json.dumps({"camera": {"keyframes": keys}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
