import argparse
import io
import json
import math
import re
from PIL import Image, ImageChops, ImageStat
from common import duration, ensure_review_items, fail_main, fps, inside, new_review, now, probe, read, require_tools, root_path, run, sha, stream, write


def frame(video, index):
    data = run(['ffmpeg', '-v', 'error', '-i', str(video), '-vf', f'select=eq(n\\,{index})',
                '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1']).stdout
    return Image.open(io.BytesIO(data)).convert('RGB')


def mae(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean)/3


def main():
    p = argparse.ArgumentParser(description='截图动态成片机器检查与待人工审阅记录；不自动声称操作真实')
    p.add_argument('root'); p.add_argument('--spec', default='render.json'); p.add_argument('--video', required=True)
    args = p.parse_args(); root = root_path(args.root); read(root/'project.json'); require_tools()
    spec = read(inside(root, args.spec)); video = inside(root, args.video); info = probe(video)
    v = stream(info, 'video'); a = stream(info, 'audio'); signature = sha(video); checks = {}
    if v is None or a is None:
        raise ValueError('成片缺少画面或声音轨道')
    seconds = duration(info, 'video')
    checks['dimensions_fps'] = (v['width'], v['height']) == (1080, 1920) and abs(fps(v)-30) < .001
    checks['av_duration'] = abs(seconds-duration(info, 'audio')) <= .08
    decode = run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'])
    checks['full_decode'] = not decode.stderr.strip()
    data = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(video)]).stdout)
    times = [float(f['best_effort_timestamp_time']) for f in data['frames']]
    checks['frame_count'] = abs(len(times) - round(seconds*30)) <= 1
    checks['timestamps'] = bool(times) and abs(times[0]) < .001 and all(abs(y-x-1/30) < .001 for x,y in zip(times,times[1:]))
    volume = run(['ffmpeg', '-hide_banner', '-i', str(video), '-af', 'volumedetect', '-vn', '-sn', '-f', 'null', '-']).stderr.decode()
    mean = re.search(r'mean_volume: ([\-\w.]+) dB', volume); peak = re.search(r'max_volume: ([\-\w.]+) dB', volume)
    if not mean or not peak:
        raise ValueError('无法分析声音')
    mv, pv = float(mean[1]), float(peak[1])
    checks['audio_present_not_clipped'] = math.isfinite(mv) and mv > -35 and pv < -.1
    caps = read(inside(root, spec['captions'])); last = 0
    checks['caption_ranges'] = bool(caps)
    for c in caps:
        start, end = float(c['start']), float(c['end'])
        checks['caption_ranges'] &= math.isfinite(start+end) and start >= last-.001 and end > start and end+.2 <= seconds+1/30
        last = end
    cover = Image.open(inside(root, spec['cover'])).convert('RGB')
    cover_errors = []
    if cover.size == (1080, 1920) and checks['dimensions_fps']:
        cover_errors = [mae(frame(video, i), cover) for i in range(6)]
        checks['cover_six_frames'] = max(cover_errors) < 12 and mae(frame(video, 6), cover) > 12
    else:
        checks['cover_six_frames'] = False
    source_record = root / 'edit/screenshot-record.json'
    checks['screenshot_sources'] = False
    checks['screenshot_body_audio_plan'] = False
    checks['screenshot_duration'] = False
    if source_record.exists():
        mapping = read(source_record)
        shots = mapping.get('shots', [])
        checks['screenshot_sources'] = bool(shots) and mapping.get('mode') == 'screenshot_dynamic'
        for shot in shots:
            checks['screenshot_sources'] &= bool(shot.get('evidence', '').strip()) and sha(inside(root, shot['file'])) == shot['source_sha256'] and sha(inside(root, shot['safe_image'])) == shot['safe_sha256']
        checks['screenshot_body_audio_plan'] = (sha(inside(root, spec['body'])) == mapping['body_sha256']
            and sha(inside(root, spec['audio'])) == mapping['audio_sha256']
            and sha(inside(root, mapping['plan'])) == mapping['plan_sha256'])
        checks['screenshot_duration'] = abs(mapping['duration'] - duration(probe(inside(root, spec['body'])), 'video')) <= 1/30
    report = {'checked_at': now(), 'sha256': signature, 'video': str(video), 'duration': seconds,
              'frames': len(times), 'mean_volume_db': mv, 'peak_volume_db': pv,
              'cover_mae': cover_errors, 'checks': checks, 'passed': all(checks.values()),
              'human_review_required': True, 'screenshot_record_available': source_record.exists(), 'mode': 'screenshot_dynamic'}
    write(root / 'qa/technical.json', report)
    review_path = root / 'qa/review.json'
    if not review_path.exists() or read(review_path)['sha256'] != signature:
        write(review_path, new_review(video))
    else:
        write(review_path, ensure_review_items(read(review_path)))
    for label, t in [('opening', .3), ('middle', seconds/2), ('ending', max(.3,seconds-.4))]:
        run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', str(video), '-frames:v', '1', str(root/f'qa/{label}.png')])
    print(json.dumps(report, ensure_ascii=False))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    fail_main(main)
