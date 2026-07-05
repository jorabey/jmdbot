import os
import sys
import subprocess
import asyncio
import re
import gdown

# ================================================================
# ⚙️ 1-QADAM: AVTOMATIK KUTUBXONALARNI TEKSHIRISH VA O'RNATISH
# ================================================================
def auto_install():
    required = {"aiogram": "aiogram", "aiohttp": "aiohttp"}
    for module, pkg in required.items():
        try:
            __import__(module)
        except ImportError:
            print(f"📦 {pkg} o'rnatilmoqda (Tezkor ishlash uchun)...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

auto_install()

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp

# ================================================================
# 🔑 2-QADAM: MA'LUMOTLARINGIZNI SHU YERGA YOZING
# ================================================================
BOT_TOKEN = "8853810127:AAHw26Q70UWt4_uIPW-OzzF03R3jmYAkyBw"
SUPABASE_REST_URL = "https://dswpheeugtozosdaguym.supabase.co/rest/v1/versions" # ⚠️ O'ZGARTIRING
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRzd3BoZWV1Z3Rvem9zZGFndXltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgzMDU4MzAsImV4cCI6MjA5Mzg4MTgzMH0.NvIEl0_2T54QLqr9uvHESd-1XIdT-s8FmS8R60IqcJ0" # ⚠️ O'ZGARTIRING
# ================================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Foydalanuvchilarning holatini saqlash (chatni toza saqlash uchun)
# Tuzilishi: chat_id -> {'msg_id': int, 'state': 'menu' yoki 'loading'}
user_state = {}

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# --- BAZADAN MA'LUMOT OLISH ---
async def fetch_versions(active_only=True):
    params = {"active": "eq.true", "select": "*", "order": "version.desc"} if active_only else {"select": "*"}
    async with aiohttp.ClientSession() as session:
        async with session.get(SUPABASE_REST_URL, headers=headers, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
    return []

async def fetch_single_version(version):
    params = {"version": f"eq.{version}", "select": "*"}
    async with aiohttp.ClientSession() as session:
        async with session.get(SUPABASE_REST_URL, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data[0] if data else None
    return None

# --- G-DRIVE DAN TEZKOR YUKLASH ---
def get_gdrive_id(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match: return match.group(1)
    match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match: return match.group(1)
    return None

async def download_file(url):
    try:
        # Faylni yuklash uchun unique nom beramiz (har bir chat uchun alohida bo'lishi uchun)
        filename = "temp_file.apk"
        # Agar fayl eski bo'lsa o'chirib tashlaymiz
        if os.path.exists(filename):
            os.remove(filename)

        # wget yordamida yuklash (Google Drive "Download anyway" ni o'zi bosib o'tadi)
        # --no-check-certificate: SSL xatolarini oldini oladi
        # -O: faylni aynan shu nom bilan saqlash
        cmd = f"wget --no-check-certificate '{url}' -O {filename}"
        
        # Jarayonni ishga tushiramiz
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        # Fayl yuklanganligini tekshiramiz
        if os.path.exists(filename) and os.path.getsize(filename) > 1024: # Fayl 1kb dan katta bo'lsa
            with open(filename, 'rb') as f:
                content = f.read()
            os.remove(filename) # Faylni o'chiramiz
            return content
        else:
            print("Yuklashda xato: Fayl topilmadi yoki 0 kb.")
            return None
    except Exception as e:
        print(f"Yuklashda xato: {e}")
        return None

# --- XABARLAR DIZAYNI ---
def format_caption(data):
    # 'Noma'lum' so'zini oldindan o'zgaruvchiga olamiz
    noma = "Noma'lum"
    created = str(data.get('created_at', noma))[:10]
    
    return (
        "⚡ <b>Jora Messenger</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Versiya:</b> <code>v{data.get('version')}</code>\n"
        f"\n"
        f"📅 <b>Chiqarilgan sana:</b> <i>{created}</i>\n"
        f"\n"
        f"🏢 <b>Kompaniya:</b> <code>{data.get('company', 'JORA NET')}</code>\n"
        f"\n"
        f"👤 <b>Muallif:</b> <i>{data.get('author', 'Jora Developer')}</i>\n"
        f"\n"
        f"🔗 <b>Manba:</b> <a href='{data.get('install', '#')}'>Yuklash manzili</a>\n"
        f"\n"
        f"🔗 <b>Web Sayt:</b> <a href='{data.get('url', '#')}'>Kirish</a>"
    )

def get_menu_keyboard(versions, page=0):
    builder = InlineKeyboardBuilder()
    start_idx = page * 10
    end_idx = start_idx + 10
    current_versions = versions[start_idx:end_idx]

    for v in current_versions:
        builder.button(text=f"💎 v{v['version']}", callback_data=f"get_{v['version']}")
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"page_{page-1}"))
    if end_idx < len(versions):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.adjust(1) # Bitta qatorda bittadan tugma
    return builder.as_markup()

def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Orqaga", callback_data="back_to_menu")
    return builder.as_markup()

# --- ASOSIY MANTIQ VA TOZALASH ---
async def clean_and_send_menu(chat_id, message_to_delete=None):
    # Eski xabarni o'chirish (agar bo'lsa)
    if message_to_delete:
        try:
            await message_to_delete.delete()
        except: pass

    if chat_id in user_state and 'msg_id' in user_state[chat_id]:
        try:
            await bot.delete_message(chat_id, user_state[chat_id]['msg_id'])
        except: pass

    versions = await fetch_versions()
    if not versions:
        msg = await bot.send_message(chat_id, "📭 <i>Hozircha faol versiyalar topilmadi.</i>", parse_mode="HTML")
    else:
        kb = get_menu_keyboard(versions, 0)
        msg = await bot.send_message(chat_id, "✨ <b>Jora Messenger Yangilash Markazi</b>\n\n👇 Kerakli versiyani tanlang:", reply_markup=kb, parse_mode="HTML")
    
    user_state[chat_id] = {'msg_id': msg.message_id, 'state': 'menu'}

async def process_version_request(chat_id, version_num):
    # 1. Eski xabarni "Yuklanmoqda" deb yangilash (aslida u yuklamaydi, shunchaki UI uchun)
    if chat_id in user_state and 'msg_id' in user_state[chat_id]:
        try:
            await bot.edit_message_text("⏳ <i>Tayyorlanmoqda...</i>", chat_id, user_state[chat_id]['msg_id'], parse_mode="HTML")
        except: pass
    else:
        msg = await bot.send_message(chat_id, "⏳ <i>Tayyorlanmoqda...</i>", parse_mode="HTML")
        user_state[chat_id] = {'msg_id': msg.message_id, 'state': 'loading'}

    user_state[chat_id]['state'] = 'loading'
    
    # 2. Bazadan ma'lumot olish
    data = await fetch_single_version(version_num)
    
    # 3. Agar fayl topilmasa
    if not data or not data.get('tmf_id'):
        kb = get_back_keyboard()
        await bot.edit_message_text("❌ <b>Bu versiya topilmadi yoki fayl ID mavjud emas.</b>", chat_id, user_state[chat_id]['msg_id'], reply_markup=kb, parse_mode="HTML")
        user_state[chat_id]['state'] = 'menu'
        return

    # 4. Eski xabarni o'chirish
    try:
        await bot.delete_message(chat_id, user_state[chat_id]['msg_id'])
    except: pass

    # 5. Faylni yuborish (file_id orqali)
    # E'tibor bering: download_file chaqirilmayapti, shuning uchun juda tez ishlaydi!
    try:
        msg = await bot.send_document(
            chat_id, 
            document=data['tmf_id'], # Bazadagi ustun nomi
            caption=format_caption(data),
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
        user_state[chat_id] = {'msg_id': msg.message_id, 'state': 'menu'}
    except Exception as e:
        print(f"Fayl yuborishda xato: {e}")
        await bot.send_message(chat_id, "❌ Faylni yuborishda xatolik yuz berdi. (ID noto'g'ri bo'lishi mumkin)")
        user_state[chat_id]['state'] = 'menu'

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # Start yozilganda, chatni tozalab yangi menyu ochamiz
    await clean_and_send_menu(message.chat.id, message)

@dp.callback_query(F.data.startswith("page_"))
async def page_handler(call: types.CallbackQuery):
    page = int(call.data.split("_")[1])
    versions = await fetch_versions()
    kb = get_menu_keyboard(versions, page)
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except: pass
    await call.answer()

@dp.callback_query(F.data.startswith("get_"))
async def get_version_handler(call: types.CallbackQuery):
    if user_state.get(call.message.chat.id, {}).get('state') == 'loading':
        await call.answer("Iltimos, kutib turing...", show_alert=True)
        return
    
    version_num = call.data.split("_")[1]
    await call.answer()
    await process_version_request(call.message.chat.id, version_num)

@dp.callback_query(F.data == "back_to_menu")
async def back_handler(call: types.CallbackQuery):
    if user_state.get(call.message.chat.id, {}).get('state') == 'loading':
        await call.answer("Kuting...", show_alert=True)
        return
    await call.answer()
    await clean_and_send_menu(call.message.chat.id)

@dp.message(F.text)
async def text_handler(message: types.Message):
    # Har qanday yozilgan xabarni darhol o'chiramiz (Chat tozaligi uchun)
    try:
        await message.delete()
    except: pass

    text = message.text.strip().lower()
    
    # Agar foydalanuvchi "v1.0.0" yoki "1.0.0" formatida yozsa
    if re.match(r'^v?\d+\.\d+\.\d+$', text):
        if user_state.get(message.chat.id, {}).get('state') == 'loading':
            return
        version_num = text.replace("v", "")
        await process_version_request(message.chat.id, version_num)

@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery):
    query = inline_query.query.strip().lower()
    if query.startswith("v"):
        version_num = query.replace("v", "")
        data = await fetch_single_version(version_num)
        
        if data:
            result = InlineQueryResultArticle(
                id=data['version'],
                title=f"Jora Messenger v{data['version']}",
                description=f"Chiqarilgan: {data.get('created_at', '')[:10]}",
                input_message_content=InputTextMessageContent(
                    message_text=format_caption(data),
                    parse_mode="HTML"
                )
            )
            await inline_query.answer([result], cache_time=1)
        else:
            await inline_query.answer([], cache_time=1)



# ================================================================
# 🚀 ISHGA TUSHIRISH
# ================================================================
async def main():
    print("🚀 Bot asinxron rejimda (Tezkor) ishga tushdi...")
    # Barcha eski xabarlarni (bot o'chiqligida kelgan) o'tkazib yuborish
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())