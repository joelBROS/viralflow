# ViralFlow V12 — deployment gratuite

Cette version supprime n8n. Architecture :

**Telegram → Render Free → ViralFlow Python → MP4 → Telegram**

Le service utilise uniquement des composants gratuits du projet : Wikimedia Commons, eSpeak et FFmpeg. Aucune API payante n'est nécessaire.

## Déploiement

1. Importer ce dossier dans un dépôt GitHub.
2. Sur Render, créer un **Web Service** depuis ce dépôt et choisir le plan **Free**.
3. Les variables d'environnement à définir sont :
   - `TELEGRAM_BOT_TOKEN` : token du bot fourni par BotFather.
   - `TELEGRAM_WEBHOOK_SECRET` : une chaîne secrète quelconque, par exemple `vf-telegram-2026`.
4. Après déploiement, noter l'URL HTTPS Render, par exemple `https://viralflow-free.onrender.com`.
5. Ouvrir dans un navigateur :
   `https://api.telegram.org/bot<TON_TOKEN>/setWebhook?url=https://TON-URL.onrender.com/telegram&secret_token=vf-telegram-2026`
6. Envoyer une idée au bot Telegram.

Le service peut s'endormir après une période d'inactivité sur le plan gratuit. Le webhook Telegram permet toutefois à une nouvelle requête de réveiller le service.
