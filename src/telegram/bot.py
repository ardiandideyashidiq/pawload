from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from loguru import logger

from telegram.config import Config


def detect_provider(url: str) -> str | None:
    lower = url.lower()
    if "sourceforge.net" in lower or "sf.net" in lower:
        return "sourceforge"
    if "gofile.io" in lower:
        return "gofile"
    if "vikingfile.com" in lower or "vik1ngfile.site" in lower:
        return "vikingfile"
    if "pixeldrain.com" in lower:
        return "pixeldrain"
    return None


async def start_handler(message: types.Message) -> None:
    text = (
        "<b>Welcome to Multi-Cloud Transfer Bot!</b>\n\n"
        "Supported providers:\n"
        "- <b>SourceForge</b> (sf.net)\n"
        "- <b>GoFile</b> (gofile.io)\n"
        "- <b>VikingFile</b> (vikingfile.com)\n"
        "- <b>Pixeldrain</b> (pixeldrain.com)\n\n"
        "<b>Commands:</b>\n"
        "/info &lt;url&gt; - Inspect cloud file metadata\n"
        "/download &lt;url&gt; - Download file to host server\n"
        "/help - Display this guide\n\n"
        "<i>Or send/forward any document directly to upload to GoFile/Pixeldrain!</i>"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


async def info_handler(message: types.Message) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply(
            "Usage: <code>/info &lt;url&gt;</code>", parse_mode=ParseMode.HTML
        )
        return

    url = args[1].strip()
    provider = detect_provider(url)

    if not provider:
        await message.reply(
            "[ERROR] Unsupported URL. Supported: SourceForge, GoFile, VikingFile, Pixeldrain."
        )
        return

    status_msg = await message.reply(f"[INFO] Querying {provider.capitalize()} metadata...")

    try:
        if provider == "pixeldrain":
            from pixeldrain.client import PixeldrainClient
            from pixeldrain.config import format_size

            client = PixeldrainClient()
            info = client.get_info(url)
            text = (
                "<b>[pixeldrain] File</b>\n\n"
                f"<b>Name:</b> {info.name}\n"
                f"<b>Size:</b> {format_size(info.size)}\n"
                f"<b>ID:</b> <code>{info.id}</code>\n"
                f"<b>Downloads:</b> {info.downloads}\n"
                f"<b>Date:</b> {info.date_upload}\n"
            )
            await status_msg.edit_text(text, parse_mode=ParseMode.HTML)

        elif provider == "vikingfile":
            from vikingfile.client import VikingFileClient
            from vikingfile.config import format_size

            client = VikingFileClient()
            info = client.check(url)
            if not info or not info.exist:
                await status_msg.edit_text(
                    "[ERROR] VikingFile: File does not exist or was deleted."
                )
                return
            text = (
                "<b>[vikingfile] Details</b>\n\n"
                f"<b>Name:</b> {info.name}\n"
                f"<b>Size:</b> {format_size(info.size)}\n"
                f"<b>Hash:</b> <code>{info.hash}</code>\n"
                f"<b>URL:</b> {info.url}\n"
            )
            await status_msg.edit_text(text, parse_mode=ParseMode.HTML)

        elif provider == "gofile":
            from gofile.client import GoFileClient
            from gofile.config import format_size

            client = GoFileClient()
            file_info = client.get_file_info(url)
            text = (
                "<b>[gofile] Details</b>\n\n"
                f"<b>Name:</b> {file_info.name}\n"
                f"<b>Size:</b> {format_size(file_info.size)}\n"
                f"<b>ID:</b> <code>{file_info.id}</code>\n"
                f"<b>Direct Link:</b> {file_info.link}\n"
            )
            await status_msg.edit_text(text, parse_mode=ParseMode.HTML)

        elif provider == "sourceforge":
            direct_url, filename, _total_size, md5 = client.resolve_download(url)
            text = (
                "<b>[sourceforge] File</b>\n\n"
                f"<b>Filename:</b> {filename}\n"
                f"<b>Direct URL:</b> {direct_url}\n"
            )
            if md5:
                text += f"<b>MD5:</b> <code>{md5}</code>\n"
            await status_msg.edit_text(text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.exception("Info query failed")
        await status_msg.edit_text(
            f"[ERROR] Error querying {provider}: <code>{e}</code>", parse_mode=ParseMode.HTML
        )


async def document_handler(message: types.Message, bot: Bot) -> None:
    doc = message.document
    if not doc:
        return

    # Telegram bot API limits getFile downloads to 20MB
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.reply(
            "[WARN] File size exceeds Telegram Bot API's 20 MB download limit for standard bot tokens.",
            parse_mode=ParseMode.HTML,
        )
        return

    file_name = doc.file_name or "uploaded_file"
    status_msg = await message.reply(
        f"[INFO] Downloading <b>{file_name}</b> from Telegram...", parse_mode=ParseMode.HTML
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        dest_path = Path(tmpdir) / file_name
        try:
            file_obj = await bot.get_file(doc.file_id)
            if not file_obj.file_path:
                await status_msg.edit_text(
                    "[ERROR] Failed to obtain file path from Telegram."
                )
                return

            await bot.download_file(file_obj.file_path, destination=dest_path)
            await status_msg.edit_text(
                f"[UPLOAD] Uploading <b>{file_name}</b> to GoFile...",
                parse_mode=ParseMode.HTML,
            )

            from gofile.client import GoFileClient

            gf_client = GoFileClient()
            result = gf_client.upload(dest_path)

            success_text = (
                "[OK] <b>Upload Complete!</b>\n\n"
                f"<b>File:</b> {file_name}\n"
                f"<b>Provider:</b> GoFile\n"
                f"<b>Download Link:</b> {result.download_page}\n"
            )
            await status_msg.edit_text(success_text, parse_mode=ParseMode.HTML)

        except Exception as e:
            logger.exception("Document handling error")
            await status_msg.edit_text(
                f"[ERROR] Upload failed: <code>{e}</code>", parse_mode=ParseMode.HTML
            )


def run_bot(bot_token: str | None = None) -> None:
    """Run interactive bot polling daemon."""
    cfg = Config.load()
    token = bot_token or cfg.bot_token
    if not token:
        raise ValueError(
            "Telegram bot token not configured. Set TELEGRAM_BOT_TOKEN or run 'tg config set'."
        )

    bot = Bot(token=token)
    dp = Dispatcher()

    dp.message.register(start_handler, CommandStart())
    dp.message.register(start_handler, Command("help"))
    dp.message.register(info_handler, Command("info"))
    dp.message.register(document_handler, F.document)

    logger.info("Starting Telegram bot polling daemon...")
    asyncio.run(dp.start_polling(bot))
