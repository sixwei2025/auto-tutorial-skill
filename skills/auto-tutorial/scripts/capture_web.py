#!/usr/bin/env python3
"""Step D｜网页取画面：自动打开 URL，按脚本点击 / 输入 / 滚动，截出真实界面图或轻录屏

用法：TV_PROJECT=/path python3 capture_web.py [--force]

配置写在 project.json 的 capture 段：
{
  "capture": {
    "url": "https://www.workbuddy.cn",
    "viewport": [1200, 675],
    "dpr": 2,
    "settle": 1500,
    "steps": [
      {"action": "shot", "name": "01-home"},
      {"action": "click", "selector": "text=功能"},
      {"action": "wait", "ms": 800},
      {"action": "shot", "name": "02-feature"},
      {"action": "scroll", "dy": 900, "frames": 14, "name": "scroll-demo"}
    ]
  }
}

产出：
  assets/captured/<name>.png    真实界面截图（2x）
  clips/<name>.mp4              轻录屏（逐帧截图 + ffmpeg 合成，给 patch_frames 用）
  capture.json                  取了哪些画面、尺寸、来源 URL
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, cfg, ffmpeg, launch_browser

from playwright.sync_api import sync_playwright

C = cfg().get("capture", {})
FORCE = "--force" in sys.argv

if not C or not C.get("url"):
    raise SystemExit("project.json 里没有 capture 配置。示例：\n"
                     '"capture": {"url": "https://...", "steps": [{"action": "shot", "name": "01"}]}')

VW, VH = C.get("viewport", [1200, 675])
DPR = int(C.get("dpr", 2))
SHOTS = os.path.join(PROJECT, "assets", "captured")
CLIPS = os.path.join(PROJECT, "clips")
TMP = os.path.join(PROJECT, ".capture_tmp")
for d in (SHOTS, CLIPS, TMP):
    os.makedirs(d, exist_ok=True)

FPS = int(C.get("fps", 12))


def save_shot(pg, name):
    p = os.path.join(SHOTS, "%s.png" % name)
    if os.path.exists(p) and not FORCE:
        print("  [skip] %s" % name)
        return None
    pg.screenshot(path=p)
    print("  [shot] %-22s %dx%d" % (name, VW * DPR, VH * DPR))
    return "assets/captured/%s.png" % name


def assemble(count, out_name, fps=FPS):
    """逐帧截图 → mp4（轻录屏）。count = 帧数。"""
    if not count:
        return None
    out = os.path.join(CLIPS, "%s.mp4" % out_name)
    pattern = os.path.join(TMP, "f%04d.jpg")
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-framerate", str(fps), "-i", pattern,
           "-vf", "scale=%d:%d:flags=lanczos" % (VW * DPR, VH * DPR),
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("  ⚠ 录屏合成失败：", r.stderr[-300:])
        return None
    dur = round(count / fps, 2)
    print("  [clip] %-22s %ss / %d 帧" % (out_name, dur, count))
    return {"file": "clips/%s.mp4" % out_name, "duration": dur, "frames": count}


def main():
    shots, clips = [], []
    steps = C.get("steps", [{"action": "shot", "name": "01-page"}])

    with sync_playwright() as p:
        b = launch_browser(p)
        pg = b.new_page(viewport={"width": VW, "height": VH}, device_scale_factor=DPR)
        print("▶ 打开 %s" % C["url"])
        pg.goto(C["url"], wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(int(C.get("settle", 1500)))

        for i, st in enumerate(steps, 1):
            act = st.get("action", "shot")
            label = "%d/%d %s" % (i, len(steps), act)
            try:
                if act == "click":
                    pg.click(st["selector"], timeout=15000)
                    print("  [click] %s" % st["selector"][:46])
                    pg.wait_for_timeout(int(st.get("ms", 700)))
                elif act == "hover":
                    pg.hover(st["selector"], timeout=15000)
                    print("  [hover] %s" % st["selector"][:46])
                    pg.wait_for_timeout(int(st.get("ms", 500)))
                elif act == "type":
                    pg.fill(st["selector"], st.get("text", ""), timeout=15000)
                    print("  [type ] %s ← %s" % (st["selector"][:36], st.get("text", "")[:20]))
                    pg.wait_for_timeout(int(st.get("ms", 400)))
                elif act == "press":
                    pg.keyboard.press(st.get("key", "Enter"))
                    pg.wait_for_timeout(int(st.get("ms", 600)))
                elif act == "wait":
                    pg.wait_for_timeout(int(st.get("ms", 800)))
                elif act == "goto":
                    pg.goto(st["url"], wait_until="domcontentloaded", timeout=60000)
                    pg.wait_for_timeout(int(st.get("ms", 1200)))
                elif act == "scroll":
                    n = int(st.get("frames", 14))
                    dy = int(st.get("dy", 800))
                    step_px = dy / max(1, n - 1)
                    for f in range(n):
                        if f:
                            pg.mouse.wheel(0, step_px)
                        pg.wait_for_timeout(int(st.get("gap", 45)))
                        pg.screenshot(path=os.path.join(TMP, "f%04d.jpg" % f),
                                      type="jpeg", quality=92)
                    info = assemble(n, st.get("name", "clip%02d" % i))
                    if info:
                        clips.append(dict(info, source=C["url"], action="scroll"))
                    for f in range(n):
                        try:
                            os.remove(os.path.join(TMP, "f%04d.jpg" % f))
                        except OSError:
                            pass
                elif act == "shot":
                    name = st.get("name", "shot%02d" % i)
                    f = save_shot(pg, name)
                    if f:
                        shots.append({"name": name, "file": f, "width": VW * DPR,
                                      "height": VH * DPR, "source": C["url"],
                                      "note": st.get("note", "")})
                else:
                    print("  ⚠ 未知动作 %s（%s）" % (act, label))
            except Exception as e:
                print("  ✗ 步骤 %s 失败：%s" % (label, str(e).splitlines()[0][:90]))
                if st.get("required", act in ("shot",)):
                    raise SystemExit("关键步骤失败，中止")

        b.close()

    os.rmdir(TMP) if os.path.isdir(TMP) and not os.listdir(TMP) else None
    out = {"url": C["url"], "viewport": [VW * DPR, VH * DPR],
           "shots": shots, "clips": clips}
    json.dump(out, open(os.path.join(PROJECT, "capture.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n✅ 截图 %d 张 → assets/captured/ ｜ 轻录屏 %d 段 → clips/" % (len(shots), len(clips)))
    for s in shots:
        print("   %-22s %s" % (s["name"], s["file"]))


if __name__ == "__main__":
    main()
