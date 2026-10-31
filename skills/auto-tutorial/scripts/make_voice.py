#!/usr/bin/env python3
"""Step｜按 project.json 的旁白文本，用本机 VoiceBox 批量配音（跨平台）

用法：TV_PROJECT=/path/to/project python3 make_voice.py [--force]
前置：VoiceBox 已启动（默认 127.0.0.1:17493）

跨平台说明：
- 音频落盘目录自动探测（macOS / Windows / Linux），也可在 project.json 指定 voice.data_dir
- engine 自动取音色的 default_engine；报 400 时自动换引擎重试
- 倍速用 ffmpeg atempo，音调不变
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (PROJECT, cfg, ffmpeg, media_duration, vb_alive, vb_api,
                    vb_audio, vb_data_dir, vb_get, vb_profile)

V = cfg().get("voice", {})
OUT = os.path.join(PROJECT, "voice", "audio")
RAW = os.path.join(PROJECT, "voice", "raw")     # 未变速的原始音频，改语速时不必重新合成
os.makedirs(OUT, exist_ok=True)
os.makedirs(RAW, exist_ok=True)
FORCE = "--force" in sys.argv
RESYNTH = "--resynth" in sys.argv               # 连原始音都重生成（换了音色/模型才需要）

RAW_IDX = os.path.join(RAW, "index.json")


def raw_index():
    try:
        return json.load(open(RAW_IDX, encoding="utf-8"))
    except Exception:
        return {}


def text_key(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:12]

SPEED_RAW = float(V.get("speed", 1.5))
# 教程语速硬标准：1.5x 是唯一值（袁总 2026-10-30 拍板，短视频时代慢就掉完播）。
# 防止 project.json 里残留旧的 1.35 或手改降速 —— 低于 1.5 一律强制拉回。
SPEED = SPEED_RAW
if SPEED_RAW < 1.5:
    SPEED = 1.5
    print("⚠️  voice.speed=%.2fx 低于教程标准 1.5x，已强制拉回 1.5x（如确需降速请改本脚本，勿改 project.json）" % SPEED_RAW)
elif SPEED_RAW > 1.5:
    print("⚠️  voice.speed=%.2fx 高于教程标准 1.5x，克隆音会发紧、有机械感，建议回到 1.5x" % SPEED_RAW)
MODEL = V.get("model_size", "1.7B")
ENGINES = [V["engine"]] if V.get("engine") else ["qwen", "qwen_custom_voice", "qwen_voice_clone"]


def post(path, payload):
    req = urllib.request.Request(vb_api() + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def gen_one(profile, text):
    """生成一段配音，返回 (音频路径, 实际引擎)。引擎不对会报 400，自动换引擎重试。"""
    pid = profile["id"]
    engines = []
    if profile.get("default_engine"):
        engines.append(profile["default_engine"])
    engines += [e for e in ENGINES if e not in engines]

    last = None
    for eng in engines:
        body = {"profile_id": pid, "text": text, "language": cfg().get("language", "zh"),
                "model_size": MODEL}
        if eng:
            body["engine"] = eng
        try:
            job = post("/generate", body)
        except urllib.error.HTTPError as e:
            last = "%s → HTTP %s %s" % (eng, e.code, e.read()[:120])
            continue
        gid = job["id"]
        status = "generating"
        for _ in range(int(V.get("timeout_s", 900)) // 3):
            time.sleep(3)
            st = vb_get("/generate/%s/status" % gid)
            status = st.get("status")
            if status in ("completed", "failed", "cancelled"):
                break
        if status != "completed":
            last = "%s → status=%s" % (eng, status)
            continue
        src = vb_audio(gid)
        if not src:
            last = "%s → 音频未落盘（%s）" % (eng, vb_data_dir())
            continue
        return src, eng
    raise SystemExit("配音失败：" + str(last))


def main():
    if not vb_alive():
        raise SystemExit("VoiceBox 未响应。请先启动 VoiceBox（默认端口 17493），"
                         "或设置环境变量 VOICEBOX_API。")

    profile = vb_profile(V.get("profile_name", "袁六伟"), V.get("profile_id"))
    if not profile:
        raise SystemExit("指定VoiceBox档案不存在；停止生成，请用户确认，禁止替换声音。")
    print("音色 %s  id=%s  默认引擎=%s  语速=%sx"
          % (profile.get("name"), profile["id"], profile.get("default_engine"), SPEED))

    result = []
    for sc in cfg()["scenes"]:
        sid, text = sc["id"], (sc.get("voice") or "").strip()
        if not text:
            raise SystemExit("场景 %s 缺少 voice 旁白文本" % sid)
        dst = os.path.join(OUT, sid + ".wav")

        # 只有在「文本没变 + 成品还在」时才跳过。以前只看文件在不在，
        # 结果改了旁白也照旧复用旧音频，时间轴和字幕全对不上——这个坑踩过。
        key = text_key(text + "|" + profile["id"] + "|" + str(MODEL))
        output_key = text_key(key + "|" + str(SPEED))
        idx = raw_index()
        if os.path.exists(dst) and idx.get(sid + ":output") == output_key and not FORCE:
            d = media_duration(dst)
            print("[skip] %-14s %.2fs（文本未变）" % (sid, d))
            result.append({"id": sid, "file": "voice/audio/%s.wav" % sid,
                           "duration": round(d, 3), "text": text})
            continue

        changed = os.path.exists(dst) and idx.get(sid) != key
        print("[gen ] %-14s (%d字)%s" % (sid, len(text), "  文本改了，重新配音" if changed else ""), flush=True)
        raw = os.path.join(RAW, sid + ".wav")
        # 原始音还在、文本没改、也不是强制重合成 → 跳过 TTS，只重跑倍速
        reused = (os.path.exists(raw) and idx.get(sid) == key and not RESYNTH)
        if reused:
            src, used = raw, "cached"
            print("       ├ 复用原始音，只重跑 %.2fx" % SPEED, flush=True)
        else:
            src, used = gen_one(profile, text)
            shutil.copy2(src, raw)
            idx[sid] = key
            json.dump(idx, open(RAW_IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        if abs(SPEED - 1.0) > 0.01:
            tmp = dst + ".tmp.wav"
            r = subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                                "-i", src, "-filter:a", "atempo=%s" % SPEED,
                                "-ar", "48000", tmp], capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit("变速失败：" + r.stderr[-400:])
            os.replace(tmp, dst)
        else:
            shutil.copy2(src, dst)

        d = media_duration(dst)
        print("[ ok ] %-14s %.2fs  engine=%s" % (sid, d, used), flush=True)
        idx = raw_index()
        idx[sid + ":output"] = output_key
        json.dump(idx, open(RAW_IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        result.append({"id": sid, "file": "voice/audio/%s.wav" % sid,
                       "duration": round(d, 3), "text": text})

    json.dump(result, open(os.path.join(PROJECT, "voice", "audio-meta.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(r["duration"] for r in result)
    print("\n✅ %d 段，纯旁白 %.1fs" % (len(result), total))


if __name__ == "__main__":
    main()
