# v3全屏工程格式

新工程先维护 ROOT 下 `steps.json`（或 `guide-steps.json`），字段与到本文件 `camera.json` 的映射见[steps-schema](steps-schema.md)；齐图后再写镜头时间。

所有文件放在同一个绝对ROOT内，脚本接受ROOT与可选`--plan camera.json`。不再使用旧版1080×1350正文及大标题栏。字幕、镜头时间以旁白起点为0，不含封面；渲染器只添加一次0.2秒封面和声音延迟。渲染器导出`字幕.srt`时统一加0.2秒，不要再次手动偏移。

`camera.json`示例（具体时间必须来自实际声音）：

```json
{
  "series": "WorkBuddy实操",
  "duration": 12,
  "cover": "cover.png",
  "audio": "voice/narration.wav",
  "captions": "captions.json",
  "output": "final.mp4",
  "scenes": [
    {"type":"video", "start":0, "end":4,
     "file":"edit/result-preview.mp4", "source":"raw/actual-result.mp4",
     "title":"真实成品效果", "preview_label":"3倍速预览",
     "evidence":"本次任务实际输出；原视频12秒，压缩为4秒；已检查隐私"},
    {"type":"image", "start":4, "end":12,
     "file":"raw/step.png", "title":"输入关键要求",
     "evidence":"实际操作时间、操作内容、可见结果及来源记录位置",
     "masks":[[0,0,240,1000]],
     "camera":[[0,900,900,1000],[1,900,900,1000],[2.2,960,840,620],[5.5,960,840,620],[7,900,900,1000],[8,900,900,1000]]}
  ]
}
```

镜头须连续覆盖配音全长。`camera`每项是`[镜头内秒数, 原图中心x, 原图中心y, 可见原图宽度]`，高度由9:16推算。浮点坐标与五次缓动避免整数裁切抖动，相同取景的连续关键帧形成稳定停留。远中近相对素材而定，不机械套固定缩放比例。全屏指完整画布服务讲解，不强制横向截图裁满竖屏；优先保证关键文字、输入和结果完整可读，不用旧版大标题栏占据内容空间。稳定取景期间持续讲解，不插入读屏等待。预览检查镜头起、中、末及必要过渡帧。

`masks`是原图实色遮挡矩形`[x,y,w,h]`，先遮挡后取景；默认高亮为空。确需黄色细框定位密集文字时，从遮挡后的安全图生成对应讲解段落专用图，保留处理记录并拆分镜头；不修改原图，不跨整片常驻框。

视频镜头只允许本题真实作品视频或直接渲染的讲解动画；软件操作录像、花录工程导出和误录视频不属于允许来源，也不能抽帧转为image镜头绕过。每段evidence注明类别、生成来源与用途；source指向保留的真实文件。当前脚本的尺寸/哈希检查不能自动识别录像来源，制作者须核对来源，不能宣称已有自动拦截。

视频镜头的`file`须预先处理成1080×1920、30fps、无字幕且时长匹配的安全预览，`source`保留真实输出。按实际速度设置`preview_label`，不把预览倍速当成制作耗时。横屏结果完整展示，留白可用同源柔化背景填充，但只保留一个清晰结果画面。隐私必须先裁掉或实色遮挡，柔化背景不属于隐私遮挡。记录预览转换命令和原始文件哈希；不生成假操作。

`captions.json`为`[{"start":0,"end":1.8,"text":"剪视频，还在一段段拖时间线？"}, ...]`，按真实说话对齐，每条不超过两行。旁白在合成前已经统一1.35倍速，渲染器不再整体加速；旧工程修订先查各段实际倍率，再同步调整声音、字幕与镜头，禁止重复乘速。

执行：`fullscreen.py ROOT --validate-only`生成`qa/camera-preview/sheet.jpg`，人工查看；`fullscreen.py ROOT`生成视频与`qa/fullscreen-render.json`；`check_fullscreen.py ROOT`生成供`project.py deliver`读取的`qa/technical.json`。技术通过后仍需真实完成全部人工审阅。旧脚本保留作历史兼容，不应用于新工程。

动态图解接入同样使用type: video，preview_label写“讲解示意”，evidence注明解释用途，source保留图解原视频，不宣称是软件实际输出。设计规范与复用边界见[动态PPT](dynamic-ppt.md)。
