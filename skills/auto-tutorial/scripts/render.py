import argparse
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from common import duration, fail_main, fps, inside, now, probe, read, require_tools, root_path, run, sha, stream, write


LAYOUT = read(Path(__file__).resolve().parent.parent / 'assets/layout.json')


def font(size):
    file = next((x for x in LAYOUT['font_candidates'] if Path(x).exists()), None)
    if file is None:
        raise RuntimeError('缺少可用中文字体，停止渲染')
    return ImageFont.truetype(file, size)


def validate(root, spec):
    if spec['series'] != 'WorkBuddy实操':
        raise ValueError('系列标签必须是WorkBuddy实操')
    body = inside(root, spec['body']); audio = inside(root, spec['audio']); cover = inside(root, spec['cover'])
    vi = probe(body); ai = probe(audio); v = stream(vi, 'video')
    if not v or (v['width'], v['height']) != (1080, 1350) or abs(fps(v) - 30) > .001:
        raise ValueError('截图动态body须为1080×1350/30fps；不在render再次裁切或变焦')
    if not stream(ai, 'audio'):
        raise ValueError('缺少配音音轨')
    seconds = duration(ai, 'audio')
    if abs(duration(vi, 'video') - seconds) > .15:
        raise ValueError('画面与配音时长差超过0.15秒；修剪辑或解说，按实际声音调整截图镜头时长')
    if Image.open(cover).size != (1080, 1920):
        raise ValueError('封面须为1080×1920')
    caps = read(inside(root, spec['captions'])); end = 0
    for c in caps:
        a, b = float(c['start']), float(c['end'])
        if not math.isfinite(a + b) or a < 0 or b <= a or b > seconds + 1/30 or a < end - .001:
            raise ValueError('字幕范围/重叠错误；时间不含封面偏移')
        if not c['text'].strip():
            raise ValueError('空字幕')
        end = b
    if not caps:
        raise ValueError('没有字幕')
    return body, audio, cover, caps, seconds


def srt_time(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def main():
    p = argparse.ArgumentParser(description='固定单画面版式，自动插入6帧封面与字幕')
    p.add_argument('root'); p.add_argument('--spec', default='render.json'); p.add_argument('--validate-only', action='store_true')
    args = p.parse_args(); root = root_path(args.root); read(root / 'project.json'); require_tools()
    spec = read(inside(root, args.spec)); body, audio, cover, caps, seconds = validate(root, spec)
    if args.validate_only:
        print('render inputs valid'); return
    w = root / 'edit'; w.mkdir(exist_ok=True); frames = math.ceil((seconds + .2) * 30)
    im = Image.new('RGB', (1080, 1920), LAYOUT['background']); dr = ImageDraw.Draw(im)
    dr.text((45, 62), f"WorkBuddy实操 · {spec.get('number', '')}", font=font(42), fill='#d6dee9')
    title = spec['title']; size = 60
    while size > 38 and dr.textbbox((0, 0), title, font=font(size))[2] > 990:
        size -= 2
    if dr.textbbox((0, 0), title, font=font(size))[2] > 990:
        raise ValueError('标题过长，先压缩标题')
    dr.text((45, 138), title, font=font(size), fill='white')
    dr.text((45, 211), spec.get('footnote', ''), font=font(22), fill='#a5afc0')
    dr.text((540, 1860), spec.get('footer', ''), font=font(30), fill='#a5afc0', anchor='mm')
    im.save(w / 'layout.png'); Image.open(cover).convert('RGB').save(w / 'cover.jpg', quality=98)
    f = font(50); cache = {}
    for c in caps:
        im = Image.new('RGB', (1080, 190), LAYOUT['background']); dr = ImageDraw.Draw(im)
        lines = ['']
        for char in c['text']:
            if dr.textbbox((0, 0), lines[-1] + char, font=f)[2] > 990:
                lines.append('')
            lines[-1] += char
        if len(lines) > 2:
            raise ValueError('单条字幕超过两行，请按真实说话时间拆开')
        for i, line in enumerate(lines):
            dr.text((540, 66 + i*55 - (len(lines)-1)*27), line, font=f, fill='white', anchor='mm', stroke_width=1)
        cache[c['text']] = im.tobytes()
    blank = Image.new('RGB', (1080, 190), LAYOUT['background']).tobytes()
    subtitle_movie = w / 'subtitles.mov'
    process = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
        '-s', '1080x190', '-r', '30', '-i', 'pipe:0', '-an', '-c:v', 'qtrle', str(subtitle_movie)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for n in range(frames):
            t = n/30 - .2; c = next((c for c in caps if c['start'] <= t < c['end']), None)
            process.stdin.write(cache[c['text']] if c else blank)
        process.stdin.close(); err = process.stderr.read(); code = process.wait()
        if code:
            raise RuntimeError('字幕渲染失败: ' + err.decode(errors='replace')[-800:])
    except Exception:
        if process.poll() is None:
            process.kill(); process.wait()
        raise
    output = inside(root, spec.get('output', 'final.mp4')); output.parent.mkdir(parents=True, exist_ok=True)
    filt = ("[2:v]trim=duration=" + str(frames/30-.2) + ",setpts=PTS-STARTPTS+0.2/TB[b];"
        "[1:v][b]overlay=0:235:enable='gte(t,0.2)':eof_action=repeat[base];"
        "[base][4:v]overlay=0:1615[cap];[0:v]fps=30,trim=end_frame=6,setpts=PTS-STARTPTS[c];"
        "[cap][c]overlay=0:0:enable='lt(t,0.2)':eof_action=pass[v];"
        "[3:a]adelay=200:all=1,loudnorm=I=-16:TP=-1.5:LRA=7[a]")
    run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', str(w/'cover.jpg'), '-loop', '1', '-i', str(w/'layout.png'),
         '-i', str(body), '-i', str(audio), '-i', str(subtitle_movie), '-filter_complex', filt, '-map', '[v]', '-map', '[a]',
         '-t', str(frames/30), '-r', '30', '-c:v', 'libx264', '-threads', '4', '-preset', 'fast', '-crf', '18',
         '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-movflags', '+faststart', str(output)])
    (root / '字幕.srt').write_text('\n'.join(f'{i+1}\n{srt_time(c["start"]+.2)} --> {srt_time(c["end"]+.2)}\n{c["text"]}\n' for i, c in enumerate(caps)), encoding='utf-8')
    write(w / 'render-record.json', {'at': now(), 'video_sha256': sha(output), 'frames': frames,
          'spec': spec, 'body_sha256': sha(body), 'audio_sha256': sha(audio), 'cover_sha256': sha(cover)})
    print(str(output))


if __name__ == '__main__':
    fail_main(main)
