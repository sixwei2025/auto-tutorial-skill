import argparse
import json
import math
import time
from common import PROFILE, fail_main, inside, now, read, require_tools, root_path, run, verify_profile, voice_request, write


def main():
    p = argparse.ArgumentParser(description='验证固定VoiceBox声音，并保存生成来源')
    p.add_argument('root'); p.add_argument('--text'); p.add_argument('--verify-only', action='store_true')
    p.add_argument('--speed', type=float, default=1.35); p.add_argument('--timeout', type=float, default=75)
    p.add_argument('--stem', default='narration'); p.add_argument('--resume', action='store_true')
    args = p.parse_args(); root = root_path(args.root); read(root / 'project.json')
    report = verify_profile(root)
    if args.verify_only:
        print(json.dumps(report, ensure_ascii=False)); return
    if not math.isfinite(args.speed) or not .5 <= args.speed <= 2:
        raise ValueError('速度须为0.5—2之间的有限值；按本条正文选定速度保持全片一致，不为开头赶秒数')
    if not math.isfinite(args.timeout) or args.timeout <= 0 or args.timeout > 90:
        raise ValueError('等待上限须为1—90秒，阻碍及时报告')
    require_tools(); text = inside(root, args.text or 'narration.txt').read_text(encoding='utf-8').strip()
    if not text:
        raise ValueError('旁白为空')
    if not args.stem or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.stem):
        raise ValueError('声音版本名称仅用英文字母、数字、连字符或下划线')
    job_path = root / f'voice/{args.stem}.job.json'
    if job_path.exists() and not args.resume:
        raise ValueError('已有声音任务；用--resume检查，修订用同一ROOT下新--stem，避免重复生成')
    began = time.monotonic()
    if args.resume:
        saved = read(job_path)
        if saved['text'] != text or saved['request_profile_id'] != PROFILE:
            raise ValueError('原任务文本/档案不一致，不能当成同一任务恢复')
        job = saved['job']
    else:
        job = voice_request('/generate', {'profile_id': PROFILE, 'text': text, 'language': 'zh', 'engine': 'qwen', 'model_size': '1.7B', 'normalize': True}, timeout=20)
        write(job_path, {'requested_at': now(), 'request_profile_id': PROFILE, 'text': text, 'job': job})
    while time.monotonic() - began < args.timeout:
        job = voice_request('/history/' + job['id'], timeout=10)
        if job['status'] == 'completed':
            break
        if job['status'] in ('failed', 'cancelled'):
            raise RuntimeError('声音生成失败；任务ID ' + job['id'])
        time.sleep(1)
    else:
        raise RuntimeError('声音生成超时；保留任务记录，用--resume检查，不重开计时或重复提交')
    if job.get('profile_id') != PROFILE:
        raise RuntimeError('返回声音档案与指定ID不符')
    raw = root / f'voice/{args.stem}-source.wav'; raw.write_bytes(voice_request('/audio/' + job['id'], timeout=20, binary=True))
    output = root / f'voice/{args.stem}.wav'
    run(['ffmpeg', '-y', '-v', 'error', '-i', str(raw), '-af', f'atempo={args.speed}', '-ar', '48000', str(output)])
    write(job_path, {'completed_at': now(), 'request_profile_id': PROFILE, 'text': text, 'speed': args.speed, 'job': job})
    print(json.dumps({'status': 'completed', 'job_id': job['id'], 'profile_id': PROFILE, 'output': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    fail_main(main)
