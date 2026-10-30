# 本机制作与复用 · v3.5.0

单一绝对项目 ROOT。先写 `steps.json`（goal/do/see），再按 `script-plan.md` 选轨：`screenshot-dynamic`（种草）或 `teach-demo`（跟着做）。

## 截图动态轨（种草；禁录屏）

严格使用真实操作截图与直接渲染的动画。不打开花录，不录屏，不先录再抽帧。缺图只补对应操作截图。

`project.py start/preflight` 验证 VoiceBox；本轨语速默认 **1.35x**。档案用环境变量 `AUTO_TUTORIAL_VOICEBOX_PROFILE` 配置（请换成你自己的声音档案 ID）。

默认管线：`steps.json →（可选 guide.html）→ camera.json → fullscreen.py → check_fullscreen.py`。缺关键 before/after 不得正式渲染。镜头格式见[工程格式](formats.md)；steps 字段见[steps-schema](steps-schema.md)。

`screenshots.py/render.py/check.py` 仅兼容旧工程。

## 教学演示轨（真机录屏带做）

细则见[teach-demo](teach-demo.md)。摘要管线：

1. `steps.json`（`mode=teach-demo`）+ 老师口吻 `narration.txt`  
2. 真机预演 → `raw/screencast/*.mp4`（ffmpeg avfoundation / 系统录屏；守隐私与动作分级）  
3. VoiceBox：持有可配置锁（示例 `AUTO_TUTORIAL_VOICEBOX_LOCK`，默认 `~/voicebox.lock`）→ 档案 ID（`AUTO_TUTORIAL_VOICEBOX_PROFILE`）→ 语速约 **1.2–1.3x**  
4. 对齐字幕 → 以录屏为主时间线剪辑 → `final.mp4`（默认 **1920×1080**）  
5. 福利结尾禁止硬切大红底；检查跟做节奏后 `project.py deliver`

GUI 一次一个操作者。依赖缺失时明确说明。历史实测边界见[验证记录](validation.md)。
