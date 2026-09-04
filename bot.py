"""
╔══════════════════════════════════════════╗
║        JORA MESSENGER BOT v2.0           ║
║  Max Speed · Minimalist · File ID Tool   ║
╚══════════════════════════════════════════╝

Kerakli kutubxonalar:
  pip install aiogram aiohttp

Ishga tushirish:
  python jora_bot.py
"""

import os
import sys
import asyncio
import re
import subprocess
from aiogram.client.default import DefaultBotProperties

# ─── Auto-install ────────────────────────────────────────────────
def _install(pkg: str):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", pkg, "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

for mod, pkg in [("aiogram", "aiogram"), ("aiohttp", "aiohttp")]:
    try:
        __import__(mod)
    except ImportError:
        print(f"Installing {pkg}...")
        _install(pkg)

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp

# ─────────────────────────────────────────────────────────────────
#  ⚙️  SOZLAMALAR  —  faqat shu qismni o'zgartiring
# ─────────────────────────────────────────────────────────────────
BOT_TOKEN        = "8506680790:AAHCBLzg41yR7XUx_r8jBrcPt9OY7c9TyYs"
SUPABASE_URL     = "https://dswpheeugtozosdaguym.supabase.co/rest/v1/versions"
SUPABASE_KEY     = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRzd3BoZWV1Z3Rvem9zZGFndXltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgzMDU4MzAsImV4cCI6MjA5Mzg4MTgzMH0"
    ".NvIEl0_2T54QLqr9uvHESd-1XIdT-s8FmS8R60IqcJ0"
)

# Botni boshqaruvchi adminlar (file_id olish buyrug'ini faqat shular ishlata oladi)
ADMIN_IDS: set[int] = {6302140863}   # ← o'z Telegram ID-ingizni yozing
# ─────────────────────────────────────────────────────────────────

# ─── Iconlar (Unicode, emoji emas) ───────────────────────────────
ICO = {
    "app":     "◈",   # ilovaning belgisi
    "version": "◉",   # versiya
    "date":    "◷",   # sana
    "company": "◆",   # kompaniya
    "author":  "◈",   # muallif
    "link":    "◎",   # havola
    "web":     "◉",   # web
    "back":    "←",   # orqaga
    "next":    "→",   # keyingi
    "prev":    "←",   # oldingi
    "dl":      "↓",   # yuklab olish
    "id":      "◇",   # file id
    "ok":      "◆",   # tayyor
    "err":     "✕",   # xato
    "wait":    "◌",   # kutish
    "diamond": "◈",   # versiya tugmasi
    "page":    "▸",   # sahifa
}

# ─── HTTP headers ────────────────────────────────────────────────
HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

# ─── Global state (chat_id → {msg_id, state}) ────────────────────
STATE: dict[int, dict] = {}

# ─── Bot & Dispatcher ────────────────────────────────────────────


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher()


# ═══════════════════════════════════════════════════════════════
#  DATABASE LAYER  —  aiohttp bilan, connection reuse uchun
# ═══════════════════════════════════════════════════════════════
_session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(
            limit=20,
            ttl_dns_cache=300,
            ssl=False,           # Supabase TLS ishonchli, tekshirishni skip qilamiz → tezroq
            keepalive_timeout=60,
        )
        _session = aiohttp.ClientSession(
            connector=connector,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=8),
        )
    return _session


async def db_versions(active_only: bool = True) -> list[dict]:
    """Barcha (yoki faqat aktiv) versiyalarni olish."""
    params = {
        "select": "version,created_at,company,author,install,url,tmf_id,active",
        "order":  "version.desc",
    }
    if active_only:
        params["active"] = "eq.true"

    try:
        session = await get_session()
        async with session.get(SUPABASE_URL, params=params) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"[DB] fetch_versions error: {e}")
    return []


async def db_version(ver: str) -> dict | None:
    """Bitta versiyani olish."""
    params = {
        "select": "*",
        "version": f"eq.{ver}",
    }
    try:
        session = await get_session()
        async with session.get(SUPABASE_URL, params=params) as r:
            if r.status == 200:
                data = await r.json()
                return data[0] if data else None
    except Exception as e:
        print(f"[DB] fetch_version error: {e}")
    return None


# ═══════════════════════════════════════════════════════════════
#  KEYBOARD FACTORY
# ═══════════════════════════════════════════════════════════════
PAGE_SIZE = 8

def kb_versions(versions: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    """Versiyalar ro'yxati klaviaturasi."""
    builder = InlineKeyboardBuilder()
    chunk   = versions[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    for v in chunk:
        ver = v["version"]
        builder.button(
            text=f"  {ICO['diamond']}  v{ver}  ",
            callback_data=f"ver:{ver}",
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text=f"{ICO['prev']}  Oldingi",
            callback_data=f"page:{page - 1}",
        ))
    if (page + 1) * PAGE_SIZE < len(versions):
        nav.append(InlineKeyboardButton(
            text=f"Keyingi  {ICO['next']}",
            callback_data=f"page:{page + 1}",
        ))
    if nav:
        builder.row(*nav)

    total_pages = (len(versions) - 1) // PAGE_SIZE + 1
    if total_pages > 1:
        builder.row(InlineKeyboardButton(
            text=f"  {ICO['page']}  {page + 1} / {total_pages}  ",
            callback_data="noop",
        ))

    builder.adjust(1)
    return builder.as_markup()


def kb_back() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"  {ICO['back']}  Orqaga  ", callback_data="menu")
    return builder.as_markup()


def kb_version_detail(ver: str, install_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"  {ICO['dl']}  Yuklab olish  ",
        url=install_url or "https://t.me",
    )
    builder.button(text=f"  {ICO['back']}  Orqaga  ", callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


# ═══════════════════════════════════════════════════════════════
#  MESSAGE TEMPLATES
# ═══════════════════════════════════════════════════════════════
MENU_TEXT = (
    "<b>◈ Jora Messenger</b>\n"
    "<code>━━━━━━━━━━━━━━━━━━━━</code>\n"
    "Versiyani tanlang:"
)

WAIT_TEXT = f"<i>{ICO['wait']}  Yuklanmoqda...</i>"


def fmt_version(d: dict) -> str:
    date    = str(d.get("created_at", ""))[:10] or "—"
    company = d.get("company", "JORA NET") or "JORA NET"
    author  = d.get("author", "Jora Developer") or "Jora Developer"
    install = d.get("install", "#") or "#"
    url     = d.get("url", "#") or "#"
    ver     = d.get("version", "")

    return (
        f"<b>◈ Jora Messenger</b>  <code>v{ver}</code>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n\n"
        f"{ICO['date']}  <b>Chiqarilgan:</b>  <code>{date}</code>\n"
        f"{ICO['company']}  <b>Kompaniya:</b>  <code>{company}</code>\n"
        f"{ICO['author']}  <b>Muallif:</b>  <i>{author}</i>\n\n"
        f"{ICO['link']}  <a href='{install}'>APK manzili</a>    "
        f"{ICO['web']}  <a href='{url}'>Veb-sayt</a>"
    )


# ═══════════════════════════════════════════════════════════════
#  STATE HELPERS
# ═══════════════════════════════════════════════════════════════
async def _delete(chat_id: int, msg_id: int) -> None:
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


async def send_menu(chat_id: int, delete_id: int | None = None) -> None:
    """Eski xabarni o'chir, yangi menyuni yubor."""
    old_id = STATE.get(chat_id, {}).get("msg_id")

    if delete_id:
        await _delete(chat_id, delete_id)
    if old_id and old_id != delete_id:
        await _delete(chat_id, old_id)

    versions = await db_versions()
    if not versions:
        msg = await bot.send_message(
            chat_id,
            f"<i>{ICO['err']}  Faol versiyalar topilmadi.</i>",
        )
    else:
        msg = await bot.send_message(
            chat_id,
            MENU_TEXT,
            reply_markup=kb_versions(versions),
        )

    STATE[chat_id] = {"msg_id": msg.message_id, "state": "menu"}


async def show_version(chat_id: int, ver: str) -> None:
    """Versiya faylini yubor."""
    cur = STATE.get(chat_id, {})

    # "Yuklanmoqda" holati
    if cur.get("msg_id"):
        try:
            await bot.edit_message_text(WAIT_TEXT, chat_id, cur["msg_id"])
        except Exception:
            pass
    else:
        msg = await bot.send_message(chat_id, WAIT_TEXT)
        STATE[chat_id] = {"msg_id": msg.message_id, "state": "loading"}

    STATE[chat_id]["state"] = "loading"

    data = await db_version(ver)

    if not data or not data.get("tmf_id"):
        try:
            await bot.edit_message_text(
                f"<b>{ICO['err']}  Versiya topilmadi.</b>",
                chat_id,
                STATE[chat_id]["msg_id"],
                reply_markup=kb_back(),
            )
        except Exception:
            pass
        STATE[chat_id]["state"] = "menu"
        return

    await _delete(chat_id, STATE[chat_id]["msg_id"])

    try:
        msg = await bot.send_document(
            chat_id,
            document=data["tmf_id"],
            caption=fmt_version(data),
            reply_markup=kb_version_detail(ver, data.get("install", "")),
        )
        STATE[chat_id] = {"msg_id": msg.message_id, "state": "menu"}
    except Exception as e:
        print(f"[BOT] send_document error: {e}")
        msg = await bot.send_message(
            chat_id,
            f"<b>{ICO['err']}  Faylni yuborishda xatolik.</b>\n"
            f"<code>tmf_id: {data['tmf_id']}</code>",
            reply_markup=kb_back(),
        )
        STATE[chat_id] = {"msg_id": msg.message_id, "state": "menu"}


# ═══════════════════════════════════════════════════════════════
#  FILE-ID GETTER  —  admin uchun
# ═══════════════════════════════════════════════════════════════
# Foydalanish: Botga istalgan fayl forward qiling yoki yuboring.
# Bot uning file_id sini qaytaradi.
# Faqat ADMIN_IDS ro'yxatidagi foydalanuvchilar uchun ishlaydi.

@dp.message(F.document)
async def file_id_getter(msg: types.Message):
    """Forward qilingan yoki yuborilgan faylning file_id sini qaytarish."""
    if msg.from_user.id not in ADMIN_IDS:
        # Oddiy foydalanuvchilar xabarini o'chiramiz
        try:
            await msg.delete()
        except Exception:
            pass
        return

    doc = msg.document
    info = (
        f"<b>{ICO['id']}  File ID</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n\n"
        f"<b>file_id:</b>\n"
        f"<code>{doc.file_id}</code>\n\n"
        f"<b>file_unique_id:</b>\n"
        f"<code>{doc.file_unique_id}</code>\n\n"
        f"<b>Fayl nomi:</b>  <code>{doc.file_name or '—'}</code>\n"
        f"<b>Hajmi:</b>  <code>{doc.file_size:,} byte</code>"
    )
    await msg.reply(info)


# ═══════════════════════════════════════════════════════════════
#  HANDLERS
# ═══════════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    await send_menu(msg.chat.id, msg.message_id)


@dp.message(Command("id"))
async def cmd_id(msg: types.Message):
    """Foydalanuvchiga o'z Telegram ID sini ko'rsatish."""
    await msg.reply(
        f"<b>{ICO['id']}  Sizning ID:</b>\n"
        f"<code>{msg.from_user.id}</code>",
    )


@dp.callback_query(F.data == "menu")
async def cb_menu(call: types.CallbackQuery):
    if STATE.get(call.message.chat.id, {}).get("state") == "loading":
        await call.answer("Iltimos, kuting...", show_alert=True)
        return
    await call.answer()
    await send_menu(call.message.chat.id)


@dp.callback_query(F.data.startswith("page:"))
async def cb_page(call: types.CallbackQuery):
    page     = int(call.data.split(":")[1])
    versions = await db_versions()
    try:
        await call.message.edit_reply_markup(reply_markup=kb_versions(versions, page))
    except Exception:
        pass
    await call.answer()


@dp.callback_query(F.data.startswith("ver:"))
async def cb_version(call: types.CallbackQuery):
    if STATE.get(call.message.chat.id, {}).get("state") == "loading":
        await call.answer("Iltimos, kuting...", show_alert=True)
        return
    ver = call.data.split(":")[1]
    await call.answer()
    await show_version(call.message.chat.id, ver)


@dp.callback_query(F.data == "noop")
async def cb_noop(call: types.CallbackQuery):
    await call.answer()


@dp.message(F.text)
async def txt_handler(msg: types.Message):
    # Admin xabarlari o'chirilmaydi
    if msg.from_user.id not in ADMIN_IDS:
        try:
            await msg.delete()
        except Exception:
            pass

    text = msg.text.strip().lower()
    if re.match(r"^v?\d+\.\d+\.\d+$", text):
        if STATE.get(msg.chat.id, {}).get("state") == "loading":
            return
        await show_version(msg.chat.id, text.lstrip("v"))


# ─── Inline mode ─────────────────────────────────────────────────
@dp.inline_query()
async def inline_handler(q: types.InlineQuery):
    raw = q.query.strip().lower().lstrip("v")
    if not raw:
        await q.answer([], cache_time=1)
        return

    data = await db_version(raw)
    if data:
        res = InlineQueryResultArticle(
            id=data["version"],
            title=f"Jora Messenger v{data['version']}",
            description=f"Chiqarilgan: {str(data.get('created_at', ''))[:10]}",
            input_message_content=InputTextMessageContent(
                message_text=fmt_version(data),
                parse_mode="HTML",
            ),
        )
        await q.answer([res], cache_time=1)
    else:
        await q.answer([], cache_time=1)


# ═══════════════════════════════════════════════════════════════
#  STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════
async def on_startup():
    global _session
    print("◈ Jora Bot ishga tushdi")


async def on_shutdown():
    global _session
    if _session and not _session.closed:
        await _session.close()
    print("◈ Jora Bot to'xtatildi")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
