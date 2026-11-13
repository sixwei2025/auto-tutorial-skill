#!/usr/bin/env python3
"""OpenScreen / Cap style deterministic camera push-pan-pull (zoom & pan) for video clips & stills.

Implements:
1. Quintic smooth easing (zero velocity & zero acceleration at endpoints, no overshoot):
   smooth(u) = u^3 * (6u^2 - 15u + 10)
2. Connected Pan (OpenScreen style): directly pan between focus coordinates without
   resetting to 1.0x between adjacent highlights unless requested.
3. Single-step inverse affine resampling (Bicubic) per frame: avoids double-scaling blur.
4. Semantic presets for fast editing:
   - --preset punch-in   : Quick 0.25s push to --zoom (default 1.18) around --center, hold, optional pull-out
   - --preset focus-hold : Smooth 0.55s push to --zoom (default 1.75) on UI/B-roll target, hold, smooth pull-out
   - --preset pan-across : Push in to point A, glide horizontally/diagonally to point B, pull out
   - --keyframes JSON    : Full custom keyframe list [{"time":0,"center":[0.5,0.5],"zoom":1.0}, ...]

Usage examples:
  # 1. A-roll talking head key sentence punch-in (1.18x)
  /opt/homebrew/bin/python3.11 zoom_pan.py input.mp4 -o out.mp4 --preset punch-in --zoom 1.18 --center 0.5,0.42

  # 2. B-roll UI tutorial focus push-in and pan across two controls
  /opt/homebrew/bin/python3.11 zoom_pan.py ui_clip.mp4 -o out.mp4 --preset pan-across --center 0.28,0.35 --to-center 0.72,0.55 --zoom 1.85

  # 3. Custom keyframes JSON
  /opt/homebrew/bin/python3.11 zoom_pan.py clip.mp4 -o out.mp4 --keyframes '[{"time":0,"center":[0.5,0.5],"zoom":1},{"time":0.6,"center":[0.3,0.4],"zoom":1.8},{"time":2.5,"center":[0.7,0.4],"zoom":1.8},{"time":3.2,"center":[0.5,0.5],"zoom":1}]'
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw


def smooth_quintic(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def sample_camera(keys: list[dict], t: float) -> tuple[float, float, float]:
    if t <= keys[0]["time"]:
        c = keys[0]["center"]
        return float(c[0]), float(c[1]), float(keys[0]["zoom"])
    for a, b in zip(keys, keys[1:]):
        if t <= b["time"]:
            span = max(1e-6, b["time"] - a["time"])
            q = (t - a["time"]) / span
            if b.get("ease", "smooth") != "linear":
                q = smooth_quintic(q)
            ax, ay, az = float(a["center"][0]), float(a["center"][1]), float(a["zoom"])
            bx, by, bz = float(b["center"][0]), float(b["center"][1]), float(b["zoom"])
            return ax + (bx - ax) * q, ay + (by - ay) * q, az + (bz - az) * q
    c = keys[-1]["center"]
    return float(c[0]), float(c[1]), float(keys[-1]["zoom"])


def camera_affine(state: tuple[float, float, float], source_size: tuple[int, int], viewport: tuple[int, int]):
    sw, sh = source_size
    vw_out, vh_out = viewport
    x, y, zoom = state
    base_scale = min(vw_out / sw, vh_out / sh)
    scale = base_scale * zoom
    vw, vh = vw_out / scale, vh_out / scale
    cx = sw / 2.0 if vw >= sw else max(vw / 2.0, min(sw - vw / 2.0, x * sw))
    cy = sh / 2.0 if vh >= sh else max(vh / 2.0, min(sh - vh / 2.0, y * sh))
    return (1.0 / scale, 0.0, cx - vw / 2.0, 0.0, 1.0 / scale, cy - vh / 2.0)


def parse_xy(val: str) -> list[float]:
    parts = [float(p.strip()) for p in val.split(",")]
    if len(parts) != 2 or not all(0.0 <= p <= 1.0 for p in parts):
        raise ValueError(f"Expected normalized 'x,y' in [0..1], got: {val}")
    return parts


def build_preset_keyframes(preset: str, duration: float, center: list[float], to_center: list[float], zoom: float) -> list[dict]:
    if preset == "punch-in":
        t_in = min(0.24, duration * 0.18)
        t_out_start = max(t_in + 0.2, duration - 0.28)
        return [
            {"time": 0.0, "center": [0.5, 0.5], "zoom": 1.0},
            {"time": round(t_in, 3), "center": center, "zoom": zoom},
            {"time": round(t_out_start, 3), "center": center, "zoom": zoom},
            {"time": round(duration, 3), "center": center, "zoom": zoom},
        ]
    if preset == "focus-hold":
        t_hold_start = min(0.55, duration * 0.22)
        t_hold_end = max(t_hold_start + 0.3, duration - min(0.55, duration * 0.22))
        return [
            {"time": 0.0, "center": [0.5, 0.5], "zoom": 1.0},
            {"time": round(t_hold_start, 3), "center": center, "zoom": zoom},
            {"time": round(t_hold_end, 3), "center": center, "zoom": zoom},
            {"time": round(duration, 3), "center": [0.5, 0.5], "zoom": 1.0},
        ]
    if preset == "pan-across":
        t1 = min(0.55, duration * 0.18)
        t2 = min(duration * 0.42, max(t1 + 0.2, duration * 0.38))
        t3 = max(t2 + 0.3, duration * 0.68)
        t4 = max(t3 + 0.2, duration - min(0.55, duration * 0.16))
        return [
            {"time": 0.0, "center": [0.5, 0.5], "zoom": 1.0},
            {"time": round(t1, 3), "center": center, "zoom": zoom},
            {"time": round(t2, 3), "center": center, "zoom": zoom},
            {"time": round(t3, 3), "center": to_center, "zoom": zoom},
            {"time": round(t4, 3), "center": to_center, "zoom": zoom},
            {"time": round(duration, 3), "center": [0.5, 0.5], "zoom": 1.0},
        ]
    raise ValueError(f"Unknown preset: {preset}")


def probe_media(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
    r = subprocess.run(
        [ffprobe, "-v", "error", "-show_Format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True
    )
    info = json.loads(r.stdout)
    vstream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    astream = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not vstream:
        raise ValueError(f"No video/image stream in {path}")
    w = int(vstream["width"])
    h = int(vstream["height"])
    dur = float(info.get("format", {}).get("duration") or vstream.get("duration") or 0.0)
    fps_str = vstream.get("r_frame_rate", "30/1")
    num, den = (int(x) for x in fps_str.split("/")) if "/" in fps_str else (float(fps_str), 1)
    fps = num / den if den else 30.0
    return {"width": w, "height": h, "duration": dur, "fps": fps, "has_audio": astream is not None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="Input video (.mp4/.mov) or still image (.png/.jpg)")
    ap.add_argument("-o", "--output", required=True, help="Output MP4 path")
    ap.add_argument("--preset", choices=["punch-in", "focus-hold", "pan-across"], default="focus-hold")
    ap.add_argument("--center", default="0.5,0.45", help="Focus center 'x,y' in [0..1] (default 0.5,0.45)")
    ap.add_argument("--to-center", default="0.65,0.55", help="Second focus center for pan-across")
    ap.add_argument("--zoom", type=float, default=1.75, help="Target zoom factor (1.05 to 4.0, default 1.75)")
    ap.add_argument("--keyframes", help="Explicit JSON list of keyframes [{'time':0,'center':[x,y],'zoom':z}, ...]")
    ap.add_argument("--duration", type=float, help="Override duration in seconds (required for still image)")
    ap.add_argument("--width", type=int, help="Output width (default: source width)")
    ap.add_argument("--height", type=int, help="Output height (default: source height)")
    ap.add_argument("--fps", type=int, default=30, help="Output FPS (default 30)")
    ap.add_argument("--highlight-box", help="Optional red focus box 'x,y,w,h' normalized [0..1] drawn when zoomed")
    ap.add_argument("--json", action="store_true", help="Print JSON summary")
    args = ap.parse_args()

    src = Path(args.input).resolve()
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

    is_still = src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    meta = probe_media(src)
    duration = args.duration or meta["duration"]
    if duration <= 0:
        raise ValueError("Duration must be > 0 (pass --duration for still images)")

    out_w = args.width or meta["width"]
    out_h = args.height or meta["height"]
    fps = args.fps

    center = parse_xy(args.center)
    to_center = parse_xy(args.to_center)
    keys = json.loads(args.keyframes) if args.keyframes else build_preset_keyframes(
        args.preset, duration, center, to_center, args.zoom
    )

    hbox = None
    if args.highlight_box:
        hbox = [float(v.strip()) for v in args.highlight_box.split(",")]
        if len(hbox) != 4:
            raise ValueError("--highlight-box expects 'x,y,w,h' in normalized [0..1]")

    total_frames = max(1, round(duration * fps))

    with tempfile.TemporaryDirectory(prefix="zoom_pan_") as tmpdir:
        tmp = Path(tmpdir)
        frames_in = tmp / "in"
        frames_out = tmp / "out"
        frames_in.mkdir()
        frames_out.mkdir()

        if is_still:
            base_img = Image.open(src).convert("RGB")
            src_frames = [base_img]
        else:
            subprocess.run(
                [ffmpeg, "-y", "-v", "error", "-i", str(src), "-an",
                 "-vf", f"fps={fps}", "-frames:v", str(total_frames),
                 "-start_number", "0", str(frames_in / "%06d.png")],
                check=True
            )
            decoded_paths = sorted(frames_in.glob("*.png"))
            if not decoded_paths:
                raise RuntimeError(f"Decoded 0 frames from {src}")

        for i in range(total_frames):
            t = i / fps
            if is_still:
                im = src_frames[0]
            else:
                idx = min(len(decoded_paths) - 1, i)
                im = Image.open(decoded_paths[idx]).convert("RGB")

            if hbox and sample_camera(keys, t)[2] > 1.12:
                im = im.copy()
                draw = ImageDraw.Draw(im)
                sw, sh = im.size
                bx, by, bw, bh = hbox[0] * sw, hbox[1] * sh, hbox[2] * sw, hbox[3] * sh
                draw.rounded_rectangle(
                    (bx, by, bx + bw, by + bh),
                    radius=16, outline="#C8102E", width=max(4, round(sw * 0.0035))
                )

            state = sample_camera(keys, t)
            aff = camera_affine(state, im.size, (out_w, out_h))
            rendered = im.transform(
                (out_w, out_h), Image.Transform.AFFINE, aff,
                Image.Resampling.BICUBIC, fillcolor="#141312"
            )
            rendered.save(frames_out / f"{i:06d}.jpg", quality=95, subsampling=0)

        cmd = [
            ffmpeg, "-y", "-v", "error",
            "-framerate", str(fps),
            "-i", str(frames_out / "%06d.jpg"),
        ]
        if not is_still and meta["has_audio"]:
            cmd += ["-i", str(src), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        else:
            cmd += ["-an"]
        cmd += [
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out)
        ]
        subprocess.run(cmd, check=True)

    summary = {
        "status": "ok",
        "input": str(src),
        "output": str(out),
        "duration": round(duration, 3),
        "resolution": f"{out_w}x{out_h}",
        "fps": fps,
        "frames": total_frames,
        "keyframes": keys,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Done: {out} ({duration:.2f}s, {out_w}x{out_h}@{fps}fps, {len(keys)} keyframes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
