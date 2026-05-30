"""
KrakenFiles Leech Bot (v2 - No Auth Required)
===============================================
Works on ANY krakenfiles.com link - not just your own files.
Uses public scraping + public download token endpoint.

Commands:
  /start        - Welcome message
  /leech <url>  - Download & send file
  /info <url>   - File info only
  /help         - Help
"""

import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ── Config ─────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
MAX_FILE_SIZE_MB = 50
CHUNK_SIZE       = 512 * 1024  # 512 KB

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Matches: https://krakenfiles.com/view/HASH/file.html
KRAKEN_PATTERN = re.compile(
    r"https?://krakenfiles\.com/(?:view|file)/([a-zA-Z0-9_-]+)(?:/file\.html)?"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── Helpers ─────────────────────────────────────────────────────────────────

def extract_hash(url: str) -> str | None:
    match = KRAKEN_PATTERN.search(url.strip())
    return match.group(1) if match else None


def scrape_file_info(file_hash: str) -> dict:
    """
    Scrape file info from the krakenfiles view page.
    Extracts: filename, size, server_filename (used for download).
    """
    try:
        url = f"https://krakenfiles.com/view/{file_hash}/file.html"
        r = requests.get(url, headers=HEADERS, timeout=20)

        if r.status_code == 404:
            return {"ok": False, "error": "❌ File not found. It may have been deleted."}
        if r.status_code != 200:
            return {"ok": False, "error": f"❌ HTTP {r.status_code} from KrakenFiles."}

        soup = BeautifulSoup(r.text, "html.parser")

        # Filename — in <h4> or <title> or meta
        filename = None
        h4 = soup.find("h4", {"class": re.compile("title|name|file", re.I)})
        if h4:
            filename = h4.get_text(strip=True)
        if not filename:
            title = soup.find("title")
            if title:
                # Title usually: "Download filename - KrakenFiles"
                filename = title.get_text(strip=True).split(" - ")[0].replace("Download ", "").strip()
        if not filename:
            filename = f"{file_hash}.file"

        # Size — look for text like "26.5 MB"
        size_mb = 0
        size_text = ""
        for tag in soup.find_all(string=re.compile(r"\d+\.?\d*\s*(MB|GB|KB)", re.I)):
            size_text = tag.strip()
            match = re.search(r"([\d.]+)\s*(MB|GB|KB)", size_text, re.I)
            if match:
                val, unit = float(match.group(1)), match.group(2).upper()
                if unit == "KB": size_mb = round(val / 1024, 2)
                elif unit == "MB": size_mb = round(val, 2)
                elif unit == "GB": size_mb = round(val * 1024, 2)
                break

        # Server filename — hidden input used for download token
        server_filename = None
        inp = soup.find("input", {"id": re.compile("server.?file.?name|sname", re.I)})
        if inp:
            server_filename = inp.get("value")

        # Also grab any hidden form fields for token request
        form_data = {}
        form = soup.find("form", {"id": re.compile("download|dl", re.I)})
        if form:
            for inp in form.find_all("input", {"type": "hidden"}):
                if inp.get("name") and inp.get("value"):
                    form_data[inp["name"]] = inp["value"]

        return {
            "ok": True,
            "hash": file_hash,
            "filename": filename,
            "size_mb": size_mb,
            "server_filename": server_filename,
            "form_data": form_data,
            "page_url": url,
        }

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "❌ Request timed out."}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "❌ Cannot connect to krakenfiles.com."}
    except Exception as e:
        return {"ok": False, "error": f"❌ Scrape error: {e}"}


def get_download_url(info: dict) -> dict:
    """
    POST to the public token endpoint to get direct download URL.
    KrakenFiles public endpoint: POST /api/file/{hash}/download-token
    No auth required for public files.
    """
    file_hash = info["hash"]

    try:
        # Method 1: Public API token (no auth needed for public files)
        api_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Content-Type": "application/json",
            "Referer": f"https://krakenfiles.com/view/{file_hash}/file.html",
            "Origin": "https://krakenfiles.com",
        }

        r = requests.post(
            f"https://krakenfiles.com/api/file/{file_hash}/download-token",
            headers=api_headers,
            json={},
            timeout=20,
        )

        logger.info(f"Token API response: {r.status_code} — {r.text[:200]}")

        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "ok":
                token = data["data"].get("token")
                if token:
                    dl_url = f"https://krakenfiles.com/download/{file_hash}?token={token}"
                    return {"ok": True, "download_url": dl_url}

        # Method 2: Try form-based download (older fallback)
        if info.get("form_data"):
            form_headers = {
                **HEADERS,
                "Referer": info["page_url"],
                "Origin": "https://krakenfiles.com",
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
            }
            r2 = requests.post(
                f"https://krakenfiles.com/download/{file_hash}",
                headers=form_headers,
                data=info["form_data"],
                timeout=20,
            )
            logger.info(f"Form download response: {r2.status_code} — {r2.text[:200]}")

            if r2.status_code == 200:
                try:
                    d2 = r2.json()
                    url = d2.get("url") or d2.get("download_url") or d2.get("data", {}).get("url")
                    if url:
                        return {"ok": True, "download_url": url}
                except Exception:
                    pass

        return {"ok": False, "error": f"❌ Could not get download token. API said: {r.text[:100]}"}

    except Exception as e:
        return {"ok": False, "error": f"❌ Token error: {e}"}


def stream_download(download_url: str, dest_path: str, progress_cb=None) -> dict:
    """Stream download file to disk."""
    try:
        r = requests.get(
            download_url,
            headers=HEADERS,
            stream=True,
            timeout=120,
            allow_redirects=True,
        )
        if r.status_code != 200:
            return {"ok": False, "error": f"❌ Download failed: HTTP {r.status_code}"}

        # Try to get real filename from Content-Disposition
        real_filename = None
        cd = r.headers.get("Content-Disposition", "")
        m = re.search(r'filename[^;=\n]*=(["\']?)([^\n;"\']+)\1', cd)
        if m:
            real_filename = m.group(2).strip()

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

        return {"ok": True, "size_bytes": downloaded, "real_filename": real_filename}

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "❌ Download timed out."}
    except Exception as e:
        return {"ok": False, "error": f"❌ Download error: {e}"}


# ── Telegram Handlers ────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🐙 *KrakenFiles Leech Bot*\n\n"
        "Send me *any* KrakenFiles link — I'll download and send the file to Telegram!\n\n"
        "*Commands:*\n"
        "`/leech <url>` — Download & send file\n"
        "`/info <url>` — File info only\n"
        "`/help` — Show this message\n\n"
        "*Example:*\n"
        "`/leech https://krakenfiles.com/view/Ir6jgunBI7/file.html`\n\n"
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
        await update.message.reply_text("❌ Invalid KrakenFiles URL.")
        return

    msg = await update.message.reply_text("🔍 Fetching file info...")
    info = scrape_file_info(file_hash)

    if not info["ok"]:
        await msg.edit_text(info["error"])
        return

    text = (
        f"📄 *File Info*\n\n"
        f"📝 *Name:* `{info['filename']}`\n"
        f"📦 *Size:* `{info['size_mb']} MB`\n"
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
        await update.message.reply_text("❌ Invalid KrakenFiles URL.")
        return

    # Step 1: Scrape page info
    msg = await update.message.reply_text("🔍 Scanning KrakenFiles page...")
    info = scrape_file_info(file_hash)
    if not info["ok"]:
        await msg.edit_text(info["error"])
        return

    # Step 2: Size check
    if info["size_mb"] > MAX_FILE_SIZE_MB:
        await msg.edit_text(
            f"❌ *File too large!*\n"
            f"📦 Size: `{info['size_mb']} MB` (limit: {MAX_FILE_SIZE_MB} MB)\n\n"
            f"Direct link:\n`https://krakenfiles.com/view/{file_hash}/file.html`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await msg.edit_text(
        f"✅ *Found:* `{info['filename']}`\n"
        f"📦 Size: `{info['size_mb']} MB`\n"
        f"⏳ Getting download link...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Step 3: Get download URL
    token_result = get_download_url(info)
    if not token_result["ok"]:
        await msg.edit_text(token_result["error"])
        return

    download_url = token_result["download_url"]
    await msg.edit_text(
        f"⬇️ Downloading `{info['filename']}`...\n"
        f"📦 `{info['size_mb']} MB` — Please wait ⏳",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Step 4: Stream download
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

    result = stream_download(download_url, tmp_path, on_progress)
    if not result["ok"]:
        await msg.edit_text(result["error"])
        return

    # Use real filename from server if available
    final_filename = result.get("real_filename") or info["filename"]
    size_mb = round(result["size_bytes"] / 1024 / 1024, 2)

    # Step 5: Upload to Telegram
    await msg.edit_text(f"📤 Uploading `{final_filename}` to Telegram...")

    try:
        with open(tmp_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=final_filename,
                caption=(
                    f"✅ *{final_filename}*\n"
                    f"📦 `{size_mb} MB`\n"
                    f"🐙 Leeched from KrakenFiles"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        await msg.delete()
        logger.info(f"✅ Leeched: {final_filename} ({size_mb} MB)")

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        await msg.edit_text(
            f"❌ Telegram upload failed: `{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-detect KrakenFiles URLs in plain messages."""
    text = update.message.text or ""
    match = KRAKEN_PATTERN.search(text)
    if match:
        context.args = [match.group(0)]
        await cmd_leech(update, context)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not set! Add to Heroku Config Vars.")
        return

    logger.info("🐙 KrakenFiles Leech Bot v2 starting...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("info",  cmd_info))
    app.add_handler(CommandHandler("leech", cmd_leech))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    logger.info("✅ Bot is running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
