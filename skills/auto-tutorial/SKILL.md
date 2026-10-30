---
name: auto-tutorial
description: 选题进来 → 完全自动出教程。用户给一个 WorkBuddy 选题，agent 自动完成 steps → 真机截图/录屏 → 旁白 → 三轨成品（操作指南 HTML / 截图动态种草短片 / 教学演示真机带做）。主用 WorkBuddy；其他智能体平台需自行适配界面与工具链。不填表、不学剪辑。
---

# 自动化教程 Skill · v3.5.1

> 袁六伟出品 · 主战场 WorkBuddy（open.workbuddy.cn / WorkBuddy App）
>
> **平台说明**：本 Skill 结构通用（SKILL.md + scripts + references），在 Claude Code、Codex、Cursor 等支持 Agent Skill 的平台也可安装；但实操取证、录屏入口、VoiceBox 配音等需按你本机环境自行适配。开箱最顺的是 WorkBuddy。

用户给选题即可推进：先明确观众要解决的问题与简短实操提纲，按点击顺序写入统一中间层 `steps.json`（每步 `goal`/`do`/`see`），再按选题选成品轨。同一 steps 可导出操作指南 HTML；也可做成截图推拉种草短片；「跟着做」选题走**教学演示轨**——真机打开 WorkBuddy App 或 open.workbuddy.cn，像老师带做地边操作边讲，单步停留够看清，不要 26 秒快切。素材、旁白、工程与检查由 agent 整理，**不让用户填表或学剪辑工具**。按现有授权继续，不重复询问已选定的声音和样式。

## 三轨成品（同一 steps）

| 路线 | 产出 | 何时用 | 画面来源 |
|---|---|---|---|
| **操作指南 HTML** | `guide.html`（`scripts/build_steps_html.py`） | 图文跟做、可点上下步 | 真实截图 before/after |
| **截图动态视频** | `final.mp4`（fullscreen 管线） | **种草短片**、利益开场、节奏快 | 真实截图取景推拉＋可选红白图解；**仍禁止花录/任何录屏/先录后抽帧** |
| **教学演示（真机录屏带做）** | `final.mp4`（screencast 剪辑） | **2026-10-25 起：跟着做 / 上架教程类选题默认** | 真实 App 或 open.workbuddy.cn 连续操作录屏；大纲必须来自 `steps.json` |

输入可以是图文提纲或实操记录改造进 steps；**不承诺**丢一篇长文全自动成片。任一线都不得用编造界面补 steps。

## 选题选轨（2026-10-25）

- **跟着做 / 上架 / 收款 / 认证等需逐步跟点的选题** → 默认 **教学演示轨**。详见 [教学演示](references/teach-demo.md)。
- **种草、利益钩子、短爆点** → 截图动态轨（硬禁花录不变）。
- 上架类不要用 26s 快切推拉冒充带做。
- 授权改 skill ≠ 授权发布或批量；旧片未经明确要求不删、不改、不撤。

## 教学演示硬规则（真机录屏带做）

完整细则见 [teach-demo.md](references/teach-demo.md)。摘要：

1. **大纲 = steps.json**：按点击顺序；每步有 `goal`/`do`/`see`；可拆成「上架篇 / 收款篇」各 45–90s。
2. **画面 = 真实界面**：WorkBuddy.app 或浏览器 `https://open.workbuddy.cn` 真实操作；禁止 AI 造界面、禁止用静态截图推拉冒充本轨成片。
3. **节奏像老师带做**：单步停留 ≥4–6 秒，或旁白说完再切；禁止 26s 整片快切；片长目标 **45–90 秒**（可拆集）。
4. **旁白像老师**：第二人称「你点这里」「你会看到…」；不堆功能清单；福利结尾禁止硬切大红底（可在真实画面上叠字幕口播，或淡出到轻量结束卡）。
5. **声音（可配置）**：用你本机 VoiceBox（或兼容 TTS）的声音档案 ID；生成前建议用互斥锁避免并行双开。**示例**环境变量：`AUTO_TUTORIAL_VOICEBOX_PROFILE`、`AUTO_TUTORIAL_VOICEBOX_URL`、`AUTO_TUTORIAL_VOICEBOX_LOCK`（默认示例路径 `~/voicebox.lock`，请换成你自己的锁路径与档案）。语速约 **1.2–1.3x**（本轨默认，可整片统一微调）。
6. **画幅**：主片默认 **横屏 16:9**（1920×1080）。封面必须单独出 **竖屏 3:4**（1080×1440），遵守下方「封面撑满」硬规则。
7. **取证边界**：`delete_cancel` 只到确认框后取消；`pay_stop` 只到收银台/开通页，不提交支付、不录完整支付凭证。

### 封面撑满（视频号 3:4 · 2026-10-29）

- 封面画布 **1080×1440（3:4）**，画面必须 **整幅撑满** 视频号封面位：上下左右无黑边、无灰边、无 letterbox/pillarbox。
- **禁止**把正文 16:9 成片直接截一帧当封面（会只占中间一条，上下空，或被平台裁成难看留白）。
- **正确做法**：按 3:4 单独设计/合成封面（同风同题、少字利益标题），导出独立 `cover.jpg`/`-封面.jpg`；可与成片第 0.01 秒 **同构图同风**，但必须是 **3:4 满幅构图**，不是 16:9 帧硬裁中条。
- 自检：打开封面图看宽高比是否 3:4、四边是否贴满内容；不合格不算交片。

## 截图动态轨硬约束（种草短片；禁录屏）

仅适用于**截图动态**成品轨。对「花录」的禁令在本轨仍然有效：

- 禁止启动或调用花录/HuaStudio，及 QuickTime/系统录屏/浏览器录屏/FFmpeg 屏幕采集作为本轨素材来源。
- 「动态」= 对真实截图取景、推拉与信息图解，不是连续录像。不为截图取证而先录再抽帧。
- **例外**：教学演示轨按上一节允许真机录屏；不得把录屏素材塞进截图动态轨冒充推拉成片。
- 如上轮意外留下正在录制的任务，只做停止录制所必需的收尾；不自行删除源文件。

截图动态轨其余规格（全屏竖屏 1080×1920、推拉、红白图解、开头利益、结尾 666/2693 等）见下文「截图动态轨规格」与既有 references。

## 两个内容目标：认真教会，吸引对的人

教程要真诚认真，标题和开头要有吸引力，以真实价值争取流量、信任与成交。以下与制作规格同样重要：

- **选题从观众的具体任务出发。** 先想清谁在什么场景遇到什么麻烦、看完能做成什么。优先演示有实际用途且已跑通的任务，不仅介绍按钮或罗列软件功能。
- **标题和开头围绕一个可兑现的收益。** 封面短标题抓核心利益；开头先说痛点与本条能带来的好处，并尽早给出结果画面。教学演示轨可用「列表里已有审核中的 Skill」等真机画面开场，不必压成 3 秒钩子。
- **认真体现在观众能做成。** 讲清必要材料、真实入口、关键要求和结果检查；有关键前置配置或限制就在对应步骤说明。
- **先交付价值，再承接需求。** 本条承诺的知识在视频里讲完；结尾沿用已确认文案，只设一个明确动作。教学演示轨福利结尾禁止硬切大红底。

具体标题、开头、教学与结尾写法见[内容与截图](references/content-script.md)。教学演示轨另见[teach-demo](references/teach-demo.md)。

## 实操硬要求与 Skill 选择顺序

所有教程类内容必须真实实操。涉及 Skill 时，严格按「自研 Skill 优先 → SkillHub 查找 → 两处都没有合适的再开发」的顺序。查找与证据见[Skill查找与实操记录](references/skill-practice.md)。真实结果写入 steps；呈现方式按所选成品轨（截图或录屏），不混轨。

## 截图动态轨规格（种草；竖屏推拉）

- 教程主体采用**真实操作截图＋动态剪辑**；开头可播放本次实际产出的成片片段。
- 截图来自本次真实操控 WorkBuddy，或用户提供且可核验的真实材料。
- 采用 1080×1920 全屏单画面；远中近推拉；浮点取景、缓入缓出。
- 每题讲一件能做成的事。成功数字与最终旁白须等真实结果核验后定稿。
- 正文实操：入口、动作与结果接得上；可用相邻真实截图串起。执行细节见[实操分镜](references/practice-storyboard.md)。
- 封面少字讲利益；全片连续讲完，不说「暂停视频看一下」。
- 非操作讲解可配红白动态 PPT，见[动态PPT](references/dynamic-ppt.md)。
- 只在密集文字里补充黄色细框重点标记。

## 已确认的交付要求（分轨）

### 共用

- 系列标签「WorkBuddy实操」。隐私：侧栏、私聊、证件号等裁掉或实色遮挡。
- 不修改网络、代理、账号授权或模型设置；登录、发布及不可逆操作遵从现有授权。
- **每次视频交付必须同时提供播放预览和独立的下载链接。**
- 默认交付本地审阅版；批量仍暂停。授权改 skill 不等于授权新视频、发布或批量。
- 默认结尾文案见 [closing.txt](assets/closing.txt)：可按账号改写；示例文案用阿拉伯数字 666、2693。

### 截图动态轨

- 声音：VoiceBox（或兼容 TTS）以你本机可用档案为准；通过环境变量配置档案 ID（见上文「声音（可配置）」）；默认全片 **1.35x**。
- 默认 1080×1920、30fps；首 0.2 秒封面。
- 60 秒以内成片端到端仍计 600 秒预算（策划等待不重置）。

### 教学演示轨

- 声音：同上，可配置档案与锁路径；语速约 **1.2–1.3x**。
- 默认 **1920×1080**、30fps；片长 **45–90s**（可拆集）。
- 成片须能跟做：关键点击在画面里看得见，停留够读完旁白。

## 固定制作顺序

### 共用前段

1. **开始计时与简短提纲。** `project.py start ROOT --topic '题目' --expected-seconds 60`（教学演示建议 60–75）。写 `script-plan.md`：观众、麻烦、收获、标题/开头、选轨（`mode=teach-demo` 或 `screenshot-dynamic`）、关键操作。检查应用、隐私、工具和指定声音。
2. **写/补齐 `steps.json`。** 按 [steps.template.json](assets/steps.template.json) 与 [steps-schema.md](references/steps-schema.md)；每步 `goal`/`do`/`see`。可选 `mode` 字段标明轨。可选导出指南：`build_steps_html.py`。
3. **（可选）人工过 steps。**

### 截图动态轨后段

4. 真实做成一次，成对保存 before/after → 齐图门禁 → 定稿旁白与 `camera.json` → `fullscreen.py` → `check_fullscreen.py` → deliver。缺关键图就停。细则同 v3.4。

### 教学演示轨后段

4. **真机预演与录屏条件。** 确认 WorkBuddy.app / 浏览器已登录所需账号；按 steps 点一遍不录或只短测。写/用 `scripts/record_demo.sh`（工程内）输出 `raw/screencast/demo.mp4`。长时间开录须明确授权。
5. **按 steps 顺序真机录屏。** 单步停留够；隐私遮挡；`pay_stop`/`delete_cancel` 边界。可分段录再拼接。
6. **定稿老师口吻旁白** `narration.txt`（45–75s 量级口语）→ TTS（锁→档案→1.2–1.3x）→ 对齐字幕 → 剪辑：录屏为主时间线，叠加字幕；福利结尾不硬切大红底。
7. **检查与交付。** 跟做自检：每步 goal 是否在画面出现；停留是否够；片长是否在 45–90s。deliver 登记。

调用示例与接口见[本机制作](references/production.md)。

## 调用与修订

从本技能实际安装目录使用脚本绝对路径。截图动态轨脚本：`fullscreen.py` / `check_fullscreen.py` 等。教学演示轨以工程内录屏脚本 + ffmpeg 剪辑为主；VoiceBox 经 `voice.py` 或本机 CLI，生成前建议持有配置好的锁文件。

```bash
export AUTO_TUTORIAL_VOICEBOX_PROFILE='your-profile-id'
export AUTO_TUTORIAL_VOICEBOX_URL='http://127.0.0.1:17493'   # 可选
export AUTO_TUTORIAL_VOICEBOX_LOCK="$HOME/voicebox.lock"     # 可选示例

python3 scripts/project.py start /absolute/project --topic '用WorkBuddy上架付费Skill' --expected-seconds 60
python3 scripts/project.py preflight /absolute/project
python3 scripts/build_steps_html.py /absolute/project
# 截图动态：
python3 scripts/voice.py /absolute/project --text narration.txt
python3 scripts/fullscreen.py /absolute/project --validate-only
# 教学演示：先真机录屏到 raw/screencast/，再配音剪辑（见 references/teach-demo.md）
```

本版本在 v3.4.0 截图动态中间层之上，增加教学演示轨与选轨规则；研究来源与验证边界见[验证记录](references/validation.md)。

旧版 `shots.json → screenshots.py → render.py → check.py` 仅历史兼容。新截图动态工程不使用旧 1080×1350 正文。
