"""Build a dynamic screenshot body from real source images; no recording tools."""
import argparse
import math
from pathlib import Path
from PIL import Image, ImageDraw
from common import duration, fail_main, inside, now, probe, read, require_tools, root_path, run, sha, write


def rectangle(value, width, height):
    if not isinstance(value, list) or len(value) != 4 or any(type(n) is not int for n in value):
        raise ValueError('截图区域须为四个整数[x,y,width,height]')
    x, y, w, h = value
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x+w > width or y+h > height:
        raise ValueError('截图区域越界')
    return x, y, x+w, y+h


def main():
    p = argparse.ArgumentParser(description='真实截图裁切、隐私实色遮挡、高亮与动态缩放，生成固定body')
    p.add_argument('root'); p.add_argument('--plan', default='shots.json'); p.add_argument('--validate-only', action='store_true')
    args = p.parse_args(); root = root_path(args.root); read(root/'project.json'); require_tools()
    plan = read(inside(root, args.plan)); shots = plan['shots']
    if not shots:
        raise ValueError('没有截图镜头')
    audio = inside(root, plan.get('audio', 'voice/narration.wav'))
    audio_seconds = duration(probe(audio), 'audio')
    dest = root/'edit/screenshots'; dest.mkdir(parents=True, exist_ok=True)
    records = []; position = 0
    for i, s in enumerate(shots):
        source = inside(root, s['file'])
        if not s.get('evidence', '').strip():
            raise ValueError('每张截图须写来源、实际操作及可见结果，不把填表当成结果验证')
        seconds = float(s['seconds'])
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('镜头时长须为正有限数')
        frames = round(seconds*30)
        if frames < 1:
            raise ValueError('镜头不足一帧')
        zoom = s.get('zoom', [1, 1.06]); focus = s.get('focus', [.5, .5])
        if len(zoom) != 2 or len(focus) != 2 or not all(math.isfinite(float(v)) for v in zoom+focus):
            raise ValueError('镜头缩放或焦点参数无效')
        z0, z1 = map(float, zoom); fx, fy = map(float, focus)
        if not (1 <= z0 <= 1.2 and 1 <= z1 <= 1.2 and 0 <= fx <= 1 and 0 <= fy <= 1):
            raise ValueError('缩放须在1—1.2之间，焦点须在0—1之间；取近景用真实截图局部裁切')
        with Image.open(source) as opened:
            im = opened.convert('RGB')
        # Mask original coordinates BEFORE cropping; highlights are crop-relative.
        dr = ImageDraw.Draw(im)
        for box in s.get('masks', []):
            x0, y0, x1, y1 = rectangle(box, *im.size)
            dr.rectangle((x0, y0, x1-1, y1-1), fill='#111827')
        if s.get('crop') is not None:
            im = im.crop(rectangle(s['crop'], *im.size))
        dr = ImageDraw.Draw(im)
        for mark in s.get('highlights', []):
            box = mark.get('box') if isinstance(mark, dict) else mark
            shape = mark.get('shape', 'rect') if isinstance(mark, dict) else 'rect'
            if shape not in ('rect', 'ellipse'):
                raise ValueError('重点标记形状仅支持rect矩形框或ellipse圈')
            x0, y0, x1, y1 = rectangle(box, *im.size)
            paint = dr.ellipse if shape == 'ellipse' else dr.rectangle
            paint((x0, y0, x1-1, y1-1), outline='#ffdc32', width=max(3, round(im.width/220)))
        scale = min(1080/im.width, 1350/im.height)
        im = im.resize((max(1,round(im.width*scale)), max(1,round(im.height*scale))), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (1080, 1350), '#101827')
        canvas.paste(im, ((1080-im.width)//2, (1350-im.height)//2))
        png = dest/f'{i:03}.png'; canvas.save(png)
        entry = {'file': s['file'], 'source_sha256': sha(source), 'evidence': s['evidence'],
                 'output_start': position/30, 'output_end': (position+frames)/30, 'frames': frames,
                 'crop': s.get('crop'), 'masks': s.get('masks', []), 'highlights': s.get('highlights', []),
                 'zoom': zoom, 'focus': focus, 'safe_image': str(png.relative_to(root)), 'safe_sha256': sha(png)}
        records.append(entry); position += frames
    if abs(position/30-audio_seconds) > .15:
        raise ValueError('截图镜头总长与实际旁白相差超过0.15秒；按声音时间调整镜头，不均分字幕')
    if args.validate_only:
        print('screenshot inputs valid; sanitized previews saved'); return
    clips = []
    for i, s in enumerate(records):
        z0, z1 = s['zoom']; fx, fy = s['focus']; frames = s['frames']
        z = f'{z0}+({z1}-{z0})*on/{max(1,frames-1)}'
        vf = (f"zoompan=z='{z}':x='max(0,min(iw-iw/zoom,{fx}*iw-iw/zoom/2))':"
              f"y='max(0,min(ih-ih/zoom,{fy}*ih-ih/zoom/2))':d={frames}:s=1080x1350:fps=30,setsar=1")
        clip = dest/f'{i:03}.mp4'
        run(['ffmpeg','-y','-v','error','-i',str(inside(root,s['safe_image'])),'-vf',vf,
             '-frames:v',str(frames),'-an','-c:v','libx264','-threads','4','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(clip)])
        clips.append(clip)
    # Controlled numeric filenames make this concat manifest independent of shell quoting.
    listing = dest/'concat.txt'; listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
    body = root/'edit/body.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','1','-i',str(listing),'-c','copy','-movflags','+faststart',str(body)])
    write(root/'edit/screenshot-record.json', {'at': now(), 'mode': 'screenshot_dynamic',
          'plan': args.plan, 'plan_sha256': sha(inside(root,args.plan)), 'audio_sha256': sha(audio), 'body_sha256': sha(body),
          'duration': position/30, 'frames': position, 'shots': records})
    print(str(body))


if __name__ == '__main__':
    fail_main(main)
