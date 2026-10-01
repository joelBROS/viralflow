# ViralFlow V12.1 — Free-First TikTok Automation

Objectif : **0 FCFA** pour le pipeline de base.

## Ce qui fonctionne sans clé payante

**Idée → script local → segments → médias Wikimedia Commons → voix eSpeak → zoom/mouvements → captions mot par mot → MP4 vertical 1080×1920 → Telegram (optionnel).**

Telegram Bot API est gratuit ; un bot est créé avec @BotFather et son token doit rester secret. Voir la documentation officielle Telegram. 

## Installation

Prérequis : Python 3.10+, FFmpeg, `pip install -r requirements.txt`.

```bash
cp .env.example .env
python -m app.cli --topic "L'homme qui a survécu à deux bombes nucléaires"
```

Le MP4 apparaît dans `output/`.

## Bot Telegram sans n8n payant

Ajoute `TELEGRAM_BOT_TOKEN` dans `.env`, puis :

```bash
python -m app.telegram_bot
```

Le bot reçoit une idée, lance ViralFlow et renvoie le MP4.

## Améliorations facultatives, toujours gratuites

- Piper local : meilleure voix, sans API payante.
- Ollama local : génération de scripts plus riche, sans API cloud.
- Pexels : optionnel, uniquement si tu possèdes déjà une clé ; le pipeline n'en dépend pas.

## Important

Wikimedia Commons est utilisé comme source média sans clé. Il faut respecter la licence de chaque média récupéré ; `work/media_sources.json` conserve les sources utilisées pour chaque rendu.


## Durée des vidéos
La génération standard vise **60 à 90 secondes**. Le script est généré avec suffisamment de narration, puis la timeline visuelle et les sous-titres sont automatiquement alignés sur la durée de la voix.

En mode gratuit, ViralFlow utilise une image Wikimedia pertinente réutilisée avec différents cadrages pour garder la génération rapide et sans API payante obligatoire. Pexels reste optionnel si une clé est fournie.
