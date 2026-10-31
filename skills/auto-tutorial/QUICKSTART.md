# 可视化教程视频 · 快速开始

## 1. 装什么（一次性）

```bash
pip install playwright pillow
python -m playwright install chrome     # 已有 Chrome 可跳过
```

另外需要 **ffmpeg**（必须带 libx264、aac；不需要 libass）：

- macOS：`brew install ffmpeg`
- Windows：`winget install Gyan.FFmpeg`（或 scoop / choco）
- Linux：`sudo apt install ffmpeg`

要用自己声音配音，需要 **VoiceBox** 在 `127.0.0.1:17493` 运行。

## 2. 跑一条试试

```bash
mkdir my-video && cd my-video

# macOS / Linux
TV_PROJECT=$PWD python3 <skill目录>/scripts/build_all.py --url <公众号文章链接>

# Windows PowerShell
$env:TV_PROJECT="$PWD"; python <skill目录>\scripts\build_all.py --url <文章链接>
```

大约 5-8 分钟。`delivery/` 出成片、字幕、章节和 `titles.md`（10 个备选标题），`cover/` 出 3:4 封面。

## 3. 出片后改三处再重跑

打开 `project.json`，只改这三个地方：

1. `cover.title_lines` —— 封面两行大字（第 1 行 `WorkBuddy`，第 2 行钩子 ≤8 字；脚本只能从标题拆词，钩子要人写）
   > 封面只允许两行，第三条线放什么都会被丢掉。嫌不够抓人，改第 2 行那句话，别加行。
2. 每个 `scenes[].instruction` —— 右侧面板文案（≤16 字，超了会溢出面板）
3. 每个 `scenes[].voice` —— 旁白（口语化，一句一个动作）

> **`voice.speed` 别碰，固定 1.5x。** 这是唯一标准（短视频时代慢就掉完播）；写小了 `make_voice.py` 会强制拉回 1.5 并告警。
> 嫌某段拖沓，去缩短文本或调 `lead` / `tail`，不要改语速。

```bash
TV_PROJECT=$PWD python3 scripts/build_all.py --from voice      # 改了旁白
TV_PROJECT=$PWD python3 scripts/build_all.py --from manifest   # 只改画面文案
```

## 4. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 报「VoiceBox 未响应」 | 先启动 VoiceBox；端口不是 17493 就设环境变量 `VOICEBOX_API` |
| 报「找不到 VoiceBox 音频目录」 | 在 `project.json` 的 `voice.data_dir` 填 generations 目录 |
| 报「找不到 ffmpeg」 | 装 ffmpeg，或让它进 PATH |
| 封面文案平淡 | 填 `titles.pain` / `titles.benefit`，或直接手改 `cover.title_lines` 第 2 行 |
| 封面变三四行 / 字被挤小 | `title_lines` 超 2 行会被截成「品牌行 + 结论行」；`kicker`/`sub`/`foot` 等槽位默认不渲染。别加行，改第 2 行 |
| 某段配图不对 | 自动配图按文章顺序走、不懂语义，手改 `scenes[].shot` 指到对的图 |
| 封面截图被裁了一半 | 配 `cover.shot_fit: "contain"`，整页完整显示 |
| 画面大片空白 | 那张原图是纯色占位图（公众号常见），换一张或在 `assets.ops` 里 crop |
| 右侧面板文字溢出 | `instruction` 超过 16 字，压缩 |

字段全表见 `SKILL.md`，踩坑总账见 `references/pitfalls.md`。
