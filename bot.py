"""
KrakenFiles Leech Bot
======================
Telegram bot that leeches files from krakenfiles.com using their official API.

Commands:
  /start        - Welcome message
  /leech <url>  - Download file from KrakenFiles & send to Telegram
  /info <url>   - Get file info without downloading
  /help         - Show help

Author: Built for Heroku deployment
"""

import os
import re
import logging
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ── Config (loaded from Heroku environment variables) ─────────────────────────
BOT_TOKEN     = os.environ.get("BOT_TOKEN", "")
KRAKEN_API_KEY = os.environ.get("KRAKEN_API_KEY", "")

MAX_FILE_SIZE_MB = 50       # Telegram Bot API hard limit
CHUNK_SIZE       = 1024 * 512  # 512 KB stream chunks
REQUEST_TIMEOUT  = 30

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── KrakenFiles URL pattern ───────────────────────────────────────────────────
# Matches: https://krakenfiles.com/view/HASH/file.html
KRAKEN_PATTERN = re.compile(
    r"https?://krakenfiles\.com/(?:view|file)/([a-zA-Z0-9_-]+)(?:/file\.html)?"
)

# ── KrakenFiles API ───────────────────────────────────────────────────────────

BASE_URL = "https://krakenfiles.com/api"
HEADERS  = {
    "AuthToken": KRAKEN_API_KEY,
    "Content-Type": "application/json",
    "User-Agent": "KrakenLeechBot/1.0",
}


def extract_hash(url: str) -> str | None:
    """Extract the file hash from a KrakenFiles URL."""
    match = KRAKEN_PATTERN.search(url.strip())
    return match.group(1) if match else None


def api_get_file_info(file_hash: str) -> dict:
    """
    GET /api/file/{hash}/info
    Returns file metadata: name, size, etc.
    """
    try:
        r = requests.get(
            f"{BASE_URL}/file/{file_hash}/info",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 404:
            return {"ok": False, "error": "❌ File not found. It may have been deleted."}
        if r.status_code == 401:
            return {"ok": False, "error": "❌ Invalid API key. Check KRAKEN_API_KEY config var."}
        if r.status_code != 200:
            return {"ok": False, "error": f"❌ KrakenFiles API error: HTTP {r.status_code}"}

        data = r.json()
        # API returns: {"status": "ok", "data": {"title": ..., "size": ..., ...}}
        if data.get("status") != "ok":
            return {"ok": False, "error": f"❌ API returned: {data.get('message', 'Unknown error')}"}

        info = data["data"]
        size_bytes = int(info.get("size", 0))
        size_mb = round(size_bytes / (1024 * 1024), 2)

        return {
            "ok": True,
            "hash": file_hash,
            "filename": info.get("title", "unknown_file"),
            "size_bytes": size_bytes,
            "size_mb": size_mb,
            "downloads": info.get("downloads", "N/A"),
            "created": info.get("created_at", "N/A"),
        }

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "❌ Request timed out. KrakenFiles may be slow."}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "❌ Cannot connect to krakenfiles.com."}
    except Exception as e:
        return {"ok": False, "error": f"❌ Unexpected error: {e}"}


def api_get_download_token(file_hash: str) -> dict:
    """
    POST /api/file/{hash}/download-token
    Returns a one-time download token.
    """
    try:
        r = requests.post(
            f"{BASE_URL}/file/{file_hash}/download-token",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 401:
            return {"ok": False, "error": "❌ Invalid API key."}
        if r.status_code == 404:
            return {"ok": False, "error": "❌ File not found."}
        if r.status_code != 200:
            return {"ok": False, "error": f"❌ Token request failed: HTTP {r.status_code}"}

        data = r.json()
        if data.get("status") != "ok":
            return {"ok": False, "error": f"❌ {data.get('message', 'Token error')}"}

        token = data["data"].get("token")
        if not token:
            return {"ok": False, "error": "❌ No token in API response."}

        # Direct download URL
        download_url = f"https://krakenfiles.com/download/{file_hash}?token={token}"
        return {"ok": True, "token": token, "download_url": download_url}

    except Exception as e:
        return {"ok": False, "error": f"❌ Token error: {e}"}


def download_file(download_url: str, dest_path: str, progress_cb=None) -> dict:
    """Stream download a file to dest_path."""
    try:
        r = requests.get(
            download_url,
            stream=True,
            timeout=120,
            headers={"User-Agent": "KrakenLeechBot/1.0"},
        )
        if r.status_code != 200:
            return {"ok": False, "error": f"❌ Download failed: HTTP {r.status_code}"}

        total = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        last_pct = 0

        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        pct = int(downloaded / total * 100)
                        if pct - last_pct >= 10:
                            progress_cb(downloaded, total)
                            last_pct = pct

        return {"ok": True, "size_bytes": downloaded}

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "❌ Download timed out."}
    except Exception as e:
        return {"ok": False, "error": f"❌ Download error: {e}"}


# ── Telegram Handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🐙 *KrakenFiles Leech Bot*\n\n"
        "Send me any KrakenFiles link and I'll download and deliver the file straight to Telegram!\n\n"
        "*Commands:*\n"
        "`/leech <url>` — Download & send file\n"
        "`/info <url>` — File info without downloading\n"
        "`/help` — Show this message\n\n"
        "*Supported URL format:*\n"
        "`https://krakenfiles.com/view/HASH/file.html`\n\n"
        f"⚠️ Max file size: *{MAX_FILE_SIZE_MB} MB*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/info https://krakenfiles.com/view/HASH/file.html`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    url = context.args[0]
    file_hash = extract_hash(url)
    if not file_hash:
        await update.message.reply_text("❌ Invalid KrakenFiles URL.", parse_mode=ParseMode.MARKDOWN)
        return

    msg = await update.message.reply_text("🔍 Fetching file info...")
    info = api_get_file_info(file_hash)

    if not info["ok"]:
        await msg.edit_text(info["error"])
        return

    text = (
        f"📄 *File Info*\n\n"
        f"📝 *Name:* `{info['filename']}`\n"
        f"📦 *Size:* `{info['size_mb']} MB`\n"
        f"⬇️ *Downloads:* `{info['downloads']}`\n"
        f"📅 *Uploaded:* `{info['created']}`\n"
        f"🔗 *Hash:* `{info['hash']}`"
    )
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_leech(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/leech https://krakenfiles.com/view/HASH/file.html`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    url = context.args[0]
    file_hash = extract_hash(url)
    if not file_hash:
        await update.message.reply_text("❌ Invalid KrakenFiles URL.", parse_mode=ParseMode.MARKDOWN)
        return

    # Step 1: File info
    msg = await update.message.reply_text("🔍 Checking file on KrakenFiles...")
    info = api_get_file_info(file_hash)
    if not info["ok"]:
        await msg.edit_text(info["error"])
        return

    # Step 2: Size check
    if info["size_mb"] > MAX_FILE_SIZE_MB:
        await msg.edit_text(
            f"❌ *File too large!*\n\n"
            f"📦 Size: `{info['size_mb']} MB`\n"
            f"🚫 Limit: `{MAX_FILE_SIZE_MB} MB`\n\n"
            f"You can download it directly:\n"
            f"`https://krakenfiles.com/view/{file_hash}/file.html`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await msg.edit_text(
        f"🎯 *Found:* `{info['filename']}`\n"
        f"📦 Size: `{info['size_mb']} MB`\n\n"
        f"⏳ Getting download token...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Step 3: Get download token
    token_result = api_get_download_token(file_hash)
    if not token_result["ok"]:
        await msg.edit_text(token_result["error"])
        return

    download_url = token_result["download_url"]
    await msg.edit_text(
        f"⬇️ Downloading `{info['filename']}`\n"
        f"📦 `{info['size_mb']} MB` — Please wait...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Step 4: Download file
    tmp_path = f"/tmp/{info['filename']}"

    def on_progress(downloaded, total):
        pct = int(downloaded / total * 100)
        dl_mb = round(downloaded / 1024 / 1024, 1)
        tot_mb = round(total / 1024 / 1024, 1)
        context.application.create_task(
            msg.edit_text(
                f"⬇️ Downloading `{info['filename']}`\n"
                f"📊 `{pct}%` — `{dl_mb}` / `{tot_mb}` MB",
                parse_mode=ParseMode.MARKDOWN,
            )
        )

    result = download_file(download_url, tmp_path, on_progress)
    if not result["ok"]:
        await msg.edit_text(result["error"])
        return

    # Step 5: Upload to Telegram
    await msg.edit_text(
        f"📤 Uploading `{info['filename']}` to Telegram...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        with open(tmp_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=info["filename"],
                caption=(
                    f"✅ *{info['filename']}*\n"
                    f"📦 `{info['size_mb']} MB`\n"
                    f"🐙 Leeched from KrakenFiles"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        await msg.delete()
        logger.info(f"Successfully leeched: {info['filename']} ({info['size_mb']} MB)")

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        await msg.edit_text(
            f"❌ Upload to Telegram failed: `{e}`\n\n"
            f"Direct link:\n`{download_url}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            logger.info(f"Cleaned up temp file: {tmp_path}")


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-detect KrakenFiles URLs sent as plain messages."""
    text = update.message.text or ""
    match = KRAKEN_PATTERN.search(text)
    if match:
        context.args = [match.group(0)]
        await cmd_leech(update, context)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Add it to Heroku Config Vars.")
        return
    if not KRAKEN_API_KEY:
        logger.error("KRAKEN_API_KEY not set! Add it to Heroku Config Vars.")
        return

    logger.info("🐙 KrakenFiles Leech Bot starting...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("info",  cmd_info))
    app.add_handler(CommandHandler("leech", cmd_leech))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
