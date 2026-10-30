import argparse
import difflib
import re
from pathlib import Path
from common import fail_main, inside, read, root_path, sha, write


def clean(s):
    return re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', s).lower()


def main():
    p = argparse.ArgumentParser(description='从实际声音识别时间点；不按字数均分旁白时间')
    p.add_argument('root'); p.add_argument('--audio', default='voice/narration.wav')
    p.add_argument('--text', default='narration.txt'); p.add_argument('--output', default='captions.json')
    args = p.parse_args(); root = root_path(args.root); read(root/'project.json')
    import whisper
    cached = Path.home()/'.cache/whisper/base.pt'
    expected_hash = whisper._MODELS['base'].split('/')[-2]
    if not cached.exists() or sha(cached) != expected_hash:
        raise RuntimeError('本机已验证base语音模型不可用；停止，不自动下载模型或另换声音服务')
    audio = inside(root,args.audio); text = inside(root,args.text).read_text(encoding='utf-8').strip()
    model = whisper.load_model('base',device='cpu',download_root=str(cached.parent))
    samples = whisper.load_audio(str(audio)); segments=[]; recognized=[]
    # This local voice was verified with short windows; do not prime ASR to invent expected wording.
    for offset in range(0,len(samples),7*16000):
        chunk = model.transcribe(samples[offset:offset+7*16000],language='zh',word_timestamps=True,fp16=False,condition_on_previous_text=False)
        recognized.append(chunk['text'])
        for seg in chunk['segments']:
            seg['start']+=offset/16000;seg['end']+=offset/16000
            for word in seg.get('words',[]):
                word['start']+=offset/16000;word['end']+=offset/16000
            segments.append(seg)
    result={'text':''.join(recognized),'segments':segments}
    vocabulary = read(Path(__file__).resolve().parent.parent/'assets/vocabulary.json')
    active = {a:b for a,b in vocabulary.items() if b.lower() in text.lower()}
    def spelling(s):
        for alias,canonical in active.items():
            s=re.sub(re.escape(alias),canonical,s,flags=re.IGNORECASE)
        return s
    target,seen = clean(text),clean(spelling(result['text']))
    if not target:
        raise ValueError('待核对旁白为空')
    similarity = difflib.SequenceMatcher(None,target,seen,autojunk=False).ratio()
    output = inside(root,args.output)
    write(output.with_suffix('.asr.json'),{'source_audio':str(audio),'audio_sha256':sha(audio),'expected_text':text,
          'recognized_text':result['text'],'normalized_named_terms':active,'similarity':similarity,'segments':result['segments'],'human_listening_required':True})
    if similarity < .85:
        raise RuntimeError('声音识别与原稿差异较大，保留ASR记录，先复听修正再对齐')
    words = [w for s in result['segments'] for w in s.get('words',[]) if w['end'] > w['start'] and w['word'].strip()]
    if not words:
        raise RuntimeError('识别未返回实际word时间，不能改按字数均分')
    caps=[];group=[]
    def flush():
        if group:
            caps.append({'start':float(group[0]['start']),'end':float(group[-1]['end']),'text':spelling(''.join(w['word'] for w in group).strip())});group.clear()
    for word in words:
        current=''.join(w['word'] for w in group)
        if group and (len(current+word['word']) > 18 or word['start']-group[-1]['end'] > .35):
            flush()
        group.append(word)
        if re.search(r'[，。！？；,.!?;]$',word['word'].strip()):
            flush()
    flush()
    for a,b in zip(caps,caps[1:]):
        if a['end'] > b['start']:
            raise RuntimeError('识别时间重叠；需根据真实声音修正')
    write(output,caps);print(str(output))


if __name__=='__main__':
    fail_main(main)
