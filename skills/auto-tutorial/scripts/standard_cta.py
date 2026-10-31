#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一结尾：所有 WorkBuddy 教程视频的最后一句旁白固定为
「评论区回复 666，送你 2693 元的一人公司福利包。」
并把最后一镜换成 assets/cta-666.png。

用法：
  TV_PROJECT=/path/to/project python3 standard_cta.py
  TV_PROJECT=/path python3 standard_cta.py --dry    # 只看会改成什么

说明：
- 只改 scenes 里的**最后一个场景**，前面内容一字不动。
- 会先删掉旧的「评论区打「XX」，……我发你。」这类分支口令，避免一句里两个口令。
- 如果项目里没有 cta-666.png，会从技能 assets 复制一份。
"""
import json, os, re, shutil, sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.abspath(os.environ.get("TV_PROJECT", "."))
CFG = os.path.join(PROJECT, "project.json")
CARD_SRC = os.path.join(SKILL, "assets", "cta-666.png")
CARD_REL = "assets/screenshots/cta-666.png"
STANDARD = "评论区回复 666，送你 2693 元的一人公司福利包。"

DRY = "--dry" in sys.argv

cfg = json.load(open(CFG, encoding="utf-8"))
scenes = cfg.get("scenes") or []
if not scenes:
    raise SystemExit("project.json 里没有 scenes")

last = scenes[-1]
v = str(last.get("voice", ""))

# 去掉旧的职业口令与旧的 666 句，避免重复
v = re.sub(r"评论区打「[^」]*」[^。]*。?", "", v)
v = re.sub(r"评论区回复\s*666[^。]*。?", "", v)
v = re.sub(r"点个关注[，,。！!、]?", "", v)   # 袁总：不要点关注，只要评论互动
v = v.strip()
v = re.sub(r"[，,、；;：:。\s]+$", "", v)   # 收掉残留的尾巴标点
if v:
    v += "。"
v = v + STANDARD

last["voice"] = v
last["shot"] = CARD_REL
last["title"] = "怎么领福利包"
last["instruction"] = "评论区回复 666"
last["aside"] = "最后"
last["tip"] = "回复 666，福利包统一发你"
last["checklist"] = [["回复 666", "current"],
                     ["2693 元福利包", "done"],
                     ["24 小时内统一发", "done"]]
last["zoom"] = 1.02
last["target"] = {"x": 0, "y": 0, "width": 1, "height": 1}
last["halo"] = False

# 证据指向最后一条（若原引用不存在则不动）
if "evidence_ids" in last and not last["evidence_ids"]:
    last["evidence_ids"] = []

# 卡片文件
dst = os.path.join(PROJECT, CARD_REL)
if not os.path.exists(dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(CARD_SRC):
        shutil.copy2(CARD_SRC, dst)

print("最后一镜旁白 →", v)
print("最后一镜画面 →", CARD_REL)
if DRY:
    raise SystemExit("（dry run，未写回）")
json.dump(cfg, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("✅ 已写入", CFG)
