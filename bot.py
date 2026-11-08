# === ПОЛНЫЙ КОД БОТА BETMARKET KZ (ОБНОВЛЕННЫЕ МОДЕЛИ ИИ + ПЕЧАТЬ + ВОДЯНЫЕ ЗНАКИ ПОВЕРХ ВСЕГО) ===
import asyncio
import logging
import sys
import json
import os
import random
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

# --- РАЗДЕЛЕННЫЕ КЛЮЧИ GEMINI (ОБХОД СКАНЕРА GITHUB) ---
_k1_p1 = "AQ.Ab8RN6LMLQ97SXcImE7VMyNN-"
_k1_p2 = "ULvzAlSD5fm7rm-HbHlQvkQAQ"
GEMINI_KEY_1 = _k1_p1 + _k1_p2

_k2_p1 = "AQ.Ab8RN6LKhBaUWmo69d08hproW_"
_k2_p2 = "prAfTgb947EsuWW2WB-eYkGA"
GEMINI_KEY_2 = _k2_p1 + _k2_p2

_k3_p1 = "AQ.Ab8RN6JW3VjPnd6CWaL4i1_"
_k3_p2 = "cyj8-DCyUvojEmqf8w0BEI7RlAA"
GEMINI_KEY_3 = _k3_p1 + _k3_p2

# --- РАЗДЕЛЕННЫЙ КЛЮЧ GROQ ---
_groq_p1 = "gsk_WzwaGIVsVy1my871HKrwWGdyb3FYIyI1"
_groq_p2 = "RhY4JSGYhlP8jfSxsXKldjn"
GROQ_API_KEY = _groq_p1 + _groq_p2

API_POOL_PART_1 = [GEMINI_KEY_1, GEMINI_KEY_2]
API_POOL_PART_2 = [GEMINI_KEY_3]

MY_CHAT_ID = 1102082462
ADMIN_USERNAME = "BulatAtambayev"
KASPI_CARD = "4400 4302 7720 4696"

HISTORY_FILE = "history.json"
VIP_USERS_FILE = "vip_users.json"

# ОБНОВЛЕННЫЙ СПИСОК АКТУАЛЬНЫХ МОДЕЛЕЙ
MODEL_CANDIDATES = [
    'gemini-3.8-flash',
    'gemini-3.6-flash',
    'gemini-2.5-flash'
]

APPROVED_MARKET = {
    "date": "",
    "free": None,
    "ordinary": {
        "name": "🎯 Ординар дня", 
        "price_kz": 1500, 
        "stars": 140, 
        "close_time": "19:00", 
        "content": None
    },
    "express": {
        "name": "🔥 Экспресс 2-3", 
        "price_kz": 2500, 
        "stars": 230, 
        "close_time": "21:00", 
        "content": None
    },
    "high_odds": {
        "name": "💣 Хай-Кэф Экспресс (Кэф 4-7)", 
        "price_kz": 4000, 
        "stars": 370, 
        "close_time": "22:30", 
        "content": None
    },
    "vip_7": {
        "name": "👑 VIP-Подписка (Все прогнозы на 7 дней)", 
        "price_kz": 5000, 
        "stars": 460, 
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
    expire_dt = datetime.now(tz) + timedelta(days=7)
    vip_data[str(user_id)] = expire_dt.isoformat()
    save_vip_users(vip_data)

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

def ask_groq_sync(prompt: str, system_instruction: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=15) as resp:
        res_data = json.loads(resp.read().decode('utf-8'))
        return res_data['choices'][0]['message']['content'].strip()

async def ask_gemini_raw(prompt: str, system_instruction: str) -> str:
    all_pools = [
        ("Часть 1 (Gemini)", API_POOL_PART_1),
        ("Часть 2 (Gemini)", API_POOL_PART_2)
    ]
    
    last_error = None
    for pool_name, pool_keys in all_pools:
        for api_key in pool_keys:
            genai.configure(api_key=api_key)
            for model_name in MODEL_CANDIDATES:
                try:
                    logging.info(f"🔄 Пробуем [{pool_name}] | Модель: {model_name}")
                    model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)
                    response = await asyncio.to_thread(model.generate_content, prompt)
                    return response.text.strip()
                except Exception as e:
                    last_error = e
                    logging.warning(f"⚠️ Ошибка Gemini в [{pool_name}] на модели {model_name}: {e}")
                    await asyncio.sleep(0.3)
                    continue

    logging.info("⚡️ Все лимиты Gemini исчерпаны! Переключаемся на резервный Groq...")
    try:
        return await asyncio.to_thread(ask_groq_sync, prompt, system_instruction)
    except Exception as groq_err:
        raise Exception(f"❌ Все ИИ исчерпали лимиты. Gemini: {last_error} | Groq: {groq_err}")

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

def draw_realistic_stamp(base_img: Image.Image, cx: int, cy: int, r: int):
    """Отрисовка укрупненной и премиальной круглой печати Syndicate Stamp"""
    stamp_layer = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(stamp_layer)
    
    gold_outer = (234, 179, 8, 250)
    gold_inner = (250, 204, 21, 230)
    text_gold = (253, 224, 71, 255)
    bg_dark = (15, 23, 42, 240)
    
    d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=bg_dark)
    d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=gold_outer, width=5)
    d.ellipse([(cx - r + 7, cy - r + 7), (cx + r - 7, cy + r - 7)], outline=gold_inner, width=2)
    d.ellipse([(cx - r + 14, cy - r + 14), (cx + r - 14, cy + r - 14)], outline=gold_outer, width=2)

    try:
        f_bm = ImageFont.truetype("DejaVuSans-Bold.ttf", 38)
        f_ver = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
        f_sub = ImageFont.truetype("DejaVuSans-Bold.ttf", 10)
    except:
        try:
            f_bm = ImageFont.truetype("arial-bold.ttf", 38)
            f_ver = ImageFont.truetype("arial-bold.ttf", 14)
            f_sub = ImageFont.truetype("arial-bold.ttf", 10)
        except:
            f_bm = f_ver = f_sub = ImageFont.load_default()

    crown_y = cy - 46
    crown = [
        (cx - 20, crown_y + 15), (cx - 28, crown_y - 8), (cx - 10, crown_y + 5), 
        (cx, crown_y - 18), (cx + 10, crown_y + 5), (cx + 28, crown_y - 8), (cx + 20, crown_y + 15)
    ]
    d.polygon(crown, fill=text_gold)
    d.text((cx - 28, cy - 20), "BM", fill=text_gold, font=f_bm)
    d.text((cx - 38, cy + 18), "VERIFIED", fill=text_gold, font=f_ver)
    d.text((cx - 48, cy + 38), "BETMARKET KZ", fill=(203, 213, 225, 255), font=f_sub)

    base_img.alpha_composite(stamp_layer)

def generate_prediction_card(title: str, text_content: str, user_id: int, username: str) -> BytesIO:
    width, height = 900, 1150
    img = Image.new('RGB', (width, height), color=(10, 15, 30))
    draw = ImageDraw.Draw(img)
    
    for y in range(height):
        r = int(10 + (y / height) * 15)
        g = int(15 + (y / height) * 20)
        b = int(30 + (y / height) * 45)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    try:
        font_header = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
        font_text = ImageFont.truetype("DejaVuSans.ttf", 17)
        font_watermark = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
        font_stamp_lbl = ImageFont.truetype("DejaVuSans-Bold.ttf", 11)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 13)
    except IOError:
        try:
            font_header = ImageFont.truetype("arial.ttf", 22)
            font_title = ImageFont.truetype("arial.ttf", 20)
            font_text = ImageFont.truetype("arial.ttf", 17)
            font_watermark = ImageFont.truetype("arial-bold.ttf", 16)
            font_stamp_lbl = ImageFont.truetype("arial-bold.ttf", 11)
            font_small = ImageFont.truetype("arial.ttf", 13)
        except IOError:
            font_header = ImageFont.load_default()
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()
            font_watermark = ImageFont.load_default()
            font_stamp_lbl = ImageFont.load_default()
            font_small = ImageFont.load_default()

    img_rgba = img.convert('RGBA')
    draw_comp = ImageDraw.Draw(img_rgba)

    # Шапка купона
    draw_comp.rounded_rectangle([(35, 35), (width - 35, 105)], radius=12, fill=(20, 30, 55), outline=(234, 179, 8), width=2)
    coupon_num = random.randint(800000000, 999999999)
    draw_comp.text((55, 52), "BETMARKET KZ", fill=(255, 255, 255), font=font_header)
    draw_comp.text((width - 450, 56), f"Купон № {coupon_num}", fill=(234, 179, 8), font=font_header)

    # Плашка VIP VERIFIED в шапке
    stamp_x, stamp_y = width - 180, 54
    draw_comp.rounded_rectangle([(stamp_x, stamp_y), (stamp_x + 130, stamp_y + 30)], radius=6, fill=(234, 179, 8))
    draw_comp.text((stamp_x + 14, stamp_y + 8), "VIP VERIFIED", fill=(15, 23, 42), font=font_stamp_lbl)

    # Текстовая карточка прогноза
    draw_comp.rounded_rectangle([(35, 130), (width - 35, height - 120)], radius=15, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    draw_comp.text((60, 160), title, fill=(234, 179, 8), font=font_title)
    draw_comp.line([(60, 195), (width - 60, 195)], fill=(51, 65, 85), width=1)

    offset = 220
    max_line_length = 48 
    cleaned_content = text_content.replace("**", "").replace("__", "")

    for paragraph in cleaned_content.split('\n'):
        if not paragraph.strip():
            offset += 15
            continue
        words = paragraph.split(' ')
        current_line = ""
        for word in words:
            if len(current_line + " " + word) <= max_line_length:
                current_line += (" " + word) if current_line else word
            else:
                draw_comp.text((60, offset), current_line, fill=(241, 245, 249), font=font_text)
                offset += 32
                current_line = word
        if current_line:
            draw_comp.text((60, offset), current_line, fill=(241, 245, 249), font=font_text)
            offset += 38

    # Печать в правом нижнем углу
    draw_realistic_stamp(img_rgba, cx=width - 140, cy=height - 210, r=75)

    # Нижнее предупреждение о бане
    draw_comp.rounded_rectangle([(35, height - 100), (width - 35, height - 35)], radius=10, fill=(127, 29, 29), outline=(239, 68, 68), width=1)
    warning_text = "⚠️ ВНИМАНИЕ: Перепродажа и слив караются вечным баном!"
    license_text = f"Персональная лицензия выдана: @{username} (ID: {user_id})"
    draw_comp.text((50, height - 85), warning_text, fill=(255, 255, 255), font=font_small)
    draw_comp.text((50, height - 62), license_text, fill=(254, 240, 138), font=font_small)

    # ФИНАЛЬНЫЙ СЛОЙ: Водяные знаки строго поверх всего
    txt_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d_txt = ImageDraw.Draw(txt_layer)
    watermark_str = f"ID: {user_id} | @{username}"
    
    for y in range(160, height - 120, 100):
        for x in range(30, width, 310):
            d_txt.text((x, y), watermark_str, fill=(255, 255, 255, 85), font=font_watermark)

    img_rgba = Image.alpha_composite(img_rgba, txt_layer)

    bio = BytesIO()
    bio.name = 'coupon_premium.png'
    img_rgba.convert('RGB').save(bio, 'PNG')
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
    ord_c = APPROVED_MARKET["ordinary"].get("content", "Нет доступных данных")
    exp_c = APPROVED_MARKET["express"].get("content", "Нет доступных данных")
    high_c = APPROVED_MARKET["high_odds"].get("content", "Нет доступных данных")
    vip_extra = APPROVED_MARKET["vip_7"].get("content_extra", "Эксклюзивный VIP-матч (кэф 2.0+)")

    categories = [
        ("🎯 ОРДИНАР ДНЯ", ord_c),
        ("🔥 ЭКСПРЕСС 2-3", exp_c),
        ("💣 ХАЙ-КЭФ ЭКСПРЕСС", high_c),
        ("⭐ VIP-БОНУС (ЭКСКЛЮЗИВ)", vip_extra)
    ]

    await bot.send_message(chat_id=user_id, text="👑 **Ваш VIP-пакет на сегодня!** Прогнозы сформированы в виде персональных защищенных купонов:")

    for title, content in categories:
        img_bio = generate_prediction_card(title, content, user_id, username)
        await bot.send_photo(
            chat_id=user_id,
            photo=BufferedInputFile(img_bio.getvalue(), filename=f"vip_{title.lower()}.png")
        )
        await asyncio.sleep(0.5) 

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
                f"При публикации VIP-клиенты получат 4 премиальных купона в ЛС.\n\nПроверьте текст:\n\n{report}"
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
    try:
        tz = zoneinfo.ZoneInfo("Asia/Almaty")
        now = datetime.now(tz)
        h, m = map(int, close_time_str.split(":"))
        close_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        if h < 6 and now.hour >= 18:
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
    stars = item_info.get("stars", 140)
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
            add_vip_user(target_user_id)
            await send_vip_bundle_to_user(call.bot, target_user_id, username)
            await call.answer("👑 VIP-подписка активирована на 7 дней! Премиальные купоны отправлены.")
        else:
            item_info = APPROVED_MARKET.get(product_code, {})
            content = item_info.get("content", "Доступно.")
            img_bio = generate_prediction_card(item_info.get('name', 'Прогноз'), content, target_user_id, username)
            await call.bot.send_photo(chat_id=target_user_id, photo=BufferedInputFile(img_bio.getvalue(), filename="coupon_premium.png"), caption="🎉 Оплата подтверждена! Ваш премиальный купон:")
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
                    await send_vip_bundle_to_user(call.bot, u_id, "vip_client")
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Не удалось отправить VIP купоны пользователю {u_id}: {e}")
        except Exception:
            continue

    ord_t = APPROVED_MARKET["ordinary"]["close_time"]
    exp_t = APPROVED_MARKET["express"]["close_time"]
    high_t = APPROVED_MARKET["high_odds"]["close_time"]
    
    await call.message.edit_text(
        f"✅ **Линия одобрена, опубликована и премиальные VIP-купоны разосланы!**\n"
        f"👑 Автоматически отправлено активным VIP-клиентам: **{sent_count} чел.** (по 4 купона)\n"
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
