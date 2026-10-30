#!/usr/bin/env python3
"""Step｜桌面/窗口录屏（不用 avfoundation，靠连续截屏再合成）

用途：录 WorkBuddy 桌面 App、录浏览器里的真实操作（会滚动的表格、点开的面板），
     做成 clips/*.mp4，再用 patch_frames.py 嵌进视频画面区。

用法：
  TV_PROJECT=/path python3 record_screen.py --seconds 8 --fps 10 --name feishu-scroll
  # 只录屏幕某块区域（x,y,w,h 为物理像素）
  TV_PROJECT=/path python3 record_screen.py --seconds 6 --name panel --region 0,380,2940,1532

说明：
- macOS 用 `screencapture -x`，Windows 用 PowerShell 截屏，Linux 用 `import -window root`
- 录制期间不要操作鼠标键盘（会录进去），让 Agent 用 CUA 去驱动画面
"""
raise SystemExit("此旧采集入口已停用：使用真实操作关键截图，参见 references/real-operation.md。")

import os
import platform
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, ffmpeg

args = sys.argv[1:]


def opt(flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


seconds = float(opt("--seconds", "6"))
fps = float(opt("--fps", "10"))
name = opt("--name", "screen")
region = opt("--region")
keep = "--keep" in args

CLIPS = os.path.join(PROJECT, "clips")
TMP = os.path.join(PROJECT, ".rec_tmp", name)
os.makedirs(CLIPS, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

OS = platform.system()


def grab(dst):
    if OS == "Darwin":
        cmd = ["screencapture", "-x"]
        if region:
            cmd += ["-R", region]
        cmd.append(dst)
    elif OS == "Windows":
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
            "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($bmp);"
            "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
            "'%s';$bmp.Save('%s')" % ("", dst)
        )
        cmd = ["powershell", "-NoProfile", "-Command", ps]
    else:
        cmd = ["import", "-window", "root", dst]
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode == 0


n = 0
t0 = time.time()
interval = 1.0 / fps
print("▶ 录制 %ss @ %sfps → clips/%s.mp4（现在开始动画面）" % (seconds, fps, name), flush=True)
while time.time() - t0 < seconds:
    frame = os.path.join(TMP, "f%05d.png" % n)
    if grab(frame):
        n += 1
    nxt = t0 + (n + 1) * interval
    sleep = nxt - time.time()
    if sleep > 0:
        time.sleep(sleep)

if n < 2:
    raise SystemExit("只抓到 %d 帧，录屏失败（检查屏幕录制权限）" % n)

out = os.path.join(CLIPS, "%s.mp4" % name)
r = subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                    "-framerate", "%g" % fps, "-i", os.path.join(TMP, "f%05d.png"),
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", out], capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-800:])
    raise SystemExit("合成失败")

dur = n / fps
print("✅ clips/%s.mp4  %d 帧 / %.2fs" % (name, n, dur))
print("   下一步：在 project.json 的 scene 上加 \"clip\": {\"file\": \"clips/%s.mp4\"}，跑 --from frames" % name)
if not keep:
    # 帧数过多时不要批量删——本机的安全钩子会在第 50 个文件上直接掐断进程。
    # 留着不碍事（都在 .rec_tmp/ 里），要清就手动删目录。
    files = os.listdir(TMP)
    if len(files) <= 40:
        for f in files:
            try:
                os.remove(os.path.join(TMP, f))
            except OSError:
                pass
    else:
        print("   （%d 张中间帧留在 %s，安全钩子不允许批量删，可手动清理）" % (len(files), TMP))
