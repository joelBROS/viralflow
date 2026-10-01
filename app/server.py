from __future__ import annotations
import os
import threading
from fastapi import FastAPI, Request, HTTPException
from .pipeline import build

app = FastAPI(title='ViralFlow V12')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET', '').strip()
API = f'https://api.telegram.org/bot{TOKEN}' if TOKEN else ''


def tg(method: str, payload: dict):
    import requests
    r = requests.post(f'{API}/{method}', json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def send_text(chat_id, text):
    tg('sendMessage', {'chat_id': chat_id, 'text': text})


def send_video(chat_id, path):
    import requests
    with open(path, 'rb') as f:
        r = requests.post(
            f'{API}/sendVideo',
            data={'chat_id': chat_id, 'supports_streaming': True},
            files={'video': f}, timeout=180,
        )
    r.raise_for_status()


def process(chat_id: int, topic: str):
    try:
        send_text(chat_id, '⏳ Je construis ta vidéo ViralFlow...\n\nScript → médias → voix → sous-titres → MP4.')
        meta = build(topic)
        send_video(chat_id, meta['video'])
    except Exception as e:
        try:
            send_text(chat_id, '❌ Erreur : ' + str(e)[-1000:])
        except Exception:
            pass


@app.get('/')
def health():
    return {'ok': True, 'service': 'ViralFlow V12', 'free_mode': True}


@app.get('/health')
def health2():
    return {'ok': True}


@app.post('/telegram')
async def telegram(request: Request):
    if not TOKEN:
        raise HTTPException(503, 'TELEGRAM_BOT_TOKEN is not configured')
    if SECRET and request.headers.get('X-Telegram-Bot-Api-Secret-Token') != SECRET:
        raise HTTPException(403, 'invalid secret')
    update = await request.json()
    message = update.get('message') or {}
    chat = (message.get('chat') or {}).get('id')
    text = (message.get('text') or '').strip()
    if not chat or not text:
        return {'ok': True}
    if text in ('/start', '/help'):
        send_text(chat, '🎬 ViralFlow gratuit\n\nEnvoie-moi simplement une idée de vidéo. Je génère le MP4 vertical et je te le renvoie ici.\n\nExemple : L’homme qui a survécu à deux bombes nucléaires')
        return {'ok': True}
    threading.Thread(target=process, args=(chat, text), daemon=True).start()
    return {'ok': True}
