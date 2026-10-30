from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,math,subprocess,sys,hashlib
import argparse
from common import inside, read, write, sha, probe, duration, stream, fps as getfps
ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('--plan',default='camera.json');ap.add_argument('--validate-only',action='store_true');args=ap.parse_args()
r=Path(args.root).resolve();planpath=inside(r,args.plan);p=read(planpath);caps=read(inside(r,p['captions']));W,H=1080,1920;fps=30
(r/'qa').mkdir(parents=True,exist_ok=True)
assert p['series']=='WorkBuddy实操'
assert abs(duration(probe(inside(r,p['audio'])),'audio')-p['duration'])<.05
assert Image.open(inside(r,p['cover'])).size==(W,H)
previous=0
for c in caps:
 assert 0<=previous<=c['start']<c['end']<=p['duration']+.034 and c['text'].strip()
 previous=c['end']
previous=0
for s in p['scenes']:
 assert abs(s['start']-previous)<.001 and s['end']>s['start'] and s['evidence'].strip()
 inside(r,s['file']);previous=s['end']
 if s.get('type','image')=='video':
  v=stream(probe(inside(r,s['file'])),'video')
  assert (v['width'],v['height'])==(W,H) and abs(getfps(v)-30)<.001
  assert abs(duration(probe(inside(r,s['file'])),'video')-(s['end']-s['start']))<.05
  assert s['preview_label'].strip() and s['source'].strip()
  inside(r,s['source'])
 else:
  assert s['camera'] and s['camera'][0][0]==0
  last=-1
  for k in s['camera']:
   assert len(k)==4 and all(math.isfinite(x) for x in k) and last<k[0]<=s['end']-s['start']+.000001 and k[3]>0
   last=k[0]
assert abs(previous-p['duration'])<.001
fontfile='/System/Library/Fonts/STHeiti Medium.ttc';f=ImageFont.truetype(fontfile,47);small=ImageFont.truetype(fontfile,32)
imgs={}
for s in p['scenes']:
 if s.get('type','image')=='video':continue
 im=Image.open(inside(r,s['file'])).convert('RGB');dr=ImageDraw.Draw(im)
 for x,y,w,h in s['masks']:dr.rectangle((x,y,x+w-1,y+h-1),fill='#f8f9fc')
 imgs[s['file']]=im

def camera(s,t):
 keys=s['camera'];local=t-s['start']
 if local<=keys[0][0]:return keys[0][1:]
 for a,b in zip(keys,keys[1:]):
  if local<=b[0]:
   u=max(0,min(1,(local-a[0])/(b[0]-a[0])));u=u*u*u*(u*(u*6-15)+10)
   return [a[i]+(b[i]-a[i])*u for i in (1,2,3)]
 return keys[-1][1:]

video_decoders={}
def frame(t):
 s=next((s for s in p['scenes'] if s['start']<=t<s['end']),p['scenes'][-1])
 if s.get('type','image')=='video':
  import io
  if args.validate_only:
   data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t-s['start']),'-i',str(inside(r,s['file'])),'-frames:v','1','-f','image2pipe','-vcodec','png','pipe:1'])
   im=Image.open(io.BytesIO(data)).convert('RGB')
  else:
   key=s['start']
   if key not in video_decoders:
    video_decoders[key]=subprocess.Popen(['ffmpeg','-v','error','-i',str(inside(r,s['file'])),'-an','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE)
   data=video_decoders[key].stdout.read(W*H*3)
   if len(data)!=W*H*3:raise RuntimeError('真实成品预览解码提前结束')
   im=Image.frombytes('RGB',(W,H),data)
 else:
  cx,cy,vw=camera(s,t);scale=vw/W;vh=H*scale
  im=imgs[s['file']].transform((W,H),Image.Transform.AFFINE,(scale,0,cx-vw/2,0,scale,cy-vh/2),resample=Image.Resampling.BICUBIC,fillcolor='#f8f9fc')
 dr=ImageDraw.Draw(im);label=s['title']+((' · '+s['preview_label']) if s.get('type')=='video' else '');bw=dr.textbbox((0,0),label,font=small)[2]+40
 dr.rounded_rectangle((28,36,28+bw,104),radius=14,fill='#132137');dr.text((48,52),label,font=small,fill='white')
 c=next((c for c in caps if c['start']<=t<c['end']),None)
 if c:
  lines=['']
  for ch in c['text']:
   if dr.textbbox((0,0),lines[-1]+ch,font=f)[2]>980:lines.append('')
   lines[-1]+=ch
  if len(lines)>2:raise ValueError('字幕超过两行，请按实际说话时间拆分')
  bh=75+len(lines)*57;dr.rounded_rectangle((24,H-bh-35,W-24,H-35),radius=20,fill='#132137')
  for i,line in enumerate(lines):dr.text((W/2,H-bh-10+i*57),line,font=f,fill='white',anchor='mt',stroke_width=1)
 return im

if args.validate_only:
 out=r/'qa/camera-preview';out.mkdir(exist_ok=True);samples=sorted(set(v for s in p['scenes'] for v in (s['start'],(s['start']+s['end'])/2,max(s['start'],s['end']-1/30))))
 sheet=Image.new('RGB',(1440,((len(samples)+5)//6)*460),'white');d=ImageDraw.Draw(sheet)
 for i,t in enumerate(samples):
  im=frame(t);im.save(out/f'{t}.png');im.thumbnail((240,426));x=i%6*240;y=i//6*460;sheet.paste(im,(x,y));d.text((x+5,y+433),f'{t}s',fill='black')
 sheet.save(out/'sheet.jpg');print(out/'sheet.jpg');sys.exit()
cover=Image.open(inside(r,p['cover'])).convert('RGB').resize((W,H),Image.Resampling.LANCZOS)
frames=math.ceil(p['duration']*fps);out=inside(r,p.get('output','final.mp4'));out.parent.mkdir(parents=True,exist_ok=True)
encode_args=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','30','-i','pipe:0','-i',str(r/p['audio']),'-map','0:v','-map','1:a','-af','adelay=200:all=1,loudnorm=I=-16:TP=-1.5:LRA=7','-c:v','libx264','-threads','4','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-t',str((frames+6)/fps),'-movflags','+faststart',str(out)]
proc=subprocess.Popen(encode_args,stdin=subprocess.PIPE)
try:
 raw=cover.tobytes()
 for i in range(6):proc.stdin.write(raw)
 for i in range(frames):
  proc.stdin.write(frame(i/fps).tobytes())
  if i%900==0:print('rendered',i,'/',frames,flush=True)
 proc.stdin.close();ret=proc.wait()
 if ret:raise RuntimeError(f'encode failed {ret}')
except:
 proc.kill();raise
for decoder in video_decoders.values():
 decoder.stdout.close()
 if decoder.poll() is None:decoder.terminate()
 decoder.wait()
record={'mode':'fullscreen_affine_camera','frames':frames+6,'duration':(frames+6)/fps,'video_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'plan_sha256':sha(planpath),'plan':args.plan,'audio_sha256':sha(inside(r,p['audio'])),'cover_sha256':sha(inside(r,p['cover'])),'captions_sha256':sha(inside(r,p['captions'])),'original_video_sources':{s['source']:sha(inside(r,s['source'])) for s in p['scenes'] if s.get('type')=='video'},'sources':{s['file']:hashlib.sha256((r/s['file']).read_bytes()).hexdigest() for s in p['scenes']},'motion':'purposeful wide-medium-close; quintic ease; locked holds; float affine sampling'}
json.dump(record,open(r/'qa/fullscreen-render.json','w'),ensure_ascii=False,indent=2)
def srt_time(seconds):
 ms=round(seconds*1000)
 return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
(r/'字幕.srt').write_text('\n'.join(f'{i+1}\n{srt_time(c["start"]+.2)} --> {srt_time(c["end"]+.2)}\n{c["text"]}\n' for i,c in enumerate(caps)),encoding='utf-8')
print(out)
