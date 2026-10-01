from __future__ import annotations
import os, time, tempfile
from pathlib import Path
import requests
from .pipeline import build

TOKEN=os.getenv('TELEGRAM_BOT_TOKEN','')
API=f'https://api.telegram.org/bot{TOKEN}'
OFFSET=0

def send(chat_id,text):
    requests.post(API+'/sendMessage',json={'chat_id':chat_id,'text':text},timeout=30)

def send_video(chat_id,path):
    with open(path,'rb') as f:
        requests.post(API+'/sendVideo',data={'chat_id':chat_id,'supports_streaming':True},files={'video':f},timeout=180)

def main():
    if not TOKEN: raise SystemExit('TELEGRAM_BOT_TOKEN is required')
    global OFFSET
    while True:
        try:
            r=requests.get(API+'/getUpdates',params={'timeout':25,'offset':OFFSET},timeout=35).json()
            for u in r.get('result',[]):
                OFFSET=u['update_id']+1
                m=u.get('message',{}); chat=m.get('chat',{}).get('id'); text=(m.get('text') or '').strip()
                if not chat or not text: continue
                if text in ('/start','/help'):
                    send(chat,'🎬 ViralFlow gratuit\n\nEnvoie une idée de vidéo. Je crée le script, les médias, la voix, les mouvements et les captions puis je renvoie le MP4.\n\nExemple :\nL’homme qui a survécu à deux bombes nucléaires')
                    continue
                send(chat,'⏳ Je construis ta vidéo. Le mode gratuit utilise des outils locaux et des médias sans clé payante.')
                try:
                    meta=build(text)
                    send_video(chat,meta['video'])
                except Exception as e:
                    send(chat,'❌ Erreur pendant la génération : '+str(e)[-800:])
        except Exception:
            time.sleep(5)

if __name__=='__main__': main()
