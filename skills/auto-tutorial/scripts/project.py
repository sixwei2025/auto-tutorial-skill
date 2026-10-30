import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from common import REVIEW_ITEMS, ensure_review_items, fail_main, inside, new_review, now, read, require_tools, root_path, sha, verify_profile, write


def main():
    parser = argparse.ArgumentParser(description='持久计时、依赖、人工审阅与交付登记')
    sub = parser.add_subparsers(dest='command', required=True)
    start = sub.add_parser('start'); start.add_argument('root'); start.add_argument('--topic', required=True)
    start.add_argument('--expected-seconds', type=float, required=True); start.add_argument('--started-at')
    sub.add_parser('status').add_argument('root')
    sub.add_parser('preflight').add_argument('root')
    imp = sub.add_parser('import'); imp.add_argument('root'); imp.add_argument('source'); imp.add_argument('--name', required=True)
    rev = sub.add_parser('review'); rev.add_argument('root'); rev.add_argument('--video', required=True)
    rev.add_argument('--item', choices=REVIEW_ITEMS, required=True); rev.add_argument('--status', choices=['passed', 'failed', 'pending'], required=True)
    rev.add_argument('--note', required=True)
    deliver = sub.add_parser('deliver'); deliver.add_argument('root'); deliver.add_argument('--video', required=True)
    args = parser.parse_args(); root = root_path(args.root); record = root / 'project.json'
    if args.command == 'start':
        if record.exists():
            p = read(record)
            if p['topic'] != args.topic:
                raise ValueError('此ROOT已有其他选题；不要覆盖其记录')
            print(json.dumps({'status': 'resumed', 'started_at': p['started_at'], 'reset': False}, ensure_ascii=False)); return
        if not math.isfinite(args.expected_seconds) or args.expected_seconds <= 0:
            raise ValueError('预计成片时长须大于0')
        begun = datetime.fromisoformat(args.started_at) if args.started_at else datetime.now(timezone.utc)
        if begun.tzinfo is None or begun > datetime.now(timezone.utc):
            raise ValueError('首次起点须含时区且不能在未来')
        for d in ('raw', 'edit', 'voice', 'qa'):
            (root / d).mkdir(parents=True, exist_ok=True)
        p = {'topic': args.topic, 'started_at': begun.isoformat(), 'expected_seconds': args.expected_seconds,
             'deadline_seconds': 600 if args.expected_seconds <= 60 else None, 'mode': 'screenshot_dynamic', 'events': [], 'status': 'in_progress'}
        write(record, p)
    elif args.command == 'preflight':
        p = read(record); require_tools(); voice = verify_profile(root)
        report = {'checked_at': now(), 'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe'),
                  'mode': 'screenshot_dynamic', 'pillow_available': __import__('PIL').__version__, 'voice': voice,
                  'gui_privacy_permission_and_window': 'must_check_visually'}
        write(root / 'qa/preflight.json', report); print(json.dumps(report, ensure_ascii=False)); return
    elif args.command == 'import':
        read(record); source = Path(args.source).expanduser().resolve(); target = inside(root, args.name)
        if target.exists() and sha(source) != sha(target):
            raise ValueError('目标素材已存在且不同；选新版本名称，不覆盖')
        target.parent.mkdir(parents=True, exist_ok=True)
        if source != target and not target.exists():
            shutil.copy2(source, target)
        p = read(record); p['events'].append({'at': now(), 'type': 'import', 'source': str(source), 'target': str(target), 'sha256': sha(target)})
        write(record, p); print(str(target)); return
    elif args.command == 'review':
        video = inside(root, args.video); review_path = root / 'qa/review.json'; signature = sha(video)
        review = read(review_path) if review_path.exists() else new_review(video)
        if review['sha256'] != signature:
            review = new_review(video)  # Changes invalidate every old human item.
        ensure_review_items(review)
        if not args.note.strip():
            raise ValueError('人工审阅须写实际观察证据')
        review['items'][args.item] = {'status': args.status, 'note': args.note, 'checked_at': now()}
        review['updated_at'] = now(); write(review_path, review)
        print(json.dumps(review['items'][args.item], ensure_ascii=False)); return
    elif args.command == 'deliver':
        p = read(record); video = inside(root, args.video); signature = sha(video)
        technical = read(root / 'qa/technical.json'); review = read(root / 'qa/review.json')
        if technical['sha256'] != signature or review['sha256'] != signature:
            raise ValueError('成片已改变；旧机器/人工检查无效')
        ensure_review_items(review)
        write(root / 'qa/review.json', review)
        missing = [k for k in REVIEW_ITEMS if review['items'][k].get('status') != 'passed' or not review['items'][k].get('note', '').strip()]
        if not technical['passed'] or missing:
            raise ValueError('尚未完成交付检查: ' + ', '.join(missing or ['技术项失败']))
        completed = datetime.now(timezone.utc); seconds = (completed - datetime.fromisoformat(p['started_at'])).total_seconds()
        # Check actual duration too; estimated duration cannot exempt a <=60s final.
        deadline = 600 if technical['duration'] <= 60 else p['deadline_seconds']
        p['status'] = 'delivered_for_review'; p['events'].append({'at': completed.isoformat(), 'type': 'delivery_record',
            'video': str(video), 'sha256': signature, 'elapsed_seconds': round(seconds, 2),
            'deadline_seconds': deadline, 'within_deadline': seconds <= deadline if deadline else None,
            'user_accepted': False, 'published': False})
        write(record, p)
    else:
        p = read(record)
    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(p['started_at'])).total_seconds()
    print(json.dumps({'status': p['status'], 'started_at': p['started_at'], 'elapsed_seconds': round(elapsed, 2),
                      'deadline_seconds': p['deadline_seconds']}, ensure_ascii=False))


if __name__ == '__main__':
    fail_main(main)
