# 踩坑总账（做这条片子真实遇到的全部问题）

## 渲染管线

**HyperFrames 完全不可用**
- `npx hyperframes@0.8.161 render` 在启动 Chrome 阶段卡死：7 分 40 秒只产出一个 `owner.json`，零帧。
- `npx hyperframes check` 直接被 SIGTERM（exit 137）。
- 结论：本机环境用它必死。改用 Playwright 逐帧 + ffmpeg，4884 帧约 5 分钟，稳。

**ffmpeg 没有 libass**
- 本机 ffmpeg 8.1 是精简编译，`ass` / `subtitles` / `drawtext` 一个都没有。
- `-vf "ass=file.ass"` 报 `No option name near ...`；`-vf "subtitles=..."` 同样。
- 结论：字幕只能画进 HTML，随帧输出。反而更清晰（无二次编码）。

**Playwright 浏览器版本不匹配**
- Python 端要 `chromium-1234`，缓存里是 `1248`。
- 解决：`p.chromium.launch(channel="chrome")` 走系统 Chrome，绕开版本检查。

**帧目录残留**
- 上一版 4884 帧，新版 3723 帧，旧的 3724–4883 还在，ffmpeg 按 `%05d` 继续读，成片变长。
- 解决：渲染后按 `总时长×fps` 截断。`os.remove` 循环，不要 `rm -rf`（会被 safe-delete 拦）。

## VoiceBox

- `/api/voices`、`/api/health` 都不存在。正确是 `GET /profiles` 和 `GET /health`。
- `GET /generate/{id}/status` 返回 **SSE 格式** `data: {...}`，必须剥前缀再 `json.loads`。
- preset 音色（Vivian / Serena）`default_engine` 是 `qwen_custom_voice`，传 `engine=qwen` 会 400。
- 克隆音色（如「袁六伟」）用 `engine=qwen`。
- 音频落盘在 `~/Library/Application Support/sh.voicebox.app/generations/{id}.wav`。
- 自带 normalize，各段 mean_volume 一致（实测全是 -20.0dB），不需要二次处理。
- 倍速不在 VoiceBox 做，统一 `ffmpeg -filter:a atempo=1.5`（音调不变）。**固定 1.5x**——实测 1.35x 只有 4.6 汉字/秒，比抖音主流口播慢 15–20%；1.5x 约 5.2–5.4 音节/秒，正好对上。**1.5x 是唯一标准、不许降**（袁总 2026-10-30 拍板）；`make_voice.py` 已加下限保护，project.json 里写 1.35 会被强制拉回 1.5 并告警。
- **改了 speed 别重新合成**：`make_voice.py` 会把未变速的原始音存进 `voice/raw/<id>.wav` 并记 hash，改 speed 只重跑 `atempo`，8 段几秒完成；文本改了自动重合成，换音色/模型才需要 `--resynth`。
- **每段语速会飘**：8 段独立合成，实测最快 5.92 / 最慢 4.14 音节/秒，差 37%。落音后按 `音节块数 / 时长` 量一遍，低于 4.3 的段重合成或砍文本。

## 版式

- **右侧面板 h2 溢出**：instruction 超过 16 字会顶出面板边界。压文案 + CSS `overflow-wrap:anywhere`。
- **高亮框套空白**：target 靠估算一定翻车，多个框框在没内容的地方，比不框更糟。正解：颜色检测（黄色高亮可检测）+ 人眼确认；拿不准就只留整图。
- **图文不对应**：讲 Markdown/HTML 配了 PPT 图、讲 Q&A 配 Excel 图。必须逐段核对「这段话在说什么 → 画面在展示什么」。
- **开场裸讲**：旁白讲「以前要上传文件」，画面只有 logo 卡。观众 get 不到。该做对比卡就做（左「以前」右「现在」）。
- **PIL 多图绘制串层**：一张图用 `d`、下一张忘了换 `ImageDraw` 对象，文字画到上一张去了。每张图单独建。
- **封面字号不统一**：`fit()` 逐行自动缩字号会得到 162/178/200 三档，视觉散。定一行基准，其余按视觉重量配比。

## 时间轴

- 片头 2.8 秒太长，把黄金开场浪费了。改 0.1 秒（0–2 帧），平台照样抓首帧当缩略图。
- 片头淡出必须与正文淡入**重叠**，中间任何一帧纯白都会闪。
- `make_audio.py` 遇到 `voice: null` 的段（片头）会崩，要跳过但继续推进 cursor。
- 封面段不参与正文编号。否则第一段显示 `02 / 13`，观众以为漏了一段。

## 素材

- 公众号配图防盗链：`data-src` 提取 + `Referer: https://mp.weixin.qq.com/` 可全量下载。
- 截图 1080 宽直接进 1200 视口会放大发糊，先 Lanczos 2x 到 2160 再用。
- 手机竖屏图（762×1392）不能直接塞 16:9，要合成「左文右机」卡片。
- 仓库里的 skill 动辄 154M（含示例视频），装的时候 `--exclude=.git` + 删 >15M 的媒体文件。

---

## 跨平台（2026-10-29 加，给 Windows 合伙人用）

原件全按 macOS 写死，搬到 Windows 会依次炸在这五处，现在都收进 `scripts/common.py`：

| 坑 | 现象 | 现在怎么办 |
|---|---|---|
| VoiceBox 音频目录 | macOS `~/Library/Application Support/sh.voicebox.app/generations`，Windows 在 `%APPDATA%\sh.voicebox.app\generations` | 按平台依次探测 → 问 API `/health/filesystem` → 仍找不到就报错并提示填 `voice.data_dir` |
| engine 写死 | 克隆音色用 `qwen`、preset 音色要 `qwen_custom_voice`，配错直接 400 | 读音色自带 `default_engine`，失败自动换引擎重试 |
| ffmpeg 路径 | Windows 装了但不在 PATH | PATH → Homebrew → `C:\ffmpeg\bin` → winget/scoop/choco，找不到给出对应安装命令 |
| 浏览器 | Playwright 报 Executable doesn't exist（内核版本对不上） | Chrome → Edge → 内置内核，逐个试 |
| 合成脚本 | `final_render.sh` 是 bash，Windows 没 bash | 新增 `render_mux.py`（纯 Python 调 ffmpeg），`build_all.py` 默认用它 |
| 中文字体 | 封面/说明卡在 Windows 上变方块 | PingFang → 微软雅黑 → Noto CJK 自动切换；ASS 字幕字体名也按平台给 |
| 控制台编码 | Windows GBK 控制台打印 emoji 直接崩 | `build_all.py` 注入 `PYTHONUTF8=1`；单跑脚本请 `set PYTHONUTF8=1` |

## 自动分镜（make_storyboard）

- **顺序依赖**：分镜要在素材加工之前跑，但那时 `assets/screenshots/` 还是空的。所以 `shot_path()` **不能检查文件是否存在**，只能算目标路径；一加存在性判断，全部场景都会被判成「没图」，直接生成 7 张冗余说明卡。
- **说明卡的生成条件**：只有「这一段压根没图可配」才生成，不是「图还没加工好」。
- **段落过滤**三条必须留：与文章标题重复的首段（正文里常把 h1 又贴一遍）、纯域名/引流段（`www.`、扫码、立即体验）、内嵌视频占位。
- **旁白切句**要把冒号也当分隔符，否则会出现「很多Buddy都遇到过这样的场景：，给电脑里…」这种一半冒号一半逗号的句子。
- **封面写成三四行**（反复犯的错）：3:4 在列表里就一小格，第三行往后根本没人读。已定死**两行**：`WorkBuddy` + 一句钩子。
  `make_cover.py` 会硬截到 2 行、剔除 kicker/sub/foot 这些槽位；`make_storyboard.py` 干脆不再生成它们。
- **每行标题必须 `white-space:nowrap`**：让浏览器自己折，「两行」立刻变三行，改了等于没改。
- **`nowrap` + 自动缩字号要一起调**：行元素一旦变成 `display:block`，块宽撑满父级，
  `scrollWidth` 恒定大于可用宽，autofit 会一路缩到下限（实测 176px 被压成 88px，比三行还难看）。
  正解是行加 `width:fit-content`，autofit 逐行量 `.line` 的 `scrollWidth`。
- **封面拆行**不能纯按字数对半切，会把「远程控制上线」切成「远程控 / 制上线」。先试后缀词（上线/发布/来了/更新/免费/就行），再试标点，最后才均分。
- **封面主图**要按宽高比挑（0.32–1.15，最接近 0.62），否则会选中 2160×515 的细长 banner，封面中间空一大块。
- **标题字数**：英文单词算 1 字，别按字母数算，否则「WorkBuddy」一个词就吃掉 9 字额度。

## 时长与长稿（2026-10-29 加，袁总拍板「不设时长上限」）

- **不要为了卡时长砍内容。** 一条片子可以是 40 秒，也可以是 3 分钟、5 分钟，标准是「有没有讲清楚」，不是「压进一分钟」。
- **段数也不能写死。** 原来 `TARGET = 10` 会把 500 字的稿子硬压成 10 段，每段旁白挤到 50 字，读起来喘不过气。
  现在改按体量算：`TARGET = 正文总字数 / 28`（下限 6、上限 60）。531 字 → 15 段，750 字 → 约 27 段。
  要强制段数才写 `"storyboard": {"target_scenes": N}`。
- **长稿靠换画面撑节奏，不靠加速度。** 语速恒定 1.5x 不动；3 分钟以上的片子每 5–8 秒必须有画面变化，
  每 30–40 秒给一个进度锚点（第几步 / 还剩几步），否则完播率会崩。
- **纯文字稿会崩在配图这一步**：`img_pool` 为空时 `pick_image()` 里 `idx % len(img_pool)` 直接 ZeroDivisionError。
  已修：`img_pool` 为空立刻返回 `None`，所有场景退化成说明卡。**这条坑是造长稿测试时踩出来的**——以前每篇都有图，从没暴露。

## 片尾「重复 + 留白」的根因（2026-10-29，袁总当场发现）

现象：片子最后约 3 秒，画面停在旧内容上重复、声音已经结束（静音）。

**根因**：`render_frames.py` 不清理 `frames/`。上一版 82 秒片子留下 2485 张帧，
这一版只要 1111 张，超出的 1374 张旧帧（编号在尾部）被 mux 当成片子内容继续编码。
音轨只有 37 秒，于是尾部 = **旧画面重复 + 静音**。

**修法（两道，缺一不可）**
1. `render_mux.py`：按 `sop.json` 的时间轴算出总帧数，`-frames:v N` 锁死。**不依赖音轨长度，也不依赖目录里有多少帧。**
2. `render_frames.py`：不自动删旧帧（批量删会被安全钩子拦，还会中断渲染），只提示；
   要清就设 `TV_PRUNE_FRAMES=1`。因为 mux 已锁帧，残留帧不会再进成片。

验收：`ffprobe` 的成片时长必须**等于** sop 各段时长之和（本片 37.05 = 37.05）。

## 改了旁白却复用旧音频（同日踩）

`make_voice.py` 原来先判断「目标 wav 存在就 skip」，再判断文本有没有变。
结果改了旁白重跑，音频还是旧的，时间轴和字幕全对不上（成片 49.7s，应为 93s）。

修法：先算 `text_key = sha1(文本)`，与 `voice/raw/index.json` 里的记录比对，
**文本变了才重配**；文本没变且有成品才 skip。日志里会打「文本改了，重新配音」。

## 封面类（2026-10-30 一天里连改四版，全是我的锅）

**① 截图被裁成半张**
`object-fit: cover` 会按容器比例裁图，3:4 画布里一个 16:10 的截图必然被切掉一截。
→ 封面截图一律 **`contain`**，整张缩进画面。要「满」是让画布底色满，不是让截图满。

**② 标题自以为在自适应，其实从来没缩过**
用 `getBoundingClientRect().width` 判断块级元素溢出 —— 块元素宽度永远等于容器宽，永远判不出溢出，
于是字号一路顶到 200px，第二行直接被挤成第三行或出画。
→ 用 **`scrollWidth > box`** 判断；标题每行 `display:block; white-space:nowrap`，逐行缩。

**③ 截图背后垫浅色块 = 丑**
给截图区加 `background:#FFF6F0` 想在红底上"托"一下，结果就是一块突兀的米白板。
→ **不要垫**。截图直接落红底，只有图片本身。

**④ 日期命名 + 跨天重推 = 同一条片两个版本**
`push_library` 早先按 `-YYYYMMDD` 命名，第二天重推就多出一份。片库计数从 158 涨到 165 才发现。
→ 复制前先删同名旧版（任何日期），已在 `push_library.py` 实现。

**⑤ `rm WorkBuddy*-20261029.mp4` 会误删别的片**
清理旧版时用日期通配，把两条无关成片的 mp4 一起删了（它们正好也是 1029 命名）。
→ **删之前先 `ls` 确认清单**，只删精确文件名；批量删还要过安全钩子（>50 个文件直接掐断）。
