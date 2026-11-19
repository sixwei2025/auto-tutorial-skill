# 水彩手绘毛笔大字报封面规范（AI 直出 + 双画幅封装）

> **铁律**：水彩手绘插画风（`watercolor-ai`）**严禁**用 HTML/CSS 模糊圆圈 + 贴生硬抠像凑数！必须通过 **AI 生图（风格参考图 + 真人参考照 + 选题场景隐喻）直出完整水彩插画封面**，再调用 `render_cover_suite.py --package-cover` 无损封装 `3:4` 竖版封面与 `16:9` 首帧。

## 一、两步标准流水线

### 第 1 步：AI 生成 `3:4` 完整水彩手绘封面

调用 `image-generator`（或 Gemini 图像生成模型），**同时传入两张参考图**：
1. **风格参考图（Style Reference）**：
   - 口播视频：`~/.agents/skills/huixin-video-cover/assets/style_refs/watercolor_sample_koubo.jpg`
   - 教程视频：`~/.agents/skills/huixin-video-cover/assets/style_refs/watercolor_sample_tutorial.jpg`
2. **人物参考照（Person Reference）**：
   - 本地自用版：`~/.agents/skills/huixin-video-cover/assets/owner_cutout_hd.png`（保留袁六伟真实五官与发型，以暖色水彩手绘人物画风自然融入场景，绝不生硬贴图）
   - 对外客户版：替换为客户本人照片（若客户不露脸则只画手绘隐喻场景）

#### 标准 Prompt 模板（按当期选题替换 `{...}`）

```text
Generate a vertical 3:4 editorial watercolor & ink-wash video cover illustration matching the exact style of the Style Reference Image: heavy cold-press warm cream watercolor paper texture (#F6F0E4), rich granulated burnt-orange (#E55A17) and Prussian/cobalt-blue (#1E436E) watercolor washes, dry-brush ink splatters around all margins, semi-realistic warm watercolor/gouache portrait seamlessly painted into a rich metaphorical illustration scene, and bold expressive hand-painted Chinese brush calligraphy typography filling the top 38% with zero awkward empty gap.

Person Reference: Preserve the exact facial features, hair, and likeness of the Chinese man in the Person Reference image, painted naturally in the same editorial watercolor & ink-wash style (NOT a pasted photo cutout).

Top 38% Title (centered, bold hand-painted Chinese brush calligraphy, small orange/blue doodle sparks around text):
- Line 1 (deep Prussian navy ink brush calligraphy; any numbers or key emphasis in burnt orange; English letters bold and crisp): {LINE_1_TITLE}
- Line 2 (crisp white brush calligraphy painted over a vivid rough-edged burnt-orange watercolor brush stroke): {LINE_2_ACCENT}

Bottom 62% Visual Metaphor Scene:
{SCENE_METAPHOR_DESCRIPTION}

Hard constraints: Pure illustration cover only. Zero UI icons, zero likes/comment counters, zero watermarks, zero typos in Chinese characters.
```

#### 选题场景隐喻速查库（`{SCENE_METAPHOR_DESCRIPTION}`）

| 赛道 | 常见选题 | 推荐水彩场景隐喻 |
| :--- | :--- | :--- |
| **口播 · 商业变现** | 钱从哪里来 / 赚钱方式 / 商单 | 穿卡其/藏蓝休闲衬衫，手持放大镜俯身看蓝图清单，脚下延伸出橙蓝分叉箭头通向手绘工厂与写字楼群 |
| **口播 · 避坑/困境** | 3个核心困境 / 为啥效果差 | 双手托起两块无法严丝合缝的巨型藏蓝与橙红拼图块，背景是断掉的传送带或迷宫齿轮 |
| **口播 · 获客/自媒体** | AI+自媒体 10倍获客 | 坐在木桌前面对支架手机与笔记本电脑，身旁飘出橙蓝水彩对话气泡与上升增长曲线 |
| **口播 · 认知/战略** | 老板修行 / 破局 / 无法垄断 | 掌舵木船穿梭橙蓝海浪夕阳，或围坐在一张被切分成多个工厂板块的圆形沙盘旁 |
| **教程 · 实操/自动化** | 3步学会 / 全自动工作流 | 坐在木桌前指向打开的笔记本电脑（屏幕显示操作界面/时间轴），周围环绕手绘胶片、齿轮、流程图与橙色引导箭头 |

### 第 2 步：一键封装双画幅（`3:4` 独立封面 + `16:9` 暖色柔边首帧）

AI 生成出图并人工/视觉核验「文字零错字 + 人像自然」后，执行：

```bash
/opt/homebrew/bin/python3.11 ~/.agents/skills/huixin-video-cover/scripts/render_cover_suite.py \
  --package-cover "/path/to/ai_watercolor_3x4.jpg" \
  --out "./cover"
```

输出产物：
- `cover/watercolor-ai_3x4.jpg`（`1080×1440`，推送汇芯爆款/视频号封面）
- `cover/watercolor-ai_3x4.png`（`1080×1440` 无损源图）
- `cover/watercolor-ai_16x9_opening.png`（`1920×1080`，中央 `810×1080` 为 `3:4` 安全区，左右两侧自动采用原图水彩纸暖色模糊延展，告别生硬纯黑边）
