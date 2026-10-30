#!/usr/bin/env python3
"""把成片同步进本地「汇芯视频中心」（http://127.0.0.1:8765/#lib）。

做法：按片库命名规范复制成片 + 封面到被扫描的目录，再调 /api/rescan 让它刷新。

用法：
  TV_PROJECT=/path python3 push_library.py                      # 用 project.json 的 title/slug
  TV_PROJECT=/path python3 push_library.py --dir ~/Videos/tutorial-output
  TV_LIBRARY_DIR=~/Videos/tutorial-output TV_PROJECT=/path python3 push_library.py
  TV_PROJECT=/path python3 push_library.py --dry                # 只打印要做什么
"""
import datetime
import json
import os
import re
import shutil
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, cfg


def opt(k, d=None):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d


API = os.environ.get("TV_HUB", "http://127.0.0.1:8765")
TITLE = opt("--title") or cfg().get("title") or cfg().get("slug", "video")
SLUG = cfg().get("slug", "video")
DATE = datetime.date.today().strftime("%Y%m%d")
DRY = "--dry" in sys.argv

VIDEO = os.path.join(PROJECT, "delivery", "%s-16x9.mp4" % SLUG)
COVER = opt("--cover") or next(
    (c for c in (os.path.join(PROJECT, "cover", "cover-3x4.jpg"),
                 os.path.join(PROJECT, "cover", "cover.jpg"),
                 os.path.join(PROJECT, "cover", "cover-3x4.png")) if os.path.exists(c)), None)

if not os.path.exists(VIDEO):
    raise SystemExit("❌ 找不到成片：%s（先跑 --from mux）" % VIDEO)


def pick_dir():
    """优先命令行指定；否则问视频中心自己扫哪些目录，取第一个存在的。"""
    d = opt("--dir")
    if d:
        return os.path.expanduser(d)
    try:
        raw = urllib.request.urlopen(API + "/api/output_dirs", timeout=5).read()
        by_line = json.loads(raw).get("by_line", {})
        for line in ("lab", "koubo", "kepu", "promo"):
            for p in by_line.get(line, []):
                if os.path.isdir(p):
                    return p
    except Exception as e:
        print("   ⚠ 读不到 /api/output_dirs（%s），退回默认目录" % e)
    # 公开包默认：环境变量 TV_LIBRARY_DIR，否则 ~/Videos/tutorial-output
    return os.path.expanduser(os.environ.get("TV_LIBRARY_DIR", "~/Videos/tutorial-output"))


DEST = pick_dir()
os.makedirs(DEST, exist_ok=True)

safe = TITLE.replace("/", "-").replace(" ", "")
out_v = os.path.join(DEST, "%s-%s.mp4" % (safe, DATE))
out_c = os.path.join(DEST, "%s-%s-封面%s" % (safe, DATE, os.path.splitext(COVER)[1] if COVER else ".jpg"))

# 同名旧版本（任何日期）先清掉，避免「同一条片出现两个日期版本」
for _f in os.listdir(DEST):
    _stem, _ext = os.path.splitext(_f)
    if _stem.startswith(safe + "-") and re.match(r"^%s-\d{8}(-封面)?$" % re.escape(safe), _stem) and _stem not in (os.path.splitext(os.path.basename(out_v))[0], os.path.splitext(os.path.basename(out_c))[0]):
        try:
            os.remove(os.path.join(DEST, _f))
            print("   ✕ 删掉同名旧版 %s" % _f)
        except OSError:
            pass

print("▶ %s → %s" % (os.path.basename(VIDEO), DEST))
if DRY:
    print("   would copy: %s\n   would copy: %s" % (out_v, out_c))
    raise SystemExit(0)

shutil.copy2(VIDEO, out_v)
print("   ✓ %s" % os.path.basename(out_v))
if COVER and os.path.exists(COVER):
    shutil.copy2(COVER, out_c)
    print("   ✓ %s" % os.path.basename(out_c))

# 让视频中心重新扫盘
try:
    req = urllib.request.Request(API + "/api/rescan", data=b"{}",
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    r = urllib.request.urlopen(req, timeout=20).read()
    print("   ↻ 已请求重扫：%s" % r[:120].decode("utf-8", "ignore"))
except Exception as e:
    print("   ⚠ 重扫失败（%s）——手动点页面上的「刷新片库」即可" % e)

print("✅ 同步完成：%s/#lib" % API)
