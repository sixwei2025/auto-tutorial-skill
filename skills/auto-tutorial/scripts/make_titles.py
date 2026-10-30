#!/usr/bin/env python3
"""Step｜标题生成：八公式出备选 → 七要素标注 → 四维打分 → 过闸 → Top3

用法：TV_PROJECT=/path python3 make_titles.py
产出：delivery/titles.md（8 备选 + 打分表 + Top3）

配置写在 project.json 的 titles 段（都可省，能自动从封面/文章推）：
{
  "titles": {
    "brand": "WorkBuddy", "feature": "远程控制",
    "pain": "跑回工位", "benefit": "手机直接接管电脑",
    "crowd": "一人公司老板", "scene": "通勤、会议间隙、出差"
  }
}
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECT, cfg

C = cfg()
T = C.get("titles", {})
COVER = C.get("cover", {})
SCENES = C.get("scenes", [])

BRAND = T.get("brand", "WorkBuddy")
FEATURE = T.get("feature") or re.sub(r"^WORKBUDDY\s*·\s*", "", C.get("series", "")) or "新功能"
PAIN = T.get("pain") or "跑一趟"
BENEFIT = T.get("benefit") or COVER.get("benefit") or COVER.get("sub_mark") or "打开就能用"
STEP_LABEL = T.get("steps", "3")
CROWD = T.get("crowd", "一人公司老板")
SCENE = T.get("scene", "通勤、会议、出差")
STEP_N = T.get("steps", "3")

# 标题禁区：夸张 / 绝对化
BANNED = ("震惊", "炸裂", "封神", "天花板", "吊打", "遥遥领先", "最屌", "炸天",
          "最好", "最强", "第一", "唯一", "100%", "绝对", "保证", "包过", "必赚")
# 中庸解释尾：高分冲突后接这种尾，分数直接掉
WEAK_TAIL = ("人还得盯着", "人还在场", "其实还得", "还是得自己", "当然也要", "但也要注意")


def cjk_len(s):
    """按「字数」算：汉字 1 字，英文单词/数字各 1 字。"""
    han = len(re.findall(r"[\u4e00-\u9fff]", s))
    words = len(re.findall(r"[A-Za-z]+", s))
    nums = len(re.findall(r"\d+", s))
    return han + words + nums


def formulas():
    """八公式 + 两个变体 → 候选标题（带七要素标注）。

    模板刻意只用「动词短语」做槽位，避免中文语法错位。
    """
    money = T.get("money", "3000")
    n = STEP_N
    first_scene = SCENE.split("、")[0]
    return [
        ("花钱踩坑式", f"花了{money}块买教训，{BRAND}免费就能干", ["造冲突", "借势"]),
        ("数字对比式", f"{n}个AI做同一件事，{BRAND}直接接管", ["数字", "造冲突"]),
        ("时间压缩式", f"{BRAND}{FEATURE}，{n}分钟就能上手", ["时间", "送好处"]),
        ("人群点名式", f"{CROWD}，{BRAND}{FEATURE}该用了", ["贴标签", "借势"]),
        ("免费入口式", f"{BRAND}{FEATURE}免费了，但有{n}个前提", ["送好处", "做留白"]),
        ("卸载式", f"用了{n}天{BRAND}，{FEATURE}我再没碰过", ["设悬念", "借势"]),
        ("替代式", f"别再{PAIN}了，{BRAND}{BENEFIT}", ["造冲突", "送好处"]),
        ("反转式", f"都说{FEATURE}是噱头，{BRAND}把我工位搬了", ["设悬念", "造冲突"]),
        ("造冲突+送好处", f"别再{PAIN}了，{BRAND}一键就行", ["造冲突", "借势", "送好处"]),
        ("留白式", f"{BRAND}{FEATURE}先别急着开，{first_scene}用得上吗", ["做留白", "借势"]),
    ]


def score(title, tags):
    """四维打分（好奇 30 / 相关 30 / 利益 20 / 可信 20）。"""
    cur = 15
    if re.search(r"(别再|为什么|到底|原来|居然|劝你|先别|忘了|再也|秘密)", title):
        cur += 10
    if re.search(r"(吗|？|\?)", title):
        cur += 6
    if re.search(r"\d", title):
        cur += 4
    if "做留白" in tags or "设悬念" in tags:
        cur += 6
    cur = min(cur, 30)

    rel = 10
    if any(k in title for k in ("老板", "打工人", "职场", "新手", "运营", "公司", "上班")):
        rel += 12
    if any(k in title for k in ("通勤", "会议", "出差", "加班", "工位", "路上")):
        rel += 8
    if BRAND in title:
        rel += 8
    rel = min(rel, 30)

    ben = 9
    if any(k in title for k in ("右键", "一键", "直接", "不用", "省", "搞定", "接管",
                                "就行", "别再", "搞定")):
        ben += 8
    if re.search(r"\d", title):
        ben += 4
    ben = min(ben, 20)

    cre = 10
    if re.search(r"\d", title):
        cre += 5
    if BRAND in title:
        cre += 5
    if any(k in title for k in ("我", "用了", "试了", "测了")):
        cre += 4
    cre = min(cre, 20)

    return {"好奇": cur, "相关": rel, "利益": ben, "可信": cre,
            "total": cur + rel + ben + cre}


def gate(title):
    """过闸：返回问题列表，空列表 = 通过。"""
    problems = []
    if BRAND not in title:
        problems.append("没带 WorkBuddy（流量词不能丢）")
    if cjk_len(title) > 20:
        problems.append("超 20 字（%d）" % cjk_len(title))
    for w in BANNED:
        if w in title:
            problems.append("禁词：%s" % w)
    for w in WEAK_TAIL:
        if title.endswith(w):
            problems.append("中庸解释尾")
    if "！" in title or "？？" in title:
        problems.append("标点堆叠")
    return problems


rows = []
for name, title, tags in formulas():
    title = re.sub(r"\s+", "", title)
    sc = score(title, tags)
    problems = gate(title)
    rows.append({"formula": name, "title": title, "tags": tags, "score": sc,
                 "problems": problems, "pass": not problems,
                 "high": (not problems) and sc["total"] >= 80})

rows.sort(key=lambda r: (r["pass"], r["score"]["total"]), reverse=True)
top3 = [r for r in rows if r["pass"]][:3] or rows[:3]

os.makedirs(os.path.join(PROJECT, "delivery"), exist_ok=True)
md = ["# 标题备选（自动生成，定稿前请人工过一遍）", "",
      "内容：%s" % C.get("title", ""), "",
      "| # | 公式 | 标题 | 七要素 | 好奇 | 相关 | 利益 | 可信 | 总分 | 过闸 |",
      "|---|---|---|---|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    s = r["score"]
    md.append("| %d | %s | %s | %s | %d | %d | %d | %d | **%d** | %s |"
              % (i, r["formula"], r["title"], "+".join(r["tags"]),
                 s["好奇"], s["相关"], s["利益"], s["可信"], s["total"],
                 ("✓" if r["high"] else "✓ 分低，建议再改" if r["pass"]
                  else "；".join(r["problems"]))))
md += ["", "## Top 3", ""]
for i, r in enumerate(top3, 1):
    md.append("%d. **%s** —— %s（%d 分）" % (i, r["title"], r["formula"], r["score"]["total"]))
md += ["", "> 「✓」= 过硬闸；「✓ 分低」= 过硬闸但四维<80，建议再改；「✗」= 被硬闸拦下。",
       "> 打分为规则初筛（好奇/相关/利益/可信），最终以人工判断为准；",
       "> 定稿后标题一字不改，也不要在后面贴「人还得盯着」这类正确废话。"]
open(os.path.join(PROJECT, "delivery", "titles.md"), "w", encoding="utf-8").write("\n".join(md))

TOP_N = int(T.get("top", 3))
top = [r for r in rows if r["pass"]][:TOP_N] or rows[:TOP_N]

print("✅ delivery/titles.md\n")
print("给你挑 %d 个（内部从 %d 个候选里筛，全表在 titles.md）\n" % (len(top), len(rows)))
for i, r in enumerate(top, 1):
    s = r["score"]
    print("  %d. %s" % (i, r["title"]))
    print("     %-12s 七要素 %s ｜ 四维 %d/%d/%d/%d = %d"
          % (r["formula"], "+".join(r["tags"]),
             s["好奇"], s["相关"], s["利益"], s["可信"], s["total"]))

if "--all" in sys.argv:
    print("\n全部候选：")
    print("%-4s %-14s %-24s %s" % ("", "公式", "标题", "分数"))
    for r in rows:
        s = r["score"]
        flag = ("✓" if r["high"] else "✓ 分低" if r["pass"]
                else "✗ " + (r["problems"][0][:14] if r["problems"] else ""))
        print("%-4s %-14s %-24s %3d  %s" % ("→" if r in top else "", r["formula"],
                                            r["title"], s["total"], flag))
else:
    print("\n（其余 %d 个候选已存 titles.md；想看全表加 --all）" % (len(rows) - len(top)))
