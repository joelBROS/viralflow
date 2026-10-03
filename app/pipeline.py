from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
import wave
from pathlib import Path
from typing import Dict, List

import requests
from PIL import Image, ImageDraw, ImageFont

from .config import ROOT, OUTPUT, WORK, MEDIA, ASSETS, PEXELS_API_KEY, PIPER_MODEL

# Render Free: keep the video deliberately light.
FPS = 24
W, H = 720, 1280
TARGET_MIN = 60.0
TARGET_MAX = 90.0


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-4000:])
    return p.stdout


def ffprobe_duration(path: Path) -> float:
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path)
    ])
    return float(out.strip())


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def split_segments(script: str) -> List[Dict]:
    chunks = [x.strip() for x in re.split(r"(?<=[.!?])\s+", script.strip()) if x.strip()]
    if len(chunks) < 3:
        chunks = [x.strip() for x in script.split("\n") if x.strip()]
    return [
        {"id": i + 1, "text": x, "keywords": keywords(x)}
        for i, x in enumerate(chunks)
    ]


def keywords(text):
    words = re.findall(r"[A-Za-zÀ-ÿ0-9']+", text.lower())
    stop = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on",
        "de", "la", "le", "les", "un", "une", "des", "et", "en",
        "pour", "que", "qui", "est", "sont", "du", "au", "aux",
    }
    return " ".join([w for w in words if w not in stop][:5]) or "history cinematic"


def generate_story(topic: str) -> Dict:
    t = topic.strip() or "L’homme qui a survécu à deux bombes nucléaires"
    script = (
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
    return {
        "title": t,
        "hook": "Et si survivre à une catastrophe n’était que le début ?",
        "script": script,
    }


def make_placeholder(path: Path, text: str, index: int = 1):
    im = Image.new("RGB", (W, H), (12 + index * 5, 12 + index * 4, 18 + index * 3))
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    d.text((45, 100), "VIRALFLOW", font=small, fill="white")
    lines = textwrap.wrap(text, width=22)
    y = 500
    for line in lines:
        box = d.textbbox((0, 0), line, font=font)
        x = (W - (box[2] - box[0])) / 2
        d.text((x, y), line, font=font, fill="white", stroke_width=2, stroke_fill="black")
        y += 65
    im.save(path, quality=85)


def fetch_wikimedia(query: str, out: Path, source_log: list) -> bool:
    try:
        api = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query", "generator": "search", "gsrsearch": query,
            "gsrnamespace": 6, "gsrlimit": 3, "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": W,
            "format": "json", "formatversion": 2,
        }
        r = requests.get(
            api, params=params, timeout=8,
            headers={"User-Agent": "ViralFlow/12 (free media client)"},
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", [])
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if not url:
                continue
            clean = url.lower().split("?")[0]
            if not clean.endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            rr = requests.get(url, timeout=10, headers={"User-Agent": "ViralFlow/12"})
            rr.raise_for_status()
            out.write_bytes(rr.content)
            source_log.append({
                "provider": "Wikimedia Commons",
                "title": page.get("title", ""),
                "url": url,
            })
            return True
    except Exception:
        return False
    return False


def fetch_pexels(query: str, out: Path):
    if not PEXELS_API_KEY:
        return False
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        r = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 3},
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        for v in r.json().get("videos", []):
            files = sorted(v.get("video_files", []), key=lambda f: (f.get("width") or 0), reverse=True)
            for f in files:
                link = f.get("link", "")
                if not link:
                    continue
                rr = requests.get(link, timeout=30)
                rr.raise_for_status()
                out.write_bytes(rr.content)
                return True
    except Exception:
        return False
    return False


def acquire_media(segments):
    """Download only one visual asset. Reusing it avoids many FFmpeg inputs/RAM spikes."""
    source_log = []
    seed = segments[0]["keywords"] if segments else "history cinematic"
    shared = MEDIA / "shared_story.jpg"
    if shared.exists():
        shared.unlink()

    ok = fetch_wikimedia(seed, shared, source_log)
    if not ok:
        make_placeholder(shared, seed, 1)

    # Normalize the downloaded image once so FFmpeg gets a small predictable JPEG.
    try:
        im = Image.open(shared).convert("RGB")
        im.thumbnail((W, H), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (W, H), "black")
        x = (W - im.width) // 2
        y = (H - im.height) // 2
        canvas.paste(im, (x, y))
        canvas.save(shared, "JPEG", quality=82, optimize=True)
    except Exception:
        make_placeholder(shared, seed, 1)

    (WORK / "media_sources.json").write_text(
        json.dumps(source_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return shared


def create_tts(text: str, out: Path):
    if PIPER_MODEL and shutil.which("piper"):
        proc = subprocess.run(
            ["piper", "--model", PIPER_MODEL, "--output_file", str(out)],
            input=text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode == 0 and out.exists():
            return

    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if exe:
        proc = subprocess.run(
            [exe, "-v", "fr", "-s", "155", "-w", str(out), text],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode == 0 and out.exists():
            return

    duration = max(1.5, min(8.0, len(text) / 12))
    samples = int(22050 * duration)
    with wave.open(str(out), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\0\0" * samples)


def make_srt(segments, total):
    words = []
    for s in segments:
        words.extend(re.findall(r"\S+", s["text"]))
    per = total / max(len(words), 1)

    def ts(x):
        ms = int(x * 1000)
        h = ms // 3600000
        ms %= 3600000
        m = ms // 60000
        ms %= 60000
        sec = ms // 1000
        ms %= 1000
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    lines = []
    for i, word in enumerate(words):
        a = i * per
        b = (i + 1) * per
        lines += [str(i + 1), f"{ts(a)} --> {ts(b)}", word, ""]
    p = WORK / "captions.srt"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def render(segments, media: Path, voice: Path, out: Path):
    """Low-RAM renderer: one image input + one audio input + one video filter."""
    voice_duration = ffprobe_duration(voice)
    target = max(TARGET_MIN, min(TARGET_MAX, voice_duration))
    srt = make_srt(segments, target)

    # Escape the subtitle path for FFmpeg's subtitles filter.
    srt_filter = str(srt).replace("\\", "/").replace(":", r"\\:").replace("'", r"\\'")
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,subtitles='{srt_filter}'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-threads", "1",
        "-loop", "1", "-framerate", str(FPS), "-i", str(media),
        "-i", str(voice),
        "-vf", vf,
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", f"{target:.2f}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "96k",
        "-af", "apad",
        "-movflags", "+faststart",
        str(out),
    ]
    run(cmd)
    return target


def build(topic):
    story = generate_story(topic)
    segments = split_segments(story["script"])
    media = acquire_media(segments)

    voice = WORK / "voice.wav"
    create_tts(story["script"], voice)

    out = OUTPUT / f"{slug(story['title']) or 'viralflow-video'}.mp4"
    total = render(segments, media, voice, out)

    meta = {
        "title": story["title"],
        "hook": story["hook"],
        "script": story["script"],
        "segments": segments,
        "duration": total,
        "video": str(out),
        "free_mode": not bool(PEXELS_API_KEY),
        "media_sources": str(WORK / "media_sources.json"),
    }
    (OUTPUT / f"{out.stem}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Telegram upload is intentionally handled only by server.py.
    return meta
