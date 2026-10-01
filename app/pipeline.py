from __future__ import annotations
import json, math, re, shutil, subprocess, textwrap, wave
from pathlib import Path
from typing import List, Dict, Tuple
import requests
from PIL import Image, ImageDraw, ImageFont
from .config import ROOT, OUTPUT, WORK, MEDIA, ASSETS, PEXELS_API_KEY, PIPER_MODEL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

FPS=30
W,H=1080,1920


def run(cmd):
    p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-3000:])
    return p.stdout

def ffprobe_duration(path: Path)->float:
    out=run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)])
    return float(out.strip())

def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')[:60]

def split_segments(script:str)->List[Dict]:
    chunks=[x.strip() for x in re.split(r'(?<=[.!?])\s+', script.strip()) if x.strip()]
    if len(chunks)<3:
        chunks=[x.strip() for x in script.split('\n') if x.strip()]
    return [{'id':i+1,'text':x,'keywords':keywords(x)} for i,x in enumerate(chunks)]

def keywords(text):
    words=re.findall(r"[A-Za-zÀ-ÿ0-9']+",text.lower())
    stop={'the','a','an','and','or','of','to','in','on','de','la','le','les','un','une','des','et','en','pour','que','qui','est','sont','du','au','aux'}
    return ' '.join([w for w in words if w not in stop][:5]) or 'history cinematic'

def generate_story(topic:str)->Dict:
    # Free/local fallback designed for 60–90 second short-form videos.
    t=topic.strip() or 'L’homme qui a survécu à deux bombes nucléaires'
    title=t
    script=(
        f"{t}. Imagine une histoire tellement improbable qu’elle semble inventée. "
        "Pourtant, derrière ce récit se cache une suite d’événements qui a marqué les esprits. "
        "Au début, tout semblait normal. Puis, en quelques secondes, la situation a complètement changé. "
        "Le personnage principal s’est retrouvé au cœur d’un événement qu’il était presque impossible de prévoir. "
        "La première épreuve aurait déjà suffi à bouleverser une vie entière. Il a dû survivre à la peur, à la destruction et à un environnement devenu méconnaissable. "
        "Mais le plus incroyable n’était pas encore arrivé. Après avoir survécu, il a essayé de reprendre une vie normale, pensant que le pire était derrière lui. "
        "Quelques jours plus tard, un nouvel événement l’a placé une nouvelle fois face au danger. "
        "Cette fois encore, les chances de s’en sortir semblaient minuscules. Pourtant, contre toute attente, il a survécu. "
        "Son histoire rappelle une chose étonnante : parfois, la réalité produit des événements tellement extraordinaires qu’ils ressemblent à des scénarios de cinéma. "
        "Et ce qui rend cette histoire encore plus fascinante, c’est que chaque détail montre à quel point quelques secondes peuvent changer une vie pour toujours. "
        "Si tu pensais connaître les histoires de survie les plus incroyables, attends de découvrir celle-ci jusqu’à la fin."
    )
    return {'title':title,'hook':f"Et si survivre à une catastrophe n’était que le début ?",'script':script}

def make_placeholder(path:Path, text:str, index:int):
    im=Image.new('RGB',(W,H),(12+index*5,12+index*4,18+index*3))
    d=ImageDraw.Draw(im)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',64)
    small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',32)
    d.text((70,160),f'VIRALFLOW • {index:02d}',font=small,fill='white')
    lines=textwrap.wrap(text, width=20)
    y=700
    for line in lines:
        box=d.textbbox((0,0),line,font=font); x=(W-(box[2]-box[0]))/2
        d.text((x,y),line,font=font,fill='white',stroke_width=2,stroke_fill='black'); y+=90
    im.save(path)

def fetch_wikimedia(query: str, out: Path, source_log: list) -> bool:
    """Keyless fallback: fetch a freely accessible image from Wikimedia Commons.
    The image is then turned into a short vertical clip by FFmpeg. This avoids a paid media API.
    """
    try:
        api = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action":"query", "generator":"search", "gsrsearch":query,
            "gsrnamespace":6, "gsrlimit":3, "prop":"imageinfo",
            "iiprop":"url|extmetadata", "iiurlwidth":1080,
            "format":"json", "formatversion":2,
        }
        r=requests.get(api, params=params, timeout=3, headers={"User-Agent":"ViralFlow/12 (free media client)"})
        r.raise_for_status()
        pages=r.json().get("query",{}).get("pages",[])
        for page in pages:
            info=(page.get("imageinfo") or [{}])[0]
            url=info.get("thumburl") or info.get("url")
            if not url or not url.lower().split('?')[0].endswith((".jpg",".jpeg",".png",".webp")):
                continue
            rr=requests.get(url,timeout=4,headers={"User-Agent":"ViralFlow/12"})
            rr.raise_for_status(); out.write_bytes(rr.content)
            source_log.append({"provider":"Wikimedia Commons","title":page.get("title",""),"url":url})
            return True
    except Exception:
        return False
    return False


def fetch_pexels(query:str, out:Path):
    if not PEXELS_API_KEY: return False
    headers={'Authorization':PEXELS_API_KEY}
    r=requests.get('https://api.pexels.com/videos/search',params={'query':query,'orientation':'portrait','size':'medium','per_page':5},headers=headers,timeout=20)
    r.raise_for_status(); data=r.json()
    for v in data.get('videos',[]):
        files=sorted(v.get('video_files',[]), key=lambda f:(f.get('width') or 0), reverse=True)
        for f in files:
            link=f.get('link','')
            if link:
                rr=requests.get(link,timeout=60); rr.raise_for_status(); out.write_bytes(rr.content); return True
    return False

def acquire_media(segments):
    paths=[]
    source_log=[]
    # Free mode: fetch one relevant Wikimedia image for the story, then reuse it
    # with different crops/timings. This keeps generation reliable and fast.
    seed=segments[0]['keywords'] if segments else 'history cinematic'
    shared=MEDIA/'shared_story.jpg'
    if shared.exists(): shared.unlink()
    try: ok=fetch_wikimedia(seed,shared,source_log)
    except Exception: ok=False
    if not ok: make_placeholder(shared,seed,1)

    for s in segments:
        mp4=MEDIA/f"seg_{s['id']:02d}.mp4"
        if mp4.exists(): mp4.unlink()
        if PEXELS_API_KEY:
            try:
                if fetch_pexels(s['keywords'],mp4):
                    paths.append(mp4); continue
            except Exception:
                pass
        jpg=MEDIA/f"seg_{s['id']:02d}.jpg"
        shutil.copy2(shared,jpg)
        paths.append(jpg)
    (WORK/'media_sources.json').write_text(json.dumps(source_log,ensure_ascii=False,indent=2),encoding='utf-8')
    return paths

def create_tts(text:str, out:Path):
    # Piper if locally configured; otherwise generate a clean silent track so pipeline remains runnable.
    if PIPER_MODEL and shutil.which('piper'):
        proc=subprocess.run(['piper','--model',PIPER_MODEL,'--output_file',str(out)],input=text,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if proc.returncode==0: return
    # Free local fallback: eSpeak if available; otherwise silence keeps the pipeline runnable.
    if shutil.which('espeak') or shutil.which('espeak-ng'):
        exe=shutil.which('espeak-ng') or shutil.which('espeak')
        proc=subprocess.run([exe,'-v','fr','-s','155','-w',str(out),text],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if proc.returncode==0: return
    duration=max(1.5,min(8.0,len(text)/12))
    samples=int(22050*duration)
    with wave.open(str(out),'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b'\0\0'*samples)

def make_srt(segments, total):
    words=[]
    for s in segments:
        ws=re.findall(r"\S+",s['text']); words += [(w,s['id']) for w in ws]
    n=len(words); per=total/max(n,1)
    def ts(x):
        ms=int(x*1000); h=ms//3600000; ms%=3600000; m=ms//60000; ms%=60000; sec=ms//1000; ms%=1000
        return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'
    lines=[]
    for i,(w,_) in enumerate(words):
        a=i*per; b=(i+1)*per
        lines += [str(i+1),f'{ts(a)} --> {ts(b)}',w,'']
    p=WORK/'captions.srt'; p.write_text('\n'.join(lines),encoding='utf-8'); return p

def render(segments, media, voice, out:Path):
    # Match the visual timeline to the actual voice duration, targeting 60–90s.
    voice_duration=ffprobe_duration(voice)
    target=max(60.0,min(90.0,voice_duration))
    if voice_duration < 60.0:
        target=60.0
    weights=[max(1,len(re.findall(r"\S+",s['text']))) for s in segments]
    total_words=sum(weights)
    durations=[target*w/total_words for w in weights]
    # Keep every visual readable while preserving the total target duration.
    inputs=[]; filters=[]
    for i,(p,d) in enumerate(zip(media,durations)):
        if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}:
            inputs += ['-loop','1','-i',str(p)]
        else:
            inputs += ['-stream_loop','-1','-i',str(p)]
        # Fast motion-ready framing; no expensive per-frame zoom filter.
        filters.append(f'[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},trim=duration={d:.3f},setpts=PTS-STARTPTS,fps={FPS},setsar=1[v{i}]')
    concat=''.join(f'[v{i}]' for i in range(len(media)))
    filters.append(concat+f'concat=n={len(media)}:v=1:a=0[v]')
    srt=make_srt(segments,target)
    filters.append(f"[v]subtitles='{srt.as_posix()}'[vo]")
    cmd=['ffmpeg','-y']+inputs+['-i',str(voice),'-filter_complex',';'.join(filters),'-map','[vo]','-map',f'{len(media)}:a','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-r',str(FPS),'-c:a','aac','-b:a','128k','-t',f'{target:.2f}',str(out)]
    run(cmd); return target

def telegram_send(video:Path):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID): return False
    url=f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo'
    with video.open('rb') as f:
        r=requests.post(url,data={'chat_id':TELEGRAM_CHAT_ID},files={'video':f},timeout=120)
    return r.ok

def build(topic):
    story=generate_story(topic); segments=split_segments(story['script']); media=acquire_media(segments)
    voice=WORK/'voice.wav'; create_tts(story['script'],voice)
    out=OUTPUT/f"{slug(story['title']) or 'viralflow-video'}.mp4"
    total=render(segments,media,voice,out)
    meta={'title':story['title'],'hook':story['hook'],'script':story['script'],'segments':segments,'duration':total,'video':str(out),'free_mode':not bool(PEXELS_API_KEY),'media_sources':str(WORK/'media_sources.json')}
    (OUTPUT/f'{out.stem}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    telegram_send(out)
    return meta
