#!/usr/bin/env bash
# 最终合成：帧序列 + 音轨 → MP4，再嵌入章节
set -e
cd "${TV_PROJECT:-$PWD}"

# slug：环境变量优先，否则读 project.json
if [ -z "$SLUG" ]; then
  SLUG=$(python3 -c "import json;print(json.load(open('project.json')).get('slug','video'))" 2>/dev/null || echo video)
fi

FPS=30
SRC="frames/%05d.jpg"
AUDIO="voice/full.wav"
CHAPTERS="delivery/chapters.ffmetadata"
OUT="renders/${SLUG}-16x9.mp4"
FINAL="delivery/${SLUG}-16x9.mp4"

mkdir -p renders delivery

echo "▶ 1/2 合成视频 + 音轨"
ffmpeg -y -hide_banner -loglevel warning \
  -framerate $FPS -i "$SRC" -i "$AUDIO" \
  -vf "format=yuv420p" \
  -c:v libx264 -preset medium -crf 18 -profile:v high -level 4.1 \
  -c:a aac -b:a 192k -ar 48000 \
  -shortest -movflags +faststart \
  "$OUT"

if [ -f "$CHAPTERS" ]; then
  echo "▶ 2/2 嵌入章节"
  ffmpeg -y -hide_banner -loglevel warning \
    -i "$OUT" -i "$CHAPTERS" \
    -map 0 -map_metadata 1 -c copy -movflags +faststart \
    "$FINAL"
else
  echo "⚠ 无章节文件，输出未嵌章节版本"
  cp "$OUT" "$FINAL"
fi

echo
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height \
  -of default=noprint_wrappers=1 "$FINAL"
echo "✅ $FINAL"
