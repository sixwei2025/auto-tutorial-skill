import argparse, subprocess, json
from pathlib import Path
import numpy as np
from PIL import Image
from common import inside, read, write, sha, probe, stream, duration, fps
p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--plan',default='camera.json');a=p.parse_args();r=Path(a.root).resolve()
spec=read(inside(r,a.plan));record=read(r/'qa/fullscreen-render.json');vpath=inside(r,spec.get('output','final.mp4'));info=probe(vpath);v=stream(info,'video');au=stream(info,'audio')
checks={}
checks['format']=v['width']==1080 and v['height']==1920 and abs(fps(v)-30)<.001 and v['codec_name']=='h264' and au is not None
checks['frames']=int(v['nb_frames'])==record['frames']
checks['duration']=abs(duration(info,'video')-record['duration'])<.04 and abs(duration(info,'audio')-duration(info,'video'))<.15
checks['hashes']=sha(vpath)==record['video_sha256'] and sha(inside(r,a.plan))==record['plan_sha256'] and all(sha(inside(r,spec[k]))==record[k+'_sha256'] for k in ('audio','cover','captions')) and all(sha(inside(r,k))==v for k,v in {**record['sources'],**record['original_video_sources']}.items())
subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(vpath),'-f','null','-'],check=True);checks['decode']=True
raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(vpath),'-frames:v','6','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
frames=np.frombuffer(raw,dtype=np.uint8).reshape(6,1920,1080,3);cover=np.array(Image.open(inside(r,spec['cover'])).convert('RGB')).astype(float)
checks['cover_six_frames']=all(np.mean(np.abs(x.astype(float)-cover))<12 for x in frames)
result={'sha256':sha(vpath),'duration':duration(info,'video'),'passed':all(checks.values()),'checks':checks,'human_review':'pending; machine checks do not establish truth, privacy, voice identity or subjective audio quality'}
write(r/'qa/technical.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if not result['passed']:raise SystemExit(1)
