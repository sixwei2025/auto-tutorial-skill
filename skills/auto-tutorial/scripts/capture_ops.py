#!/usr/bin/env python3
"""Step｜真实操作录制（演示光标 / 点击涟漪 / 逐字打字 / 平滑滚动 / 高亮框）

解决 capture_web.py 的四个硬伤：
  1. 画面里没有鼠标指针、没有点击反馈 —— 观众看不出「点了哪里」
  2. 滚动是硬跳，帧率不均，动效一顿一顿
  3. 每次全新实例、没有登录态 —— 后台/创作者中心这类页面截不到
  4. 滚动失败不报错 —— 产出一段静止画面还以为录成功了

架构（关键）：不让浏览器自己跑定时器/动画。
  所有动作编译成一条「纯函数时间轴」__tvSeek(t)，
  Python 每截一帧就把真实经过的时间喂进去，算出该帧的光标位置、
  滚动位置、打字进度、涟漪半径、高亮框显隐。
  这样帧和状态永远对齐，也不受 headless 下 rAF 不推进的影响。

用法：
  # 首次：打开带界面的浏览器，你自己登录一次（登录态存进专用 profile）
  TV_PROJECT=$PWD python3 capture_ops.py --profile --login

  # 之后：复用登录态，全自动录
  TV_PROJECT=$PWD python3 capture_ops.py --name demo

配置写在 project.json 的 ops 段（或 --ops ops.json）：

"ops": {
  "url": "https://www.workbuddy.cn",
  "viewport": [1200, 675], "dpr": 2,
  "settle": 2500,
  "steps": [
    {"op": "move",   "to": "text=功能", "dur": 700},
    {"op": "click",  "to": "text=功能", "hold": 300},
    {"op": "mark",   "to": ".feature-card", "dur": 1600, "label": "就是这里"},
    {"op": "scroll", "dy": 900, "dur": 1200},
    {"op": "type",   "to": "input[type=search]", "text": "workbuddy", "cps": 9},
    {"op": "key",    "key": "Enter", "ms": 700},
    {"op": "shot",   "name": "05-result"}
  ]
}

动作：move / click / dblclick / type / key / scroll / mark / wait / shot
"""
raise SystemExit("此旧采集入口已停用：使用真实操作关键截图，参见 references/real-operation.md。")

import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import IS_MAC, IS_WIN, PROJECT, cfg, ffmpeg

from playwright.sync_api import sync_playwright

ARGS = sys.argv[1:]


def opt(flag, default=None):
    if flag in ARGS and ARGS.index(flag) + 1 < len(ARGS):
        return ARGS[ARGS.index(flag) + 1]
    return default


OPS = cfg().get("ops", {})
if "--ops" in ARGS:
    OPS = json.load(open(opt("--ops"), encoding="utf-8"))

NAME = opt("--name") or OPS.get("name") or "ops"
URL = opt("--url") or OPS.get("url")
VW, VH = OPS.get("viewport", [1200, 675])
DPR = int(OPS.get("dpr", 2))
SETTLE = int(OPS.get("settle", 2500))
STEPS = OPS.get("steps", [])
USE_PROFILE = "--profile" in ARGS or bool(OPS.get("profile"))
HEADLESS = "--headed" not in ARGS
QUALITY = int(OPS.get("quality", 85))

if not URL and not ({"--login", "--profile"} & set(ARGS)) and not STEPS:
    raise SystemExit(__doc__)

CLIPS = os.path.join(PROJECT, "clips")
SHOTS = os.path.join(PROJECT, "assets", "captured")
TMP = os.path.join(PROJECT, ".ops_tmp", NAME)
for d in (CLIPS, SHOTS, TMP):
    os.makedirs(d, exist_ok=True)


def profile_dir():
    if IS_MAC:
        base = os.path.expanduser("~/Library/Application Support/tv-capture-profile")
    elif IS_WIN:
        base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "tv-capture-profile")
    else:
        base = os.path.expanduser("~/.local/share/tv-capture-profile")
    return OPS.get("profile_dir") or base


# ------------------------------------------------------------------ 注入层
INJECT_CSS = r"""
#__tvcursor{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483646;
  pointer-events:none;will-change:transform;filter:drop-shadow(0 2px 3px rgba(0,0,0,.38));}
#__tvring{position:fixed;z-index:2147483645;pointer-events:none;border-radius:50%;
  border:3px solid #C7352D;opacity:0;transform:translate(-50%,-50%) scale(.5);}
#__tvmark{position:fixed;z-index:2147483644;pointer-events:none;
  border:3px solid #C7352D;border-radius:10px;opacity:0;
  box-shadow:0 0 0 10px rgba(199,53,45,0),0 0 0 1px rgba(199,53,45,.25);}
#__tvlabel{position:fixed;z-index:2147483645;pointer-events:none;
  font:600 15px/1 "PingFang SC","Microsoft YaHei",system-ui,sans-serif;color:#fff;
  background:#C7352D;padding:6px 11px;border-radius:7px;opacity:0;
  box-shadow:0 3px 10px rgba(0,0,0,.25);white-space:nowrap;}
"""

CURSOR_SVG = (
    '<svg viewBox="0 0 26 26" width="26" height="26">'
    '<path d="M4.5 2.2 L4.5 20.4 L9.4 15.6 L12.6 23.4 L16.2 21.6 L13 13.9 L19.4 13.5 Z" '
    'fill="#ffffff" stroke="#141110" stroke-width="1.7" stroke-linejoin="round"/></svg>'
)

# 纯函数时间轴：seek(t) 决定这一帧的全部状态，不依赖 rAF / setTimeout
SEEK_JS = r"""
window.__tvMiss = [];
const __tvPlan = __TV_PLAN__;
const $ = id => document.getElementById(id);
const cur = $('__tvcursor'), ring = $('__tvring'),
      mark = $('__tvmark'), label = $('__tvlabel');
const ease = t => t < .5 ? 2*t*t : 1 - Math.pow(-2*t+2, 2)/2;
const clamp01 = v => v < 0 ? 0 : (v > 1 ? 1 : v);

function el(spec){
  if (!spec || Array.isArray(spec)) return null;
  try {
    if (spec.indexOf('text=') === 0){
      const want = spec.slice(5);
      const all = document.querySelectorAll('a,button,div,span,li,td,th,h1,h2,h3,p,label,input');
      for (const e of all){
        if (e.children.length > 3) continue;
        const t = (e.innerText || e.value || '').trim();
        if (t && t.length < 40 && t.indexOf(want) >= 0){
          const r = e.getBoundingClientRect();
          if (r.width > 6 && r.height > 6) return e;
        }
      }
      return null;
    }
    return document.querySelector(spec);
  } catch(e){ return null; }
}

function fire(e, type, x, y){
  e.dispatchEvent(new MouseEvent(type, {bubbles:true, cancelable:true, view:window,
                                        clientX:x, clientY:y}));
}

function setNativeValue(e, v){
  const proto = e instanceof HTMLTextAreaElement ? HTMLTextAreaElement
              : (e instanceof HTMLSelectElement ? HTMLSelectElement : HTMLInputElement.prototype);
  const d = Object.getOwnPropertyDescriptor(proto, 'value');
  if (d && d.set) d.set.call(e, v);
  else e.value = v;
  e.dispatchEvent(new Event('input', {bubbles:true}));
  e.dispatchEvent(new Event('change', {bubbles:true}));
}

// 光标位置：在所有 move 段之间做缓动插值
function cursorAt(t){
  let pos = __tvPlan.cursor0.slice();
  for (const m of __tvPlan.moves){
    if (t >= m[2]) pos = [m[3], m[4]];
    else if (t > m[0]) {
      const p = ease(clamp01((t - m[0]) / Math.max(1, m[2] - m[0])));
      pos = [m[1][0] + (m[3]-m[1][0])*p, m[1][1] + (m[4]-m[1][1])*p];
      break;
    } else break;
  }
  return pos;
}

window.__tvSeek = function(t){
  // 1) 光标
  const p = cursorAt(t);
  if (cur) cur.style.transform = 'translate(' + (p[0]-3) + 'px,' + (p[1]-2) + 'px)';

  // 2) 滚动（增量累加，纯函数）
  let sy = __tvPlan.scroll0;
  for (const s of __tvPlan.scrolls){
    if (t <= s[0]) break;
    const p2 = t >= s[2] ? 1 : ease(clamp01((t - s[0]) / Math.max(1, s[2] - s[0])));
    sy += s[1] * p2;
  }
  if (window.__tvLastScroll === null || window.__tvLastScroll === undefined ||
      Math.abs(sy - window.__tvLastScroll) > .5){
    window.scrollTo(0, sy);
    window.__tvLastScroll = sy;
  }

  // 3) 涟漪
  let ringOn = false;
  for (const c of __tvPlan.clicks){
    const dt = t - c[0];
    if (dt >= 0 && dt <= 480){
      const q = dt / 480;
      ring.style.left = c[1] + 'px';
      ring.style.top = c[2] + 'px';
      ring.style.opacity = String((1 - q) * .95);
      ring.style.transform = 'translate(-50%,-50%) scale(' + (0.5 + q * 4.2) + ')';
      ringOn = true;
    }
  }
  if (!ringOn && ring) ring.style.opacity = '0';

  // 4) 高亮框 + 标签
  let mk = null;
  for (const m of __tvPlan.marks){
    if (t >= m[0] && t <= m[1]) { mk = m; break; }
  }
  if (mk && mark){
    const e = el(mk[2]);
    if (e){
      const r = e.getBoundingClientRect();
      mark.style.left = (r.left - 6) + 'px';
      mark.style.top = (r.top - 6) + 'px';
      mark.style.width = (r.width + 12) + 'px';
      mark.style.height = (r.height + 12) + 'px';
      mark.style.opacity = '1';
      const breath = 6 + 6 * Math.abs(Math.sin((t - mk[0]) / 520));
      mark.style.boxShadow = '0 0 0 ' + breath + 'px rgba(199,53,45,.16)';
      if (mk[3] && label){
        label.textContent = mk[3];
        label.style.left = (r.left - 6) + 'px';
        label.style.top = Math.max(6, r.top - 40) + 'px';
        label.style.opacity = '1';
      }
    }
  } else if (mark){
    mark.style.opacity = '0';
    if (label) label.style.opacity = '0';
  }

  // 5) 打字（按 cps 推进字符）
  for (const ty of __tvPlan.types){
    const p3 = clamp01((t - ty[0]) / Math.max(1, ty[1] - ty[0]));
    const target = ty[3].slice(0, Math.round(ty[3].length * p3));
    if (target !== ty[4]){
      const e = el(ty[2]);
      if (e) { setNativeValue(e, target); e.focus(); }
      ty[4] = target;
    }
  }

  // 6) 一次性事件：点击 / 按键 / 单独截图（跨过时刻才触发）
  for (const ev of __tvPlan.events){
    if (t >= ev[0] && !ev[5]){
      ev[5] = true;
      const e = el(ev[3]);
      if (ev[1] === 'click' && e){
        fire(e,'mouseover',ev[6],ev[7]); fire(e,'mousemove',ev[6],ev[7]);
        fire(e,'mousedown',ev[6],ev[7]); fire(e,'mouseup',ev[6],ev[7]);
        e.focus && e.focus();
        e.click();
      } else if (ev[1] === 'key'){
        const t2 = e || document.body;
        t2.dispatchEvent(new KeyboardEvent('keydown', {key:ev[4], bubbles:true}));
        t2.dispatchEvent(new KeyboardEvent('keyup', {key:ev[4], bubbles:true}));
      }
    }
  }
};

window.__tvSeek(0);
window.__tvReady = true;
"""


def px_of(pg, spec):
    """把 selector / 文本 / 坐标解析成视口内绝对像素坐标（先滚到可见）。"""
    if spec is None:
        return None
    if isinstance(spec, (list, tuple)):
        return [float(spec[0]), float(spec[1])]
    try:
        return pg.evaluate(
            """(spec) => {
                const find = (s) => {
                    if (s.indexOf('text=') === 0){
                        const want = s.slice(5);
                        const all = document.querySelectorAll('a,button,div,span,li,td,th,h1,h2,h3,p,label,input');
                        for (const e of all){
                            if (e.children.length > 3) continue;
                            const t = (e.innerText || e.value || '').trim();
                            if (t && t.length < 40 && t.indexOf(want) >= 0){
                                const r = e.getBoundingClientRect();
                                if (r.width > 6 && r.height > 6) return e;
                            }
                        }
                        return null;
                    }
                    try { return document.querySelector(s); } catch(e){ return null; }
                };
                const e = find(spec);
                if (!e) return null;
                e.scrollIntoView({block:'center', behavior:'instant'});
                const r = e.getBoundingClientRect();
                return [r.left + r.width/2, r.top + r.height/2];
            }""", spec)
    except Exception:
        return None


def compile_plan(pg, steps):
    """steps → 时间轴（全部绝对时间，单位秒）"""
    plan = {"cursor0": [VW // 2, VH // 2], "moves": [], "scrolls": [],
            "clicks": [], "marks": [], "types": [], "events": [],
            "scroll0": 0.0, "total": 0.0}
    plan["scroll0"] = pg.evaluate("window.scrollY || document.documentElement.scrollTop || 0")

    t = 0.0
    pos = [VW / 2.0, VH / 2.0]
    missed = []

    # 预处理：先把所有带 to 的元素滚到可见并取坐标
    for s in steps:
        spec = s.get("to")
        s["_px"] = px_of(pg, spec) if spec is not None else None
        if spec is not None and s["_px"] is None:
            missed.append(spec if isinstance(spec, str) else "坐标")

    # 取完坐标复位滚动
    pg.evaluate("window.scrollTo(0, %d)" % int(plan["scroll0"]))
    plan["scroll0"] = float(pg.evaluate("window.scrollY || 0"))

    for s in steps:
        op = s.get("op", "move")
        dur = float(s.get("dur", 700)) / 1000.0
        px = s.get("_px")

        if op in ("move", "click", "dblclick") and px:
            plan["moves"].append([t, pos[:], t + dur, px[0], px[1]])
            t += dur
            pos = [px[0], px[1]]
            if op in ("click", "dblclick"):
                hold = float(s.get("hold", 0)) / 1000.0
                plan["clicks"].append([t, px[0], px[1]])
                plan["events"].append([t, "click", None, s.get("to"), None, False,
                                       px[0], px[1]])
                t += max(0.12, hold)
                if op == "dblclick":
                    t += 0.09
                    plan["clicks"].append([t, px[0], px[1]])
                    plan["events"].append([t, "click", None, s.get("to"), None, False,
                                           px[0], px[1]])
                    t += 0.18
        elif op == "type":
            dur = max(0.4, len(s.get("text", "")) / float(s.get("cps", 9)))
            plan["types"].append([t, t + dur, s.get("to"), s.get("text", ""), ""])
            t += dur + 0.12
        elif op == "scroll":
            dy = float(s.get("dy", 600))
            sdur = float(s.get("dur", 1000)) / 1000.0
            plan["scrolls"].append([t, dy, t + sdur])
            t += sdur
        elif op == "mark":
            mdur = float(s.get("dur", 1600)) / 1000.0
            plan["marks"].append([t, t + mdur, s.get("to"), s.get("label", "")])
            t += mdur
        elif op == "key":
            plan["events"].append([t, "key", None, s.get("to"), s.get("key", "Enter"),
                                   False, 0, 0])
            t += float(s.get("ms", 600)) / 1000.0
        elif op == "wait":
            t += float(s.get("ms", 600)) / 1000.0
        elif op == "shot":
            t += float(s.get("ms", 200)) / 1000.0

    plan["total"] = t
    return plan, missed


def launch(p, headless):
    if USE_PROFILE:
        kw = dict(user_data_dir=profile_dir(),
                  viewport={"width": VW, "height": VH},
                  device_scale_factor=DPR,
                  args=["--hide-scrollbars", "--force-device-scale-factor=%d" % DPR])
        for ch in ("chrome", "msedge", None):
            try:
                c = dict(kw)
                if ch:
                    c["channel"] = ch
                return p.chromium.launch_persistent_context(headless=headless, **c), True
            except Exception:
                continue
        raise SystemExit("持久化上下文启动失败")

    args = ["--force-device-scale-factor=%d" % DPR, "--hide-scrollbars"]
    for ch in ("chrome", "msedge", None):
        try:
            b = p.chromium.launch(headless=headless, args=args,
                                  **(dict(channel=ch) if ch else {}))
            return b, False
        except Exception:
            continue
    raise SystemExit("浏览器启动失败（Chrome / Edge / 内置内核都试过了）")


def assemble(frames, out_name):
    if len(frames) < 2:
        return None
    listing = os.path.join(TMP, "_concat.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for i, (path, dt) in enumerate(frames):
            dur = max(0.033, min(0.4, dt if i else frames[1][1]))
            fh.write("file '%s'\nduration %.3f\n" % (path.replace("'", "'\\''"), dur))
        fh.write("file '%s'\n" % frames[-1][0].replace("'", "'\\''"))
    out = os.path.join(CLIPS, out_name + ".mp4")
    vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
          "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=0xF6F4F1,format=yuv420p"
          % (VW * DPR, VH * DPR, VW * DPR, VH * DPR))
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "concat", "-safe", "0", "-i", listing,
           "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-700:])
        return None
    total = sum(max(0.033, min(0.4, dt)) for _, dt in frames)
    return {"file": "clips/%s.mp4" % out_name, "duration": round(total, 2),
            "frames": len(frames)}


def main():
    frames = []
    with sync_playwright() as p:
        ctx_or_b, persistent = launch(p, HEADLESS)
        if persistent:
            pg = ctx_or_b.pages[0] if ctx_or_b.pages else ctx_or_b.new_page()
        else:
            pg = ctx_or_b.new_page(viewport={"width": VW, "height": VH},
                                   device_scale_factor=DPR)
        closer = ctx_or_b.close

        if URL:
            print("▶ 打开 %s" % URL[:90])
            pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
            pg.wait_for_timeout(SETTLE)
        else:
            pg.wait_for_timeout(600)

        # 注入光标层
        pg.add_style_tag(content=INJECT_CSS)
        pg.evaluate(
            """() => {
                if (document.getElementById('__tvcursor')) return;
                const c = document.createElement('div');
                c.id = '__tvcursor'; c.innerHTML = __SVG__;
                document.documentElement.appendChild(c);
                for (const id of ['__tvring','__tvmark','__tvlabel']){
                    const d = document.createElement('div'); d.id = id;
                    document.documentElement.appendChild(d);
                }
            }""".replace("__SVG__", json.dumps(CURSOR_SVG)))

        if "--login" in ARGS:
            print("🔑 浏览器已打开，profile：%s" % profile_dir())
            print("   在那个窗口里登录好，回终端按 Enter 开始录…")
            sys.stdout.flush()
            try:
                input()
            except EOFError:
                pg.wait_for_timeout(120000)
            print("   ✓ 登录态已存。以后加 --profile 就直接带登录态录")
            if not STEPS:
                closer()
                print("   （这次没配 steps，只保存了登录态）")
                return

        if not STEPS:
            closer()
            print("（没配 steps）")
            return

        plan, missed = compile_plan(pg, STEPS)
        if missed:
            print("⚠ %d 个目标没找到：%s" % (len(missed), ", ".join(map(str, missed))[:180]))
            print("  稍后这些动作会被跳过（画面里不会出现光标移动）")

        pg.evaluate(SEEK_JS.replace("__TV_PLAN__", json.dumps(plan, ensure_ascii=False)))
        print("▶ 录制 %.1fs 的操作…" % plan["total"])

        t0 = time.time()
        n = 0
        while True:
            elapsed = time.time() - t0
            pg.evaluate("window.__tvSeek(%f)" % elapsed)
            path = os.path.join(TMP, "f%05d.jpg" % n)
            try:
                pg.screenshot(path=path, type="jpeg", quality=QUALITY)
            except Exception as e:
                print("  ⚠ 截图中断：%s" % str(e).splitlines()[0][:80])
                break
            frames.append((path, 0))
            n += 1
            if elapsed >= plan["total"]:
                break
            if elapsed > plan["total"] + 60:
                break

        pg.evaluate("window.__tvSeek(%f)" % plan["total"])
        if frames:
            shutil.copyfile(frames[-1][0], os.path.join(SHOTS, NAME + ".png"))
        closer()

    # 用真实时间戳重算每帧停留时长
    stats = os.stat(frames[0][0]) if frames else None
    total_wall = plan["total"]
    real = []
    prev = os.stat(frames[0][0]).st_mtime if frames else time.time()
    for path, _ in frames:
        m = os.stat(path).st_mtime
        real.append((path, max(0.03, m - prev)))
        prev = m
    frames = real
    fps = round(len(frames) / max(0.1, sum(d for _, d in frames)), 1)

    info = assemble(frames, NAME)

    man_path = os.path.join(PROJECT, "capture.json")
    man = {"shots": [], "clips": []}
    if os.path.exists(man_path):
        try:
            man = json.load(open(man_path, encoding="utf-8"))
            man.setdefault("shots", []); man.setdefault("clips", [])
        except Exception:
            pass
    man["shots"].append({"name": NAME, "file": "assets/captured/%s.png" % NAME,
                         "width": VW * DPR, "height": VH * DPR,
                         "source": URL or "", "note": "ops 末帧"})
    if info:
        man["clips"].append(dict(info, name=NAME, source=URL or "", action="ops"))
    json.dump(man, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n✅ %d 帧（%.1ffps）→ %s" % (len(frames), fps,
                                       info["file"] if info else "合成失败"))
    print("   静态图 assets/captured/%s.png" % NAME)
    if fps < 8:
        print("   ⚠ 帧率偏低：把 viewport 调小（如 [1000,562]）或降 quality（默认 85）")
    print('   用：scene 加 "clip": {"file": "clips/%s.mp4"}，跑 --from frames' % NAME)


if __name__ == "__main__":
    main()
