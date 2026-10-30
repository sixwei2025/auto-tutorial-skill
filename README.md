# 自动化教程 Skill（auto-tutorial）

> 🔴 **作者：袁六伟 · 台州汇芯**｜一人 AI 公司创业者，6000+ 学员，100+ 客户，得到/华为分享老师
> 📮 更多 AI 视频与自动化实战，关注 **公众号 / 视频号：袁六伟**

## 一句话

**选题进来 → 完全自动出教程。** 用户不填表、不学剪辑；对 agent 说一句「用自动化教程 skill 做一条 WorkBuddy XXX 教程」，即可走完 steps → 真机截图/录屏 → 旁白 → 成片/操作指南。

主战场是 **WorkBuddy**（[open.workbuddy.cn](https://open.workbuddy.cn) / WorkBuddy App）。Skill 结构通用，Claude Code、Codex、Cursor 等也可安装，但实操取证、录屏入口、VoiceBox 等需**自行适配**本机界面与工具链。

*An Agent Skill for fully automated product tutorials: one topic in → steps / screenshots or screencast / narration / three deliverable tracks out. Built for WorkBuddy; adapt UI & tooling yourself on other agent platforms.*

## 三轨成品（同一 `steps.json`）

| 路线 | 产出 | 何时用 |
|---|---|---|
| **操作指南 HTML** | `guide.html` | 图文跟做、可点上下步 |
| **截图动态种草** | 竖屏 `final.mp4` | 利益开场、节奏快的种草短片（禁录屏，真实截图推拉） |
| **教学演示真机带做** | 横屏 `final.mp4` | 「跟着做 / 上架」类默认：真机边操作边讲 |

中间层统一为 `steps.json`（每步 `goal` / `do` / `see`），选轨不混轨，禁止 AI 编造界面补步骤。

## 安装

```bash
npx skills add sixwei2025/auto-tutorial-skill
```

也可以把本仓库里的 `skills/auto-tutorial/` 整个文件夹拷进你的 agent 的 skills 目录。WorkBuddy、Claude Code、Codex、Cursor 等支持 `SKILL.md` 的 agent 都能识别；**配音 / 录屏 / 截图入口请按你本机环境配置**。

## 依赖概要

**必需**
- Python 3.10+
- ffmpeg / ffprobe（成片与响度相关处理）
- 可截图或录屏的桌面环境（WorkBuddy App 或浏览器打开 open.workbuddy.cn）

**可选**
- VoiceBox 或任意能输出 wav 的 TTS（通过环境变量配置档案与服务地址）
- 中文字体（封面与字幕）

VoiceBox 示例配置（请换成你自己的档案与路径）：

```bash
export AUTO_TUTORIAL_VOICEBOX_PROFILE='your-profile-uuid'
export AUTO_TUTORIAL_VOICEBOX_URL='http://127.0.0.1:17493'
export AUTO_TUTORIAL_VOICEBOX_LOCK="$HOME/voicebox.lock"
```

完整流程与分轨规则见 `skills/auto-tutorial/SKILL.md` 与 `skills/auto-tutorial/references/`。

## 快速开始

对 agent 说：

> 用自动化教程 skill 做一条 WorkBuddy XXX 教程

或手动：

```bash
cd skills/auto-tutorial
python3 scripts/project.py start /absolute/project --topic '用WorkBuddy上架付费Skill' --expected-seconds 60
python3 scripts/project.py preflight /absolute/project
python3 scripts/build_steps_html.py /absolute/project
# 截图动态：voice.py → fullscreen.py → check_fullscreen.py
# 教学演示：真机录屏到 raw/screencast/ 后再配音剪辑（见 references/teach-demo.md）
```

## 许可

MIT。代码开源。配音的声音、字体、配乐、平台账号与支付凭证请使用你自己有授权的资源；本仓库不附带任何私有 VoiceBox 档案或账号密钥。

---

## 关于作者

**袁六伟 · 台州汇芯**：一人 AI 公司创业者，6000+ 学员，100+ 客户，得到/华为分享老师。专注 AI 视频与自动化落地。

- 公众号：**袁六伟**
- 视频号：**袁六伟**

这个 Skill 免费开源。觉得有用的话，欢迎点个 ⭐ Star，再关注公众号或视频号「袁六伟」，那里有更多 AI 视频和自动化的实战分享。企业合作也可以通过公众号联系。

更多开源 Skill：[talking-head-video-skill](https://github.com/sixwei2025/talking-head-video-skill)、[3d-map-video-skill](https://github.com/sixwei2025/3d-map-video-skill)、[psych-kepu-video-skill](https://github.com/sixwei2025/psych-kepu-video-skill)、[dark-infographic-video-skill](https://github.com/sixwei2025/dark-infographic-video-skill)
