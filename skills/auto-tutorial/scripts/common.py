#!/usr/bin/env python3
"""跨平台公共件：VoiceBox 自动发现 / ffmpeg 定位 / Chrome 启动 / 中文字体

macOS / Windows / Linux 通用。所有脚本都从这里取环境，不写死任何路径。
"""
import json
import os
import platform
import re
import shutil
import urllib.request

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))

_CFG = None


def cfg():
    """读取项目配置（缓存）。"""
    global _CFG
    if _CFG is None:
        p = os.path.join(PROJECT, "project.json")
        _CFG = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    return _CFG


# ---------------------------------------------------------------- 可执行文件
_bin_cache = {}


def find_bin(name, hint=None):
    """定位 ffmpeg / ffprobe 等外部程序，找不到就给出各平台安装提示。"""
    if name in _bin_cache:
        return _bin_cache[name]

    exe = name + (".exe" if IS_WIN else "")
    found = shutil.which(name) or shutil.which(exe) or (hint and os.path.exists(hint) and hint)

    if not found:
        cands = []
        if IS_WIN:
            cands += [
                r"C:\ffmpeg\bin\%s" % exe,
                r"C:\Program Files\ffmpeg\bin\%s" % exe,
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\%s" % exe),
                os.path.expandvars(r"%USERPROFILE%\scoop\shims\%s" % exe),
                os.path.expandvars(r"%ProgramData%\chocolatey\bin\%s" % exe),
            ]
        elif IS_MAC:
            cands += ["/opt/homebrew/bin/%s" % name, "/usr/local/bin/%s" % name]
        else:
            cands += ["/usr/bin/%s" % name, "/usr/local/bin/%s" % name, "/snap/bin/%s" % name]
        found = next((c for c in cands if c and os.path.exists(c)), None)

    if not found:
        tip = {
            "win": "winget install Gyan.FFmpeg  或  scoop install ffmpeg",
            "mac": "brew install ffmpeg",
            "linux": "sudo apt install ffmpeg",
        }["win" if IS_WIN else "mac" if IS_MAC else "linux"]
        raise SystemExit("找不到 %s，请先安装：%s" % (name, tip))

    _bin_cache[name] = found
    return found


def ffmpeg():
    return find_bin("ffmpeg")


def ffprobe():
    return find_bin("ffprobe")


def media_duration(path):
    import subprocess
    out = subprocess.run([ffprobe(), "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


# ------------------------------------------------------------------- 浏览器
def launch_browser(p, args=None, dsf=1):
    """启动浏览器：优先系统 Chrome，其次 Edge，最后 Playwright 自带内核。

    绕开「Python playwright 与缓存内核版本不匹配」这个坑。
    """
    args = args or ["--force-device-scale-factor=%d" % dsf, "--hide-scrollbars"]
    forced = os.environ.get("TV_BROWSER", "").strip()
    tries = [{"channel": forced}] if forced else [{"channel": "chrome"}, {"channel": "msedge"}]
    errs = []
    for kw in tries:
        try:
            return p.chromium.launch(args=args, **kw)
        except Exception as e:
            errs.append("%s: %s" % (kw["channel"], str(e).splitlines()[0][:70]))
    try:
        return p.chromium.launch(args=args)
    except Exception as e:
        errs.append("bundled: %s" % str(e).splitlines()[0][:70])
    raise SystemExit("启动浏览器失败（试过 Chrome / Edge / 内置内核）：\n  " + "\n  ".join(errs))


# --------------------------------------------------------------------- 字体
def font_css():
    return ('"PingFang SC","Hiragino Sans GB","Microsoft YaHei UI","Microsoft YaHei",'
            '"Noto Sans CJK SC","Source Han Sans SC",system-ui,sans-serif')


def mono_css():
    return '"SF Mono","JetBrains Mono",Consolas,"Cascadia Mono","Courier New",monospace'


def ass_font():
    """ASS 字幕字体名（烧录用，按平台选可用中文字体）。"""
    if IS_WIN:
        return "Microsoft YaHei"
    if IS_MAC:
        return "PingFang SC"
    return "Noto Sans CJK SC"


def pil_font(size, bold=False):
    """PIL 用中文字体（macOS PingFang / Windows 微软雅黑 / Linux Noto）。"""
    from PIL import ImageFont
    cands = []
    if IS_WIN:
        cands = [(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc", 0),
                 (r"C:\Windows\Fonts\msyh.ttc", 0),
                 (r"C:\Windows\Fonts\simhei.ttf", 0)]
    elif IS_MAC:
        cands = [("/System/Library/Fonts/PingFang.ttc", 1 if bold else 0),
                 ("/System/Library/Fonts/PingFang.ttc", 0),
                 ("/System/Library/Fonts/STHeiti Medium.ttc", 0)]
    else:
        cands = [("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold
                  else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
                 ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
                 ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0)]
    for path, idx in cands:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=idx)
            except Exception:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
    return ImageFont.load_default()


_TOFU_SIG = {}


def pil_char_ok(ch, size=40, bold=True):
    """字体里到底有没有这个字形。

    不能只看 getmask 有没有像素 —— 缺字形时字体会画「豆腐块」，也是有像素的。
    办法：渲染私用区字符 U+E000 当基准豆腐块，和它一模一样就是缺字形。
    实测 macOS PingFang：✓ ✔ 都是豆腐块，√ → ● ○ ▶ 正常。
    """
    key = (size, bold)
    f = pil_font(size, bold=bold)
    if key not in _TOFU_SIG:
        _TOFU_SIG[key] = (f, bytes(f.getmask("\ue000")))
    font, tofu = _TOFU_SIG[key]
    try:
        return bytes(font.getmask(ch)) != tofu
    except Exception:
        return False


def pil_mark(kind, size=26):
    """清单状态符号：优先语义字符，缺字形自动降级到几何符号。"""
    chain = {
        "done": ["\\u221a", "\\u25cf", "V"],
        "current": ["\\u2192", "\\u25b6", ">"],
        "todo": ["\\u25cb", "\\u00b7", "o"],
    }.get(kind, ["\\u00b7"])
    for ch in chain:
        if len(ch) > 1:
            ch = ch.encode().decode("unicode_escape")
        if pil_char_ok(ch, size=size, bold=True):
            return ch
    return "-"



# ------------------------------------------------------------------ VoiceBox
def vb_api():
    v = cfg().get("voice", {})
    return (v.get("api") or os.environ.get("VOICEBOX_API")
            or "http://127.0.0.1:17493").rstrip("/")


def vb_get(path, timeout=25):
    with urllib.request.urlopen(vb_api() + path, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    for line in raw.splitlines():          # status 接口返回 SSE，需剥 data: 前缀
        line = line.strip()
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return json.loads(raw)


def vb_alive():
    try:
        vb_get("/health", timeout=4)
        return True
    except Exception:
        return False


def vb_profiles():
    data = vb_get("/profiles")
    return data if isinstance(data, list) else data.get("profiles", [])


def vb_profile(name=None, pid=None):
    """按 id 或名字取音色，返回完整 profile（含 default_engine）。"""
    arr = vb_profiles()
    if pid:
        return next((p for p in arr if p.get("id") == pid), None)
    for p in arr:
        if p.get("name") == name or p.get("display_name") == name:
            return p
    names = ", ".join(str(p.get("name")) for p in arr[:12])
    raise SystemExit("VoiceBox 里找不到音色「%s」。现有：%s" % (name, names))


def vb_data_dir():
    """VoiceBox 生成音频的落盘目录，macOS / Windows / Linux 自动探测。

    优先级：project.json → 环境变量 → API 自报 → 各平台默认路径。
    """
    v = cfg().get("voice", {})
    explicit = v.get("data_dir") or os.environ.get("VOICEBOX_DATA_DIR")
    if explicit:
        return os.path.expanduser(os.path.expandvars(explicit))

    if IS_MAC:
        roots = ["~/Library/Application Support/sh.voicebox.app"]
    elif IS_WIN:
        roots = [os.path.expandvars(r"%APPDATA%\sh.voicebox.app"),
                 os.path.expandvars(r"%LOCALAPPDATA%\sh.voicebox.app"),
                 os.path.expandvars(r"%APPDATA%\com.voicebox.app"),
                 r"C:\ProgramData\sh.voicebox.app"]
    else:
        roots = ["$XDG_DATA_HOME/sh.voicebox.app", "~/.local/share/sh.voicebox.app",
                 "~/.config/sh.voicebox.app"]

    for r in roots:
        base = os.path.expanduser(os.path.expandvars(r))
        g = os.path.join(base, "generations")
        if os.path.isdir(g):
            return g

    # API 自报路径（跨平台最可靠）
    for ep in ("/health/filesystem", "/health"):
        try:
            blob = json.dumps(vb_get(ep, timeout=6), ensure_ascii=False)
        except Exception:
            continue
        for m in re.finditer(r'"(?:[^"]*?(?:generations|voicebox)[^"]*?)"', blob, re.I):
            raw = m.group(0).strip('"').replace("\\\\", "\\").replace("\\/", "/")
            for cand in (raw, os.path.join(raw, "generations")):
                if os.path.isdir(cand):
                    return cand

    raise SystemExit(
        "找不到 VoiceBox 音频目录。请在 project.json 里补一句：\n"
        '  "voice": { "data_dir": "你的 generations 目录" }\n'
        "或设置环境变量 VOICEBOX_DATA_DIR。")


def vb_audio(job_id, gen_dir=None):
    """按任务 id 找到生成的音频文件（兼容 wav / mp3 / flac）。"""
    gen_dir = gen_dir or vb_data_dir()
    for ext in ("wav", "WAV", "mp3", "flac", "m4a", "ogg"):
        p = os.path.join(gen_dir, "%s.%s" % (job_id, ext))
        if os.path.exists(p):
            return p
    for root, _dirs, files in os.walk(gen_dir):
        for f in files:
            if f.startswith(job_id):
                return os.path.join(root, f)
    return None
