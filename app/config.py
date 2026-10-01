from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
OUTPUT = ROOT / 'output'
WORK = ROOT / 'work'
MEDIA = WORK / 'media'
ASSETS = ROOT / 'assets'
for p in (OUTPUT, WORK, MEDIA, ASSETS): p.mkdir(parents=True, exist_ok=True)
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
PIPER_MODEL = os.getenv('PIPER_MODEL', '')
