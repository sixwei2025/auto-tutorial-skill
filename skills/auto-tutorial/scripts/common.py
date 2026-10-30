import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# VoiceBox / TTS：请换成你自己的声音档案与服务地址（示例占位，勿硬编码仅本机可用的秘密）
#   export AUTO_TUTORIAL_VOICEBOX_PROFILE='your-profile-uuid'
#   export AUTO_TUTORIAL_VOICEBOX_URL='http://127.0.0.1:17493'
#   export AUTO_TUTORIAL_VOICEBOX_LOCK="$HOME/voicebox.lock"  # 可选互斥锁路径
PROFILE = os.environ.get('AUTO_TUTORIAL_VOICEBOX_PROFILE', 'YOUR_VOICEBOX_PROFILE_ID')
VOICE_URL = os.environ.get('AUTO_TUTORIAL_VOICEBOX_URL', 'http://127.0.0.1:17493')
VOICEBOX_LOCK = os.environ.get('AUTO_TUTORIAL_VOICEBOX_LOCK', str(Path.home() / 'voicebox.lock'))
REVIEW_ITEMS = ('content', 'playback', 'flow', 'narration', 'captions', 'framing', 'result', 'privacy', 'cover', 'production_method', 'dynamic_ppt', 'closing', 'skill_practice')

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def root_path(value):
    return Path(value).expanduser().resolve()


def inside(root, value):
    p = (root / value).resolve()
    if not p.is_relative_to(root):
        raise ValueError(f'文件必须在唯一项目根内: {p}')
    return p


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]).stdout)


def stream(info, kind):
    return next((s for s in info['streams'] if s['codec_type'] == kind), None)


def duration(info, kind=None):
    s = stream(info, kind) if kind else None
    return float(s.get('duration', info['format']['duration']) if s else info['format']['duration'])


def fps(s):
    a, b = s['avg_frame_rate'].split('/')
    return float(a) / float(b)


def require_tools():
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise RuntimeError(f'缺少 {tool}；停止后续转换')


def voice_request(path, payload=None, timeout=10, binary=False):
    # Only loopback requests; no system proxy/config mutation.
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    request = urllib.request.Request(VOICE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    with op.open(request, timeout=timeout) as response:
        result = response.read()
    return result if binary else json.loads(result)


def verify_profile(root):
    profiles = voice_request('/profiles')
    if isinstance(profiles, dict):
        profiles = profiles.get('profiles', [])
    profile = next((p for p in profiles if p.get('id') == PROFILE), None)
    report = {'checked_at': now(), 'profile_id': PROFILE, 'available': profile is not None,
              'display_name': profile.get('name') if profile else None}
    write(root / 'voice/profile-check.json', report)
    if profile is None:
        raise RuntimeError('指定 VoiceBox 档案不可用；请设置 AUTO_TUTORIAL_VOICEBOX_PROFILE 为你本机可用的档案 ID')
    return report


def new_review(video):
    return {'video': str(video), 'sha256': sha(video), 'updated_at': now(),
            'items': {k: {'status': 'pending', 'note': ''} for k in REVIEW_ITEMS}}


def ensure_review_items(review):
    # Preserve evidence for an unchanged video; newly required items await review.
    items = review.setdefault('items', {})
    for key in REVIEW_ITEMS:
        items.setdefault(key, {'status': 'pending', 'note': ''})
    return review


def fail_main(fn):
    try:
        fn()
    except (ValueError, RuntimeError, KeyError, TypeError, ImportError, OSError, subprocess.CalledProcessError) as e:
        detail = e.stderr.decode(errors='replace')[-1200:] if isinstance(e, subprocess.CalledProcessError) and e.stderr else str(e)
        print(json.dumps({'status': 'blocked', 'reason': detail}, ensure_ascii=False))
        raise SystemExit(1)
