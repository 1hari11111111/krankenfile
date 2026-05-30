# 🐙 KrakenFiles Leech Bot — Heroku Deploy Guide

## Files in this zip
```
bot.py            ← main bot code
requirements.txt  ← Python dependencies
Procfile          ← tells Heroku to run as worker
runtime.txt       ← Python version
README.md         ← this file
```

---

## ✅ Step-by-Step Deploy

### 1. Install Heroku CLI
Download from: https://devcenter.heroku.com/articles/heroku-cli

### 2. Login & Create App
```bash
heroku login
heroku create kraken-leech-bot
```

### 3. Set Config Vars (your secrets)
```bash
heroku config:set BOT_TOKEN=8938744418:AAER35y5SCJvo
heroku config:set KRAKEN_API_KEY=OThkNDdjZTViMDE5MmI4YQqJEz6
```
> ⚠️ Regenerate your KrakenFiles API key after deploy for security!

### 4. Push Code
```bash
git init
git add .
git commit -m "deploy kraken leech bot"
git push heroku main
```

### 5. Start Worker Dyno
```bash
heroku ps:scale worker=1
```

### 6. Check Logs
```bash
heroku logs --tail
```
Look for: `✅ Bot is running!`

---

## 🤖 Bot Commands

| Command | What it does |
|---------|-------------|
| `/start` | Welcome message |
| `/leech <url>` | Download & send file to Telegram |
| `/info <url>` | Show file name, size, downloads |
| `/help` | Show help |
| Just paste URL | Auto-detects and leeches! |

### Example:
```
/leech https://krakenfiles.com/view/Ir6jgunBI7/file.html
```

---

## ⚠️ Limits

| Limit | Value |
|-------|-------|
| Max file size | 50 MB (Telegram Bot API) |
| Files above limit | Bot sends direct link instead |
| Heroku /tmp storage | ~500 MB (cleared on restart) |

---

## 🔄 Update Bot
```bash
git add .
git commit -m "update"
git push heroku main
```

## 🔁 Restart Bot
```bash
heroku ps:restart
```

## 🔑 Regenerate KrakenFiles API Key (recommended after deploy)
1. Go to krakenfiles.com → your account → API settings
2. Generate new key
3. Run: `heroku config:set KRAKEN_API_KEY=your_new_key`
4. Bot restarts automatically
