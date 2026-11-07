# === ПОЛНЫЙ КОД БОТА BETMARKET KZ (VIP-АВТОМАТИЗАЦИЯ НА 7 ДНЕЙ) ===
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

BOT_TOKEN = "9229154481:AAH7WAFdvY0dTu6FL8gYVhFAJzluYN0mZxE"

_p1 = "AQ.Ab8RN6LMLQ97SXcImE7VMyNN-"
_p2 = "ULvzAlSD5fm7rm-HbHlQvkQAQ"
GEMINI_API_KEY = _p1 + _p2

MY_CHAT_ID = 1102082462
ADMIN_USERNAME = "BulatAtambayev"
KASPI_CARD = "4400 4302 7720 4696"

HISTORY_FILE = "history.json"
VIP_USERS_FILE = "vip_users.json"

genai.configure(api_key=GEMINI_API_KEY)

MODEL_CANDIDATES = [
    'gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
    'gemini-2.5-flash',
    'gemini-3.6-flash'
]

APPROVED_MARKET = {
    "date": "",
    "free": None,
    "ordinary": {
        "name": "🎯 Ординар дня", 
        "price_kz": 1500, 
        "stars": 50, 
        "close_time": "19:00", 
        "content": None
    },
    "express": {
        "name": "🔥 Экспресс 2-3", 
        "price_kz": 2500, 
        "stars": 80, 
        "close_time": "21:00", 
        "content": None
    },
    "high_odds": {
        "name": "💣 Хай-Кэф Экспресс (Кэф 4-7)", 
        "price_kz": 4000, 
        "stars": 130, 
        "close_time": "22:30", 
        "content": None
    },
    "vip_7": {
        "name": "👑 VIP-Подписка (Все прогнозы на 7 дней)", 
        "price_kz": 5000, 
        "stars": 160, 
        "active": True, 
        "content": "👑 VIP-Доступ ко всем прогнозам (Ординар, Экспресс, Хай-Кэф) + Эксклюзивный VIP-матч (кэф 2.0+)."
    }
}

PENDING_DRAFT = {"text": ""}
USER_PENDING_PURCHASE = {}
ADMIN_STATE = {}

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

def load_vip_users():
    if os.path.exists(VIP_USERS_FILE):
        try:
            with open(VIP_USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_vip_users(data):
    with open(VIP_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_vip_user(user_id: int):
    vip_data = load_vip_users()
    tz = zoneinfo.ZoneInfo("Asia/Almaty")
    # Подписка на 7 дней от текущего момента
    expire_dt = datetime.now(tz) + timedelta(days=7)
    vip_data[str(user_id)] = expire_dt.isoformat()
    save_vip_users(vip_data)

def is_user_vip(user_id: int) -> bool:
    vip_data = load_vip_users()
    str_id = str(user_id)
    if str_id not in vip_data:
        return False
    try:
        tz = zoneinfo.ZoneInfo("Asia/Almaty")
        expire_dt = datetime.fromisoformat(vip_data[str_id])
        if datetime.now(tz) < expire_dt:
            return True
    except Exception:
        pass
    return False

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
Твоя задача — отобрать из предложенного списка реальных матчей на СЕГОДНЯ самые надежные исходы и составить VIP-бонус.
ВАЖНО: Никогда не выдумывай коэффициенты! Указывай реальные рыночные котировки.

Строгий формат ответа:
Бесплатный прогноз: 
[Матч] — [Ставка]

Ординар: 
[Матч] — [Ставка]

Экспресс: 
[Матч 1] + [Матч 2] (Итоговый кэф 1.80-2.20)

Хай-кэф: 
[Матч 1] + [Матч 2] + [Матч 3] (Итоговый кэф от 4.00 до 7.00)

VIP-бонус:
[Матч] — [Ставка] (Эксклюзивный коэффициент не ниже 2.00)

---
Аналитическое обоснование:
1. [Описание]
2. [Описание]
3. [Описание]
4. [Описание]
5. [Описание]
Никакой лишней воды, строго соблюдай разделение на прогнозы и аналитику в конце.
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
    prompt = f"Вот список реальных матчей на сегодня из официального календаря:\n{matches_text}\n\nСформируй профессиональный маркет-лист прогнозов, включая специальный VIP-бонус с коэффициентом от 2.0."
    return await ask_gemini_raw(prompt, SYSTEM_ANALYST_INSTRUCTION)

def generate_prediction_card(title: str, text_content: str, user_id: int, username: str) -> BytesIO:
    width, height = 900, 1100
    img = Image.new('RGB', (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("DejaVuSans.ttf", 28)
        font_text = ImageFont.truetype("DejaVuSans.ttf", 20)
        font_watermark = ImageFont.truetype("DejaVuSans.ttf", 20)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 16)
    except IOError:
        try:
            font_title = ImageFont.truetype("arial.ttf", 28)
            font_text = ImageFont.truetype("arial.ttf", 20)
            font_watermark = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except IOError:
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
    
    offset = 175
    max_line_length = 50
    
    for paragraph in text_content.split('\n'):
        words = paragraph.split(' ')
        current_line = ""
        for word in words:
            if len(current_line + " " + word) <= max_line_length:
                current_line += (" " + word) if current_line else word
            else:
                draw.text((50, offset), current_line, fill=(241, 245, 249), font=font_text)
                offset += 30
                current_line = word
        if current_line:
            draw.text((50, offset), current_line, fill=(241, 245, 249), font=font_text)
            offset += 35

    draw.rectangle([(30, height - 85), (width - 30, height - 25)], fill=(185, 28, 28))
    warning_text = f"Персональная лицензия: @{username} (ID: {user_id})"
    draw.text((40, height - 72), warning_text, fill=(255, 255, 255), font=font_small)

    bio = BytesIO()
    bio.name = 'prediction.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

async def parse_and_store_market(text_block: str):
    APPROVED_MARKET["date"] = get_today_date_str()
    APPROVED_MARKET["free"] = None
    APPROVED_MARKET["ordinary"]["content"] = None
    APPROVED_MARKET["express"]["content"] = None
    APPROVED_MARKET["high_odds"]["content"] = None
    APPROVED_MARKET["vip_7"]["content_extra"] = None
    
    current_section = None
    buf = {"free": [], "ordinary": [], "express": [], "high": [], "vip_bonus": []}
    
    for line in text_block.split("\n"):
        l_lower = line.lower()
        if "аналитическое обоснование" in l_lower or "аналитика" in l_lower or "---" in l_lower:
            current_section = None
            continue
            
        if "бесплатный прогноз:" in l_lower:
            current_section = "free"
            clean_val = line.split(":", 1)[1].strip()
            if clean_val: buf["free"].append(clean_val)
            continue
        elif "ординар:" in l_lower:
            current_section = "ordinary"
            clean_val = line.split(":", 1)[1].strip()
            if clean_val: buf["ordinary"].append(clean_val)
            continue
        elif "экспресс:" in l_lower:
            current_section = "express"
            clean_val = line.split(":", 1)[1].strip()
            if clean_val: buf["express"].append(clean_val)
            continue
        elif "хай-кэф:" in l_lower or "хай кэф:" in l_lower:
            current_section = "high"
            clean_val = line.split(":", 1)[1].strip()
            if clean_val: buf["high"].append(clean_val)
            continue
        elif "vip-бонус:" in l_lower or "вип-бонус:" in l_lower:
            current_section = "vip_bonus"
            clean_val = line.split(":", 1)[1].strip()
            if clean_val: buf["vip_bonus"].append(clean_val)
            continue
            
        if current_section and line.strip():
            if line.strip()[0].isdigit() and "." in line[:3]:
                continue
            clean_line = line.replace("*", "").replace("—", "-").strip()
            if clean_line:
                buf[current_section].append(clean_line)
                
    if buf["free"]:
        APPROVED_MARKET["free"] = "\n".join(buf["free"])
    if buf["ordinary"]:
        APPROVED_MARKET["ordinary"]["content"] = "\n".join(buf["ordinary"])
    if buf["express"]:
        APPROVED_MARKET["express"]["content"] = "\n".join(buf["express"])
    if buf["high"]:
        APPROVED_MARKET["high_odds"]["content"] = "\n".join(buf["high"])
    if buf["vip_bonus"]:
        APPROVED_MARKET["vip_7"]["content_extra"] = "\n".join(buf["vip_bonus"])

async def send_vip_bundle_to_user(bot: Bot, user_id: int, username: str):
    ord_c = APPROVED_MARKET["ordinary"].get("content", "Нет данных")
    exp_c = APPROVED_MARKET["express"].get("content", "Нет данных")
    high_c = APPROVED_MARKET["high_odds"].get("content", "Нет данных")
    vip_extra = APPROVED_MARKET["vip_7"].get("content_extra", "Эксклюзивный VIP-матч (кэф 2.0+)")
    
    full_vip_content = (
        f"👑 **VIP ПАКЕТ ПРОГНОЗОВ НА СЕГОДНЯ:**\n\n"
        f"🎯 **Ординар:**\n{ord_c}\n\n"
        f"🔥 **Экспресс:**\n{exp_c}\n\n"
        f"💣 **Хай-Кэф:**\n{high_c}\n\n"
        f"⭐ **Эксклюзивный VIP-бонус (кэф 2.0+):**\n{vip_extra}"
    )
    img_bio = generate_prediction_card("👑 VIP-ДОСТУП КО ВСЕМ ПРОГНОЗАМ", full_vip_content, user_id, username)
    await bot.send_photo(chat_id=user_id, photo=BufferedInputFile(img_bio.getvalue(), filename="vip_daily.png"), caption="🎁 Ваши ежедневные VIP-прогнозы по активной подписке!")

async def auto_send_daily_bets(bot: Bot):
    logging.info("⏰ Запуск автоматической генерации черновика линии (16:30)...")
    try:
        report = await build_full_daily_report()
        PENDING_DRAFT["text"] = report
        
        ord_t = APPROVED_MARKET["ordinary"]["close_time"]
        exp_t = APPROVED_MARKET["express"]["close_time"]
        high_t = APPROVED_MARKET["high_odds"]["close_time"]
        
        moderation_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Опубликовать и разослать VIP", callback_data="admin_approve_market")],
            [InlineKeyboardButton(text="⚙️ Настроить время по категориям", callback_data="admin_cat_time_menu")],
            [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="admin_retry_market")]
        ])
        
        await bot.send_message(
            chat_id=MY_CHAT_ID, 
            text=(
                f"📋 **Сгенерирован новый черновик линии на сегодня!**\n\n"
                f"⏳ **Дедлайны продаж:** Ординар ({ord_t}) | Экспресс ({exp_t}) | Хай-Кэф ({high_t})\n\n"
                f"При публикации линия автоматически уйдет всем активным VIP-клиентам в ЛС.\n\nПроверьте текст:\n\n{report}"
            ), 
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

def is_sale_active(close_time_str: str) -> bool:
    """Умная проверка дедлайна с учетом ночных матчей (после полуночи)"""
    try:
        tz = zoneinfo.ZoneInfo("Asia/Almaty")
        now = datetime.now(tz)
        h, m = map(int, close_time_str.split(":"))
        
        # Создаем время дедлайна на сегодня
        close_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        # Если дедлайн указан глубокой ночью (например, 00:50, 01:00), 
        # а сейчас вечер предыдущего дня, то продажи активны.
        # Если сейчас уже ночь после дедлайна — продажи закрываются.
        if h < 6 and now.hour >= 18:
            # Матч ночью следующего дня, сегодня продажи еще идут
            return True
            
        return now < close_dt
    except Exception:
        return True

def get_dynamic_keyboard():
    keyboard = []
    if APPROVED_MARKET.get("free"):
        keyboard.append([InlineKeyboardButton(text="🎁 Забрать бесплатный прогноз", callback_data="get_free_pick")])
    
    row = []
    if APPROVED_MARKET["ordinary"].get("content") and is_sale_active(APPROVED_MARKET["ordinary"]["close_time"]):
        row.append(InlineKeyboardButton(text=f"🎯 Ординар ({APPROVED_MARKET['ordinary']['price_kz']} ₸)", callback_data="item_ordinary"))
    if APPROVED_MARKET["express"].get("content") and is_sale_active(APPROVED_MARKET["express"]["close_time"]):
        row.append(InlineKeyboardButton(text=f"🔥 Экспресс ({APPROVED_MARKET['express']['price_kz']} ₸)", callback_data="item_express"))
    if row:
        keyboard.append(row)
        
    row2 = []
    if APPROVED_MARKET["high_odds"].get("content") and is_sale_active(APPROVED_MARKET["high_odds"]["close_time"]):
        row2.append(InlineKeyboardButton(text=f"💣 Хай-Кэф ({APPROVED_MARKET['high_odds']['price_kz']} ₸)", callback_data="item_high_odds"))
    if APPROVED_MARKET.get("vip_7") and APPROVED_MARKET["vip_7"]["active"]:
        row2.append(InlineKeyboardButton(text=f"👑 VIP 7 дней ({APPROVED_MARKET['vip_7']['price_kz']} ₸)", callback_data="item_vip_7"))
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
    
    if item_code != "vip_7":
        item_data = APPROVED_MARKET.get(item_code, {})
        if not is_sale_active(item_data.get("close_time", "21:00")):
            await call.answer("❌ Время продаж этого прогноза истекло!", show_alert=True)
            return

    if item_code == "vip_7":
        item_info = APPROVED_MARKET["vip_7"]
    else:
        item_info = APPROVED_MARKET.get(item_code)
        
    if not item_info:
        await call.answer("❌ Позиция недоступна", show_alert=True)
        return
    
    USER_PENDING_PURCHASE[call.from_user.id] = item_info.get("name", "Прогноз")

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
    if item_code == "vip_7":
        item_info = APPROVED_MARKET["vip_7"]
    else:
        item_info = APPROVED_MARKET.get(item_code, {})
    
    USER_PENDING_PURCHASE[call.from_user.id] = item_info.get("name", "Прогноз")

    await call.message.edit_text(
        f"💳 **Оплата через Kaspi**\nРеквизиты: `{KASPI_CARD}`\nСумма: {item_info.get('price_kz', 1500)} ₸\n\n📸 Отправьте скриншот чека в чат.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")]]), parse_mode="Markdown"
    )

@router.message(F.photo)
async def handle_receipt(message: Message):
    if message.from_user.id == MY_CHAT_ID:
        return
    user = message.from_user
    
    desired_product = USER_PENDING_PURCHASE.get(user.id, "❓ Товар не выбран в меню (покупка напрямую)")
    
    if user.username:
        user_link = f"@{user.username} (ссылка: t.me/{user.username})"
    else:
        user_link = f"[{user.first_name}](tg://user?id={user.id})"

    caption = (
        f"🔔 **Новый чек на оплату!**\n\n"
        f"🛍 **Выбранный товар:** <u>{desired_product}</u>\n\n"
        f"👤 **Клиент:** {user.first_name}\n"
        f"🔗 **Связь с клиентом:** {user_link}\n"
        f"🆔 **ID:** `{user.id}`"
    )
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Ординар", callback_data=f"grant_ordinary_{user.id}"),
            InlineKeyboardButton(text="🔥 Экспресс", callback_data=f"grant_express_{user.id}")
        ],
        [
            InlineKeyboardButton(text="💣 Хай-Кэф", callback_data=f"grant_high_odds_{user.id}"),
            InlineKeyboardButton(text="👑 VIP-7 (Активировать подписку)", callback_data=f"grant_vip_7_{user.id}")
        ]
    ])
    
    await message.bot.send_photo(chat_id=MY_CHAT_ID, photo=message.photo[-1].file_id, caption=caption, reply_markup=admin_kb, parse_mode="Markdown")
    await message.answer("✅ Чек успешно передан администратору!")

@router.callback_query(F.data.startswith("grant_"))
async def grant_product(call: CallbackQuery):
    if call.from_user.id != MY_CHAT_ID:
        return
    parts = call.data.split("_")
    if "high" in call.data:
        product_code = "high_odds"
        target_user_id = int(parts[-1])
    elif "vip" in call.data:
        product_code = "vip_7"
        target_user_id = int(parts[-1])
    else:
        product_code = parts[1]
        target_user_id = int(parts[-1])
        
    try:
        target_chat = await call.bot.get_chat(target_user_id)
        username = target_chat.username or "no_username"
        
        if product_code == "vip_7":
            # Активируем подписку в базе на 7 дней
            add_vip_user(target_user_id)
            
            # Отправляем текущую подборку
            await send_vip_bundle_to_user(call.bot, target_user_id, username)
            await call.answer("👑 VIP-подписка активирована на 7 дней! Прогнозы отправлены.")
        else:
            item_info = APPROVED_MARKET.get(product_code, {})
            content = item_info.get("content", "Доступно.")
            img_bio = generate_prediction_card(f"📦 {item_info.get('name', 'ПРОГНОЗ')}", content, target_user_id, username)
            await call.bot.send_photo(chat_id=target_user_id, photo=BufferedInputFile(img_bio.getvalue(), filename="paid.png"), caption="🎉 Оплата подтверждена! Ваш прогноз:")
            await call.answer("Успешно выдано клиенту!")
        
        if target_user_id in USER_PENDING_PURCHASE:
            del USER_PENDING_PURCHASE[target_user_id]
            
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@router.message(Command("schedule"))
async def admin_schedule(message: Message):
    if message.from_user.id != MY_CHAT_ID:
        return
    status_msg = await message.answer("⏳ Генерация расписания и линии через ESPN API...")
    report = await build_full_daily_report()
    PENDING_DRAFT["text"] = report
    
    ord_t = APPROVED_MARKET["ordinary"]["close_time"]
    exp_t = APPROVED_MARKET["express"]["close_time"]
    high_t = APPROVED_MARKET["high_odds"]["close_time"]
    
    moderation_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать и разослать VIP", callback_data="admin_approve_market")],
        [InlineKeyboardButton(text="⚙️ Настроить время по категориям", callback_data="admin_cat_time_menu")],
        [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="admin_retry_market")]
    ])
    
    await status_msg.edit_text(
        f"📋 **Черновик сформирован!**\nДедлайны: Ординар ({ord_t}) | Экспресс ({exp_t}) | Хай-Кэф ({high_t})\n\n{report}", 
        reply_markup=moderation_kb, 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_cat_time_menu")
async def admin_cat_time_menu(call: CallbackQuery):
    if call.from_user.id != MY_CHAT_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎯 Ординар (сейчас: {APPROVED_MARKET['ordinary']['close_time']})", callback_data="set_cat_ordinary")],
        [InlineKeyboardButton(text=f"🔥 Экспресс (сейчас: {APPROVED_MARKET['express']['close_time']})", callback_data="set_cat_express")],
        [InlineKeyboardButton(text=f"💣 Хай-Кэф (сейчас: {APPROVED_MARKET['high_odds']['close_time']})", callback_data="set_cat_high_odds")],
        [InlineKeyboardButton(text="◀️ Назад к публикации", callback_data="admin_back_to_publish")]
    ])
    await call.message.edit_text(
        "⚙️ **Выберите категорию прогноза для изменения дедлайна продаж:**",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("set_cat_"))
async def select_category_to_set(call: CallbackQuery):
    if call.from_user.id != MY_CHAT_ID:
        return
    cat_code = call.data.replace("set_cat_", "")
    ADMIN_STATE[call.from_user.id] = {"action": "setting_cat_time", "category": cat_code}
    
    names = {"ordinary": "Ординар дня", "express": "Экспресс 2-3", "high_odds": "Хай-Кэф Экспресс"}
    
    time_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="18:00", callback_data=f"timeval_18:00"),
            InlineKeyboardButton(text="19:00", callback_data=f"timeval_19:00"),
            InlineKeyboardButton(text="20:30", callback_data=f"timeval_20:30")
        ],
        [
            InlineKeyboardButton(text="21:00", callback_data=f"timeval_21:00"),
            InlineKeyboardButton(text="22:30", callback_data=f"timeval_22:30"),
            InlineKeyboardButton(text="⌨️ Ввести вручную", callback_data="timeval_custom")
        ],
        [InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="admin_cat_time_menu")]
    ])
    
    await call.message.edit_text(
        f"⏱ Выберите время дедлайна для: **{names.get(cat_code, cat_code)}**",
        reply_markup=time_kb
    )

@router.callback_query(F.data.startswith("timeval_"))
async def apply_time_value(call: CallbackQuery):
    if call.from_user.id != MY_CHAT_ID:
        return
    val = call.data.replace("timeval_", "")
    state_data = ADMIN_STATE.get(call.from_user.id, {})
    cat_code = state_data.get("category")
    
    if not cat_code:
        await call.answer("Ошибка сессии.", show_alert=True)
        return
        
    if val == "custom":
        ADMIN_STATE[call.from_user.id]["action"] = "waiting_custom_time"
        await call.message.answer(f"⌨️ Введите время дедлайна в формате `ЧЧ:ММ` (например, `19:15`):")
        await call.answer()
        return
        
    APPROVED_MARKET[cat_code]["close_time"] = val
    ADMIN_STATE[call.from_user.id] = None
    await show_category_menu_after_change(call.message)

async def show_category_menu_after_change(message: Message):
    ord_t = APPROVED_MARKET["ordinary"]["close_time"]
    exp_t = APPROVED_MARKET["express"]["close_time"]
    high_t = APPROVED_MARKET["high_odds"]["close_time"]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎯 Ординар ({ord_t})", callback_data="set_cat_ordinary")],
        [InlineKeyboardButton(text=f"🔥 Экспресс ({exp_t})", callback_data="set_cat_express")],
        [InlineKeyboardButton(text=f"💣 Хай-Кэф ({high_t})", callback_data="set_cat_high_odds")],
        [InlineKeyboardButton(text="◀️ Назад к публикации", callback_data="admin_back_to_publish")]
    ])
    await message.edit_text("✅ Время успешно обновлено! Настройте другую категорию или вернитесь назад:", reply_markup=kb)

@router.callback_query(F.data == "admin_back_to_publish")
async def admin_back_to_publish(call: CallbackQuery):
    if call.from_user.id != MY_CHAT_ID:
        return
    draft_text = PENDING_DRAFT.get("text", "Нет текста")
    ord_t = APPROVED_MARKET["ordinary"]["close_time"]
    exp_t = APPROVED_MARKET["express"]["close_time"]
    high_t = APPROVED_MARKET["high_odds"]["close_time"]
    
    moderation_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать и разослать VIP", callback_data="admin_approve_market")],
        [InlineKeyboardButton(text="⚙️ Настроить время по категориям", callback_data="admin_cat_time_menu")],
        [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="admin_retry_market")]
    ])
    await call.message.edit_text(
        f"📋 **Черновик линии:**\nДедлайны: Ординар ({ord_t}) | Экспресс ({exp_t}) | Хай-Кэф ({high_t})\n\n{draft_text}",
        reply_markup=moderation_kb,
        parse_mode="Markdown"
    )

@router.message(F.text & (F.from_user.id == MY_CHAT_ID))
async def admin_text_input(message: Message):
    state = ADMIN_STATE.get(message.from_user.id, {})
    if isinstance(state, dict) and state.get("action") == "waiting_custom_time":
        cat_code = state.get("category")
        text_time = message.text.strip()
        
        if ":" in text_time and len(text_time) <= 5:
            APPROVED_MARKET[cat_code]["close_time"] = text_time
            ADMIN_STATE[message.from_user.id] = None
            
            ord_t = APPROVED_MARKET["ordinary"]["close_time"]
            exp_t = APPROVED_MARKET["express"]["close_time"]
            high_t = APPROVED_MARKET["high_odds"]["close_time"]
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🎯 Ординар ({ord_t})", callback_data="set_cat_ordinary")],
                [InlineKeyboardButton(text=f"🔥 Экспресс ({exp_t})", callback_data="set_cat_express")],
                [InlineKeyboardButton(text=f"💣 Хай-Кэф ({high_t})", callback_data="set_cat_high_odds")],
                [InlineKeyboardButton(text="◀️ Назад к публикации", callback_data="admin_back_to_publish")]
            ])
            await message.answer(f"✅ Время установлено на **{text_time}**!", reply_markup=kb, parse_mode="Markdown")
        else:
            await message.answer("❌ Неверный формат. Введите в формате `ЧЧ:ММ`:")

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
    
    # АВТОМАТИЧЕСКАЯ РАССЫЛКА АКТИВНЫМ VIP-КЛИЕНТАМ
    vip_data = load_vip_users()
    sent_count = 0
    tz = zoneinfo.ZoneInfo("Asia/Almaty")
    now_dt = datetime.now(tz)
    
    for str_id, expire_str in vip_data.items():
        try:
            expire_dt = datetime.fromisoformat(expire_str)
            if now_dt < expire_dt:
                u_id = int(str_id)
                try:
                    # Пробуем отправить свежий VIP-пакет
                    await send_vip_bundle_to_user(call.bot, u_id, "vip_client")
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Не удалось отправить VIP рассылку пользователю {u_id}: {e}")
        except Exception:
            continue

    ord_t = APPROVED_MARKET["ordinary"]["close_time"]
    exp_t = APPROVED_MARKET["express"]["close_time"]
    high_t = APPROVED_MARKET["high_odds"]["close_time"]
    
    await call.message.edit_text(
        f"✅ **Линия одобрена, опубликована и разослана!**\n"
        f"👑 Автоматически отправлено активным VIP-клиентам: **{sent_count} чел.**\n"
        f"⏱ Дедлайны: Ординар ({ord_t}) | Экспресс ({exp_t}) | Хай-Кэф ({high_t})\n\n{draft_text}", 
        parse_mode="Markdown"
    )
    await call.answer("Опубликовано и разослано!")

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
            [InlineKeyboardButton(text="✅ Опубликовать и разослать VIP", callback_data="admin_approve_market")],
            [InlineKeyboardButton(text="⚙️ Настроить время по категориям", callback_data="admin_cat_time_menu")],
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
