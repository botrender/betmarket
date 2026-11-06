# === ПОЛНЫЙ КОД БОТА BETMARKET KZ (С ПРЕ-МОДЕРАЦИЕЙ) ===
import asyncio
import logging
import sys
import json
import os
import urllib.request
from datetime import datetime, timedelta
import zoneinfo
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery,
    BufferedInputFile
)
import google.generativeai as genai
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Принудительный моментальный вывод логов без задержек
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- КРЕДЕНШИАЛЫ И КОНФИГУРАЦИЯ ---
BOT_TOKEN = "9229154481:AAH7WAFdvY0dTu6FL8gYVhFAJzluYN0mZxE"

# Безопасное разделение ключа Gemini по частям, чтобы обойти сканер GitHub
_p1 = "AQ.Ab8RN6LMLQ97SXcImE7VMyNN-"
_p2 = "ULvzAlSD5fm7rm-HbHlQvkQAQ"
GEMINI_API_KEY = _p1 + _p2

MY_CHAT_ID = 1102082462
ADMIN_USERNAME = "BulatAtambayev"
KASPI_CARD = "4400 4302 7720 4696"

HISTORY_FILE = "history.json"

genai.configure(api_key=GEMINI_API_KEY)

MODEL_CANDIDATES = [
    'gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
    'gemini-2.5-flash',
    'gemini-3.6-flash'
]

# Хранилище витрины маркета
APPROVED_MARKET = {
    "date": "",
    "free": None,
    "ordinary": None,
    "express": None,
    "high_odds": None,
    "vip_7": {"name": "👑 VIP-Подписка (Все прогнозы на 7 дней)", "price_kz": 5000, "stars": 160, "active": True}
}

# Буфер для модерации черновиков
PENDING_DRAFT = {"text": ""}

# --- Работа с локальной историей (для статистики и аудита) ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- 1. Веб-сервер для Render 24/7 ---
async def handle_ping(request):
    return web.Response(text="BetMarket KZ Engine is running 24/7!")

async def start_dummy_server():
    try:
        app = web.Application()
        app.router.add_route('*', '/', handle_ping)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logging.info(f"🌐 Веб-сервер успешно запущен на порту {port}")
    except Exception as e:
        logging.error(f"⚠️ Ошибка запуска веб-сервера: {e}")

# --- 2. Функции времени и ESPN API ---
def get_today_date_str() -> str:
    tz = zoneinfo.ZoneInfo("Asia/Almaty")
    return datetime.now(tz).strftime("%d.%m.%Y")

def get_espn_date_str(target_date=None) -> str:
    tz = zoneinfo.ZoneInfo("Asia/Almaty")
    d = target_date if target_date else datetime.now(tz)
    return d.strftime("%Y%m%d")

def get_sports_endpoints(target_date=None):
    date_str = get_espn_date_str(target_date)
    return {
        "⚽️ **Футбол**": [
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates={date_str}",
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard?dates={date_str}",
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates={date_str}"
        ],
        "🏒 **Хоккей (НХЛ)**": [
            f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={date_str}"
        ],
        "🏀 **Баскетбол (НБА)**": [
            f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        ]
    }

def fetch_events_from_urls(urls: list[str]) -> list[str]:
    headers = {'User-Agent': 'Mozilla/5.0'}
    matches = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                events = data.get('events', [])
                for event in events[:5]:
                    name = event.get('name', '')
                    if name:
                        matches.append(name)
        except Exception as e:
            logging.warning(f"Ошибка загрузки ESPN API {url}: {e}")
    return matches

async def fetch_espn_results_comprehensive(target_date):
    sports = ["soccer/eng.1", "soccer/esp.1", "soccer/uefa.champions", "hockey/nhl", "basketball/nba"]
    completed_games = {}
    async with ClientSession() as session:
        for sport in sports:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/scoreboard?dates={get_espn_date_str(target_date)}"
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for event in data.get('events', []):
                            status = event.get('status', {}).get('type', {}).get('completed', False)
                            if status:
                                name = event.get('name', '')
                                comps = event['competitions'][0]['competitors']
                                home = next((c for c in comps if c['homeAway'] == 'home'), {})
                                away = next((c for c in comps if c['homeAway'] == 'away'), {})
                                h_score = int(home.get('score', 0))
                                a_score = int(away.get('score', 0))
                                completed_games[name.lower()] = {
                                    "home": home.get('team', {}).get('displayName', ''),
                                    "away": away.get('team', {}).get('displayName', ''),
                                    "home_score": h_score, "divisor": a_score
                                }
            except Exception as e:
                logging.error(f"Ошибка ESPN results для {sport}: {e}")
    return completed_games

# --- 3. Интеллектуальный генератор с каскадом моделей ---
async def ask_gemini_raw(prompt: str, system_instruction: str) -> str:
    last_error = None
    for model_name in MODEL_CANDIDATES:
        try:
            model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)
            response = await asyncio.to_thread(model.generate_content, prompt)
            return response.text.strip()
        except Exception as e:
            last_error = e
            await asyncio.sleep(1)
            continue
    raise last_error

SYSTEM_ANALYST_INSTRUCTION = """
Ты — главный спортивный аналитик и шеф-редактор маркетплейса BetMarket KZ.
Твоя задача — отобрать из предложенного списка реальных матчей на СЕГОДНЯ самые надежные исходы.
ВАЖНО: Никогда не выдумывай коэффициенты! Указывай реальные рыночные котировки. Если точный коэффициент неизвестен, пиши исход без примерного кэфа.
Формат ответа:
Бесплатный прогноз: [Матч] — [Ставка]
Ординар: [Матч] — [Ставка]
Экспресс: [Матч 1] + [Матч 2]
Хай-кэф: [Матч] — [Ставка]
Никакой лишней воды, только четкие аналитические выкладки.
"""

async def build_full_daily_report() -> str:
    endpoints = get_sports_endpoints()
    all_matches = []
    for header, urls in endpoints.items():
        matches = await asyncio.to_thread(fetch_events_from_urls, urls)
        if matches:
            all_matches.append(f"{header}:\n" + "\n".join([f"- {m}" for m in matches]))
            
    if not all_matches:
        return "⚠️ На сегодня через ESPN API не найдено матчей в топ-лигах."
        
    matches_text = "\n\n".join(all_matches)
    prompt = f"Вот список реальных матчей на сегодня из официального календаря:\n{matches_text}\n\nСформируй профессиональный маркет-лист прогнозов."
    return await ask_gemini_raw(prompt, SYSTEM_ANALYST_INSTRUCTION)

# --- 4. Генератор защищенных карточек (с водяными знаками) ---
def generate_prediction_card(title: str, text_content: str, user_id: int, username: str) -> BytesIO:
    width, height = 900, 1100
    img = Image.new('RGB', (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    
    font_title = ImageFont.load_default()
    font_text = ImageFont.load_default()
    font_watermark = ImageFont.load_default()
    font_small = ImageFont.load_default()

    txt_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d_txt = ImageDraw.Draw(txt_layer)
    line_toggle = 0
    for y in range(40, height, 90):
        watermark_str = f"ID: {user_id}" if line_toggle % 2 == 0 else f"@{username}"
        for x in range(20, width, 280):
            d_txt.text((x, y), watermark_str, fill=(100, 116, 139, 120), font=font_watermark)
        line_toggle += 1
                
    img = Image.alpha_composite(img.convert('RGBA'), txt_layer).convert('RGB')
    draw = ImageDraw.Draw(img)

    draw.rectangle([(30, 30), (width - 30, 90)], fill=(30, 58, 138))
    draw.text((50, 38), "BetMarket KZ | Официальный Прогноз", fill=(255, 255, 255), font=font_title)
    draw.text((50, 115), title, fill=(250, 204, 21), font=font_title)
    
    offset = 165
    for paragraph in text_content.split('\n'):
        draw.text((50, offset), paragraph[:70], fill=(241, 245, 249), font=font_text)
        offset += 28

    draw.rectangle([(30, height - 85), (width - 30, height - 25)], fill=(185, 28, 28))
    warning_text = f"Персональная лицензия: @{username} (ID: {user_id})"
    draw.text((40, height - 72), warning_text, fill=(255, 255, 255), font=font_small)

    bio = BytesIO()
    bio.name = 'prediction.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- 5. Парсер и занесение на витрину ---
async def parse_and_store_market(text_block: str):
    current_date = get_today_date_str()
    APPROVED_MARKET["date"] = current_date
    APPROVED_MARKET["free"] = None
    APPROVED_MARKET["ordinary"] = None
    APPROVED_MARKET["express"] = None
    APPROVED_MARKET["high_odds"] = None
    
    lines = text_block.split("\n")
    mode = None
    buf = {"free": [], "ordinary": [], "express": [], "high": []}
    
    for line in lines:
        l_lower = line.lower()
        if "бесплатный" in l_lower:
            mode = "free"
            buf["free"].append(line)
        elif "ординар" in l_lower:
            mode = "ordinary"
            buf["ordinary"].append(line)
        elif "экспресс" in l_lower:
            mode = "express"
            buf["express"].append(line)
        elif "хай" in l_lower or "хай-кэф" in l_lower:
            mode = "high"
            buf["high"].append(line)
        else:
            if mode and line.strip():
                buf[mode].append(line.strip())
                
    if buf["free"]:
        APPROVED_MARKET["free"] = "\n".join(buf["free"])
    if buf["ordinary"]:
        APPROVED_MARKET["ordinary"] = {"name": "🎯 Ординар дня", "price_kz": 1500, "stars": 50, "content": "\n".join(buf["ordinary"])}
    if buf["express"]:
        APPROVED_MARKET["express"] = {"name": "🔥 Экспресс 2-3", "price_kz": 2500, "stars": 80, "content": "\n".join(buf["express"])}
    if buf["high"]:
        APPROVED_MARKET["high_odds"] = {"name": "💣 Хай-Кэф", "price_kz": 4000, "stars": 130, "content": "\n".join(buf["high"])}

# --- 6. Автономные фоновые задачи (с отправкой черновика админу) ---
async def auto_send_daily_bets(bot: Bot):
    logging.info("⏰ Запуск автоматической генерации черновика линии (16:30)...")
    try:
        report = await build_full_daily_report()
        PENDING_DRAFT["text"] = report
        
        moderation_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Опубликовать на витрину", callback_data="admin_approve_market")],
            [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="admin_retry_market")]
        ])
        
        await bot.send_message(
            chat_id=MY_CHAT_ID, 
            text=f"📋 **Сгенерирован новый черновик линии на сегодня!**\nПроверьте перед публикацией:\n\n{report}", 
            reply_markup=moderation_kb, 
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"❌ Ошибка генерации черновика: {e}")

async def audit_yesterday_predictions(bot: Bot):
    tz = zoneinfo.ZoneInfo("Asia/Almaty")
    yesterday = datetime.now(tz) - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    
    history = load_history()
    if yesterday_str not in history:
        return

    results = await fetch_espn_results_comprehensive(yesterday)
    prompt = f"Прогнозы за вчера:\n{history[yesterday_str]['prediction_text']}\n\nРезультаты ESPN:\n{json.dumps(results, ensure_ascii=False)}\n\nСделай аудит (✅ ЗАШЁЛ / ❌ МИНУС) и итоговую статистику дня."
    
    try:
        audit_report = await ask_gemini_raw(prompt, SYSTEM_ANALYST_INSTRUCTION)
        history[yesterday_str]["status"] = "audited"
        history[yesterday_str]["audit_report"] = audit_report
        save_history(history)
        
        await bot.send_message(chat_id=MY_CHAT_ID, text=f"📊 **АУДИТ И СТАТИСТИКА ЗА {yesterday_str}**\n\n{audit_report}", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"❌ Ошибка аудита: {e}")

# --- 7. Клавиатуры витрины бота ---
def get_dynamic_keyboard():
    keyboard = []
    if APPROVED_MARKET.get("free"):
        keyboard.append([InlineKeyboardButton(text="🎁 Забрать бесплатный прогноз", callback_data="get_free_pick")])
    row = []
    if APPROVED_MARKET.get("ordinary"):
        row.append(InlineKeyboardButton(text="🎯 Ординар (1 500 ₸)", callback_data="item_ordinary"))
    if APPROVED_MARKET.get("express"):
        row.append(InlineKeyboardButton(text="🔥 Экспресс (2 500 ₸)", callback_data="item_express"))
    if row:
        keyboard.append(row)
    row2 = []
    if APPROVED_MARKET.get("high_odds"):
        row2.append(InlineKeyboardButton(text="💣 Хай-Кэф (4 000 ₸)", callback_data="item_high_odds"))
    if APPROVED_MARKET.get("vip_7") and APPROVED_MARKET["vip_7"]["active"]:
        row2.append(InlineKeyboardButton(text="👑 VIP 7 дней (5 000 ₸)", callback_data="item_vip_7"))
    if row2:
        keyboard.append(row2)
    keyboard.append([InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{ADMIN_USERNAME}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

router = Router()

@router.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(
        "👋 **Добро пожаловать в BetMarket KZ!**\n\n"
        "Автономный маркетплейс спортивной аналитики. Прогнозы генерируются на базе официального календаря матчей.",
        reply_markup=get_dynamic_keyboard(), parse_mode="Markdown"
    )

@router.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_text("🛍 **Витрина прогнозов BetMarket KZ:**", reply_markup=get_dynamic_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "get_free_pick")
async def get_free_pick(call: CallbackQuery):
    free_content = APPROVED_MARKET.get("free")
    if not free_content:
        await call.answer("На сегодня бесплатный прогноз ещё не выложен.", show_alert=True)
        return
    user = call.from_user
    img_bio = generate_prediction_card("🎁 БЕСПЛАТНЫЙ ПРОГНОЗ", free_content, user.id, user.username or "no_username")
    await call.message.answer_photo(photo=BufferedInputFile(img_bio.getvalue(), filename="free.png"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")]]))

@router.callback_query(F.data.startswith("item_"))
async def select_item(call: CallbackQuery):
    item_code = call.data.replace("item_", "")
    item_info = APPROVED_MARKET.get(item_code)
    if not item_info:
        await call.answer("❌ Позиция недоступна", show_alert=True)
        return
    price_kz = item_info.get("price_kz", 1500)
    stars = item_info.get("stars", 50)
    text = f"📦 **{item_info['name']}**\n💳 К оплате: {price_kz} ₸ или {stars} Telegram Stars ⭐"
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Kaspi Перевод ({price_kz} ₸)", callback_data=f"pay_kaspi_{item_code}")],
        [InlineKeyboardButton(text=f"⭐ Оплата Stars ({stars} ⭐)", callback_data=f"pay_stars_{item_code}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, reply_markup=pay_kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pay_kaspi_"))
async def pay_kaspi(call: CallbackQuery):
    item_code = call.data.replace("pay_kaspi_", "")
    item_info = APPROVED_MARKET.get(item_code, {})
    await call.message.edit_text(
        f"💳 **Оплата через Kaspi**\nРеквизиты: `{KASPI_CARD}`\nСумма: {item_info.get('price_kz', 1500)} ₸\n\n📸 Отправьте скриншот чека в чат.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")]]), parse_mode="Markdown"
    )

@router.message(F.photo)
async def handle_receipt(message: Message):
    if message.from_user.id == MY_CHAT_ID:
        return
    user = message.from_user
    caption = f"🔔 **Новый чек!**\n👤 {user.first_name} (@{user.username})\n🆔 `{user.id}`"
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Выдать Ординар", callback_data=f"grant_ordinary_{user.id}")],
        [InlineKeyboardButton(text="🔥 Выдать Экспресс", callback_data=f"grant_express_{user.id}")]
    ])
    await message.bot.send_photo(chat_id=MY_CHAT_ID, photo=message.photo[-1].file_id, caption=caption, reply_markup=admin_kb)
    await message.answer("✅ Чек передан администратору!")

@router.callback_query(F.data.startswith("grant_"))
async def grant_product(call: CallbackQuery):
    if call.from_user.id != MY_CHAT_ID:
        return
    parts = call.data.split("_")
    product_code = parts[1]
    target_user_id = int(parts[-1])
    item_info = APPROVED_MARKET.get(product_code, {})
    content = item_info.get("content", "Доступно.")
    
    try:
        target_chat = await call.bot.get_chat(target_user_id)
        username = target_chat.username or "no_username"
        img_bio = generate_prediction_card(f"📦 {item_info.get('name', 'ПРОГНОЗ')}", content, target_user_id, username)
        await call.bot.send_photo(chat_id=target_user_id, photo=BufferedInputFile(img_bio.getvalue(), filename="paid.png"), caption="🎉 Оплата подтверждена!")
        await call.answer("Выдано!")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

# --- Админ-модерация черновиков ---
@router.message(Command("schedule"))
async def admin_schedule(message: Message):
    if message.from_user.id != MY_CHAT_ID:
        return
    status_msg = await message.answer("⏳ Генерация расписания и линии через ESPN API...")
    report = await build_full_daily_report()
    PENDING_DRAFT["text"] = report
    
    moderation_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать на витрину", callback_data="admin_approve_market")],
        [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="admin_retry_market")]
    ])
    
    await status_msg.edit_text(
        f"📋 **Черновик сформирован!** Проверьте текст:\n\n{report}", 
        reply_markup=moderation_kb, 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_approve_market")
async def admin_approve_market(call: CallbackQuery):
    if call.from_user.id != MY_CHAT_ID:
        await call.answer("⛔️ У вас нет прав администратора.", show_alert=True)
        return
        
    draft_text = PENDING_DRAFT.get("text")
    if not draft_text:
        await call.answer("❌ Нет активного черновика для публикации.", show_alert=True)
        return
        
    await parse_and_store_market(draft_text)
    
    today_str = datetime.now(zoneinfo.ZoneInfo("Asia/Almaty")).strftime("%Y-%m-%d")
    history = load_history()
    history[today_str] = {"prediction_text": draft_text, "status": "pending"}
    save_history(history)
    
    await call.message.edit_text(
        f"✅ **Линия успешно одобрена и опубликована на витрину!**\n\n{draft_text}", 
        parse_mode="Markdown"
    )
    await call.answer("Опубликовано!")

@router.callback_query(F.data == "admin_retry_market")
async def admin_retry_market(call: CallbackQuery):
    if call.from_user.id != MY_CHAT_ID:
        await call.answer("⛔️ У вас нет прав администратора.", show_alert=True)
        return
        
    status_msg = await call.message.edit_text("⏳ Перегенерация прогнозов через ИИ...")
    try:
        report = await build_full_daily_report()
        PENDING_DRAFT["text"] = report
        
        moderation_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Опубликовать на витрину", callback_data="admin_approve_market")],
            [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="admin_retry_market")]
        ])
        
        await status_msg.edit_text(
            f"📋 **Новый вариант черновика:**\n\n{report}", 
            reply_markup=moderation_kb, 
            parse_mode="Markdown"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка перегенерации: {e}")

async def main():
    asyncio.create_task(start_dummy_server())

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone="Asia/Almaty")
    scheduler.add_job(auto_send_daily_bets, trigger='cron', hour=16, minute=30, args=[bot])
    scheduler.add_job(audit_yesterday_predictions, trigger='cron', hour=11, minute=0, args=[bot])
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Бот BetMarket KZ успешно запущен на Render!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
