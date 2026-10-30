# steps.json 中间层（v3.5）

统一中间层文件名优先 `steps.json`；历史或对外可读名可用 `guide-steps.json`（字段相同）。放在项目 ROOT 根目录。模板见 [steps.template.json](../assets/steps.template.json)。

本层吸收 interactive-docs 的步骤卡（`do`/`see`/`who`/`evidence`/`note`）、tutorial-generator 的 before+after 成对截图与动作分级、content-to-video 的「研究→分章→用户过稿再渲染」门禁。**不**整包搬三仓；**不**承诺「丢一篇文章全自动成片」。输入改造接图文提纲或实操记录即可。

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `version` | 是 | schema 版本，当前 `"1.0"` |
| `topic` | 是 | 本条教程题目 |
| `audience` | 建议 | 目标观众 |
| `goal` | 是 | 看完能做成什么 |
| `mode` | 建议 | `teach-demo`（教学演示）/ `screenshot-dynamic`（截图动态种草）；缺省时按 script-plan 选轨 |
| `updated_at` | 建议 | ISO 或本地可读时间 |
| `review` | 是 | 过稿状态；旁白定稿与 fullscreen 渲染前须齐图且建议 `ready`/`approved` |
| `steps` | 是 | 有序步骤数组 |

### `review`

| 字段 | 说明 |
|---|---|
| `status` | `draft` / `ready`（制作方自检齐） / `approved`（六伟过稿，可选） |
| `reviewed_by` / `reviewed_at` / `notes` | 过稿记录；未过稿可空 |

## 每步固定字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 稳定短 id，如 `s01`；改顺序不改 id |
| `goal` | 是 | 观众本步目标 |
| `do` | 是 | 操作说明（点哪里、输入什么） |
| `see` | 是 | 应看到的结果（可核验） |
| `shots.before` | 核心步必填 | 动作前真实截图路径（相对 ROOT） |
| `shots.after` | 核心步必填 | 动作后真实截图路径 |
| `shots.extra` | 可选 | 模态/下拉/确认框等附加真实截图 |
| `evidence` | 是 | 来源、时间、可见结果；禁止编界面或 AI 生成 UI 填空 |
| `who` | 可选 | 谁在操作 / 哪位专家交接 |
| `note` / `note_kind` | 可选 | 备注；`note_kind`=`tip`/`warning`/`limit`/`optional` |
| `action_level` | 建议 | 见下方动作分级 |
| `video` | 可选 | 映射到成片镜头的提示 |

### `video`（映射 camera.json）

| 字段 | 说明 |
|---|---|
| `include` | `false` 则本步只进 HTML/指南，不进视频 |
| `push_on` | `before` / `after`（默认）/ `both`：推近对准哪张图 |
| `camera_hint` | 给人看的取景说明，写 camera 时参考 |

## 与 camera.json 的映射

1. 只把 `video.include !== false` 的步骤编入视频镜头；开头成品预览、结尾福利镜头可单独存在于 `camera.json`，不必强行塞进 steps。
2. 默认每个核心步骤至少两个 image 镜头机会：`before`（定位入口）与 `after`（结果/变化）；若旁白只讲结果，可合并为一个镜头但 **文件仍须成对存在**。
3. **推近默认对准 `after`**（变化后的关键输入/结果）；讲「从哪点进去」时对 `before` 取景。`push_on=both` 时拆两个相连镜头。
4. `shots.extra`（模态、下拉）通常短切或中景点名，不强制完整推拉。
5. `camera.json` 每段 `evidence` 应能追溯到对应 step 的 `evidence` 与原图路径；图解 Remotion/红白动画只作概念解释，**不能**替代 `shots.before/after`。
6. 缺关键 before/after：**停止**定稿旁白与 `fullscreen.py` 正式渲染，先补真实截图。禁止用 AI 生成界面、介绍页或「完成」提示填空。

## 动作分级（取证边界）

| `action_level` | 取证范围 |
|---|---|
| `browse` | 可完整展示浏览与结果页 |
| `create` | 可完整展示创建到可见结果 |
| `edit` | 可完整展示编辑到保存/可见变化 |
| `delete_cancel` | **只到确认框，然后取消**；不真正删除 |
| `pay_stop` | **只到收银台/支付页**；不提交支付、不输入完整支付凭证 |

## 过稿门禁

旁白定稿、`camera.json` 定稿与 `fullscreen.py` 正式渲染前：

1. 每个 `video.include` 核心步的 `shots.before` 与 `shots.after` 文件存在且非空；
2. `evidence` 非空且可追溯；
3. 缺图 = **阻塞**；补齐前不生成指定声音、不对齐字幕、不正式渲染（`--validate-only` 预览也不得用假图冒充）。
4. 可选：六伟过 `steps`（`review.status=approved`）后再渲；用户未要求时可在制作方 `ready` 后继续，但不得跳过齐图检查。

## 三成品

同一 `steps.json` 可导出：

- **操作指南 HTML**（`scripts/build_steps_html.py`）：目录 + 上下步 + do/see + 截图；
- **截图动态视频**（fullscreen 管线）：种草短片；仍禁止录屏/花录；
- **教学演示视频**（真机录屏带做）：跟着做选题默认；见[teach-demo](teach-demo.md)。本轨不要求 before/after 齐图才开录，但 steps 的 goal/do/see 必须完整；成片证据为 screencast。

更完整的交互壳后续可接；本技能先保证中间层与轻量导出。

## 最小校验（制作方自检）

```bash
python3 -c "
import json,sys,pathlib
p=pathlib.Path(sys.argv[1])
d=json.loads(p.read_text())
root=p.parent
bad=[]
for s in d.get('steps',[]):
  v=(s.get('video') or {}).get('include', True)
  if not v: continue
  for k in ('before','after'):
    rel=(s.get('shots') or {}).get(k)
    if not rel or not (root/rel).is_file():
      bad.append(f\"{s.get('id')}:{k}->{rel}\")
  if not (s.get('evidence') or '').strip():
    bad.append(f\"{s.get('id')}:evidence\")
print('OK' if not bad else 'BLOCK\\n'+'\\n'.join(bad)); sys.exit(1 if bad else 0)
" /absolute/project/steps.json
```
