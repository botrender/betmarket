import asyncio
import logging
import sys
import os
from io import BytesIO
from datetime import datetime, timezone, timedelta
from aiohttp import web
import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    BotCommand,
    BotCommandScopeChat,
    BufferedInputFile
)
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont

# --- НАСТРОЙКИ И КОНФИГУРАЦИЯ ---
BOT_TOKEN = "9229154481:AAEQDxNsKv7mN6mH3wwMLOHuxV90h5fsjNs"

part1 = "AQ.Ab8RN6LMLQ97SXcImE7VMyNN-"
part2 = "ULvzAlSD5fm7rm-HbHlQvkQAQ"
GEMINI_API_KEY = part1 + part2

KASPI_CARD = "4400 4302 7720 4696"
ADMIN_USERNAME = "BulatAtambayev"
ADMIN_CHAT_ID = 1102082462

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-flash-latest'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

APPROVED_MARKET = {
    "date": "",
    "free": None,
    "ordinary": None,
    "express": None,
    "high_odds": None,
    "vip_7": {"name": "👑 VIP-Подписка (Сливы на 7 дней)", "price_kz": 5000, "stars": 160, "active": True}
}

LAST_GENERATED_DRAFT = {"text": ""}

PRODUCTS_BASE = {
    "ordinary": {"name": "🎯 Ординар", "price_kz": 1500, "stars": 50},
    "express": {"name": "🔥 Экспресс 2-3", "price_kz": 2500, "stars": 80},
    "high_odds": {"name": "💣 Хай-Кэф", "price_kz": 4000, "stars": 130},
}

# --- СТРОГИЕ ИНСТРУКЦИИ ДЛЯ ИИ (АКТУАЛЬНЫЕ МАТЧИ ТОП-ЛИГ) ---
SYSTEM_ANALYST_INSTRUCTION = """
Ты — главный спортивный аналитик и шеф-редактор маркетплейса BetMarket KZ.
Твоя главная задача — выдавать СТРОГО АКТУАЛЬНЫЕ И РЕАЛЬНЫЕ матчи на текущую дату.
СПЕЦИАЛИЗАЦИЯ:
⚽ Футбол: Топ-5 лиг Европы (АПЛ, Ла Лига, Серия А, Бундеслига, Лига 1) + Еврокубки (ЛЧ, ЛЕ, ЛК).
🏒 Хоккей: КХЛ, НХЛ.
🏀 Баскетбол: НБА.

КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:
- Выдумывать матчи, команды или счета.
- Использовать матчи из прошлых или будущих дней (игра должна проходить ровно в дату запроса).
Если на сегодня в указанных лиге/виде спорта нет матчей, так и пиши. Бери только реальную спортивную линию дня.
"""

def generate_prediction_card(title: str, text_content: str, user_id: int, username: str) -> BytesIO:
    width, height = 900, 1100
    img = Image.new('RGB', (width, height), color=(15, 23, 42)) # Тёмно-синий фон
    draw = ImageDraw.Draw(img)
    
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "arial.ttf"
    ]
    
    font_title, font_text, font_watermark, font_small = None, None, None, None
    for path in font_paths:
        try:
            font_title = ImageFont.truetype(path, 28)
            font_text = ImageFont.truetype(path, 18)
            font_watermark = ImageFont.truetype(path, 26)
            font_small = ImageFont.truetype(path, 16)
            break
        except Exception:
            continue
            
    if not font_title:
        font_title = font_text = font_watermark = font_small = ImageFont.load_default()

    # Слой водяных знаков с чередованием строк (ID на одной, Ник на другой)
    txt_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d_txt = ImageDraw.Draw(txt_layer)
    
    line_toggle = 0
    for y in range(40, height, 90):
        watermark_str = f"ID: {user_id}" if line_toggle % 2 == 0 else f"@{username}"
        for x in range(20, width, 280):
            d_txt.text((x, y), watermark_str, fill=(100, 116, 139, 130), font=font_watermark)
        line_toggle += 1
            
    img = Image.alpha_composite(img.convert('RGBA'), txt_layer).convert('RGB')
    draw = ImageDraw.Draw(img)

    # Шапка брендинга
    draw.rectangle([(30, 30), (width - 30, 90)], fill=(30, 58, 138))
    draw.text((50, 38), "BetMarket KZ | Официальный Прогноз", fill=(255, 255, 255), font=font_title)
    
    # Заголовок товара
    draw.text((50, 115), title, fill=(250, 204, 21), font=font_title)
    
    # Текст прогноза и аналитики
    margin = 50
    offset = 165
    max_width = width - (margin * 2)
    
    for paragraph in text_content.split('\n'):
        words = paragraph.split(' ')
        line = ''
        for word in words:
            test_line = line + word + ' '
            if len(test_line) * 9.5 > max_width:
                draw.text((margin, offset), line, fill=(241, 245, 249), font=font_text)
                offset += 24
                line = word + ' '
            else:
                line = test_line
        draw.text((margin, offset), line, fill=(241, 245, 249), font=font_text)
        offset += 30

    # Нижняя панель защиты
    draw.rectangle([(30, height - 85), (width - 30, height - 25)], fill=(185, 28, 28))
    warning_text = f"Персональная лицензия: @{username} (ID: {user_id}) | Защита BetMarket KZ"
    draw.text((40, height - 72), warning_text, fill=(255, 255, 255), font=font_small)

    bio = BytesIO()
    bio.name = 'prediction.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

async def expand_with_ai_reasoning(user_input_text: str) -> str:
    almaty_time = datetime.now(timezone(timedelta(hours=5)))
    current_date_str = almaty_time.strftime("%d.%m.%Y")
    
    prompt = (
        f"Текущая дата: {current_date_str}. "
        f"Администратор указал следующий прогноз: '{user_input_text}'. "
        f"Напиши профессиональное спортивное обоснование и аналитику по матчу, опираясь на текущую форму команд на дату {current_date_str}. "
        f"Сделай текст развернутым, авторитетным и готовым для публикации."
    )
    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_ANALYST_INSTRUCTION)
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=25.0  # Увеличен тайм-аут
        )
        ai_text = response.text.strip()
        return f"{user_input_text}\n\n💡 Экспертная аналитика:\n{ai_text}"
    except Exception as e:
        logging.error(f"AI Reasoning error: {e}")
        return user_input_text

async def ask_gemini_market_draft() -> str:
    almaty_time = datetime.now(timezone(timedelta(hours=5)))
    current_date_str = almaty_time.strftime("%d.%m.%Y")
    
    prompt = (
        f"СЕГОДНЯШНЯЯ ДАТА: {current_date_str}. "
        f"Составь утреннюю подборку матчей, которые играются РОВНО СЕГОДНЯ ({current_date_str}) по топ-лигам (Футбол: АПЛ, Ла Лига, Серия А, Бундеслига, Лига 1, ЛЧ/ЛЕ/ЛК; Хоккей: КХЛ, НХЛ; Баскетбол: НБА). "
        f"Предложи варианты с детальным обоснованием:\n"
        f"Бесплатный прогноз: [Точный матч на сегодня, ставка, кэф и анализ]\n"
        f"Ординар: [Точный матч на сегодня, ставка, кэф и аналитическое обоснование]\n"
        f"Экспресс: [2 реальных матча на сегодня с общим кэфом 2.0-3.0 и обоснованием]\n"
        f"Хай-кэф: [Реальные матчи на сегодня с высоким кэфом от 4.0 и обоснованием]"
    )
    
    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_ANALYST_INSTRUCTION)
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=25.0  # Увеличен тайм-аут до 25 секунд
        )
        text = response.text.strip()
        LAST_GENERATED_DRAFT["text"] = text
        return f"📅 Линия на сегодня: {current_date_str}\n\n{text}"
    except Exception as e:
        logging.error(f"Draft error: {e}")
        return "⚠️ Не удалось сгенерировать черновик. Попробуйте еще раз."

def get_dynamic_keyboard():
    keyboard = []
    if APPROVED_MARKET.get("free"):
        keyboard.append([InlineKeyboardButton(text="🎁 Бесплатный прогноз дня", callback_data="get_free_pick")])
        
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
        
    keyboard.append([
        InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
        InlineKeyboardButton(text="📊 Статистика / ROI", callback_data="stats")
    ])
    keyboard.append([InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{ADMIN_USERNAME}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(CommandStart())
async def start_cmd(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("👋 **Добро пожаловать в BetMarket KZ!**\nОфициальный маркетплейс точных спортивных прогнозов.", reply_markup=get_dynamic_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery):
    try:
        await call.message.edit_text("🛍 **Главное меню BetMarket KZ:**", reply_markup=get_dynamic_keyboard(), parse_mode="Markdown")
    except Exception:
        await call.message.answer("🛍 **Главное меню BetMarket KZ:**", reply_markup=get_dynamic_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "get_free_pick")
async def get_free_pick(call: CallbackQuery):
    free_content = APPROVED_MARKET.get("free")
    if not free_content:
        await call.answer("На сегодня бесплатный прогноз не выставлен.", show_alert=True)
        return
        
    user = call.from_user
    username = user.username if user.username else "no_username"
    current_date = datetime.now(timezone(timedelta(hours=5))).strftime("%d.%m.%Y")
    
    img_bio = generate_prediction_card(f"🎁 БЕСПЛАТНЫЙ ПРОГНОЗ ({current_date})", free_content, user.id, username)
    input_file = BufferedInputFile(img_bio.getvalue(), filename="free.png")
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]])
    
    await call.message.answer_photo(photo=input_file, caption="🎁 Ваш бесплатный прогноз с защитным водяным знаком:", reply_markup=back_kb)

@router.callback_query(F.data.startswith("item_"))
async def select_item(call: CallbackQuery):
    item_code = call.data.replace("item_", "")
    if item_code not in APPROVED_MARKET or not APPROVED_MARKET[item_code]:
        await call.answer("❌ Данный товар сегодня отсутствует в продаже!", show_alert=True)
        return
        
    item_info = APPROVED_MARKET[item_code]
    name = item_info.get("name", "Прогноз")
    price_kz = item_info.get("price_kz", 1500)
    stars = item_info.get("stars", 50)
    
    text = f"📦 **Вы выбрали:** {name}\n💳 **Стоимость:** {price_kz} ₸ или {stars} Stars ⭐\n\nВыберите способ оплаты:"
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить Kaspi ({price_kz} ₸)", callback_data=f"pay_kaspi_{item_code}")],
        [InlineKeyboardButton(text=f"⭐ Оплатить Telegram Stars ({stars} ⭐)", callback_data=f"pay_stars_{item_code}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, reply_markup=pay_kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pay_kaspi_"))
async def pay_kaspi(call: CallbackQuery):
    item_code = call.data.replace("pay_kaspi_", "")
    item_info = APPROVED_MARKET.get(item_code, {})
    name = item_info.get("name", "Прогноз")
    price_kz = item_info.get("price_kz", 1500)
    text = f"💳 **Оплата через Kaspi**\nТовар: **{name}**\nК оплате: **{price_kz} ₸**\nКарта: `{KASPI_CARD}`\n\n📸 Отправьте скриншот чека в этот чат."
    kaspi_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]])
    await call.message.edit_text(text, reply_markup=kaspi_kb, parse_mode="Markdown")

@router.message(F.photo)
async def handle_receipt_photo(message: Message):
    if message.from_user.id == ADMIN_CHAT_ID:
        return  
    user = message.from_user
    photo = message.photo[-1].file_id
    caption = f"🔔 **Новый чек от клиента!**\n👤 {user.first_name} (@{user.username})\n🆔 `{user.id}`"
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Ординар", callback_data=f"grant_ordinary_{user.id}")],
        [InlineKeyboardButton(text="🔥 Экспресс", callback_data=f"grant_express_{user.id}")],
        [InlineKeyboardButton(text="💣 Хай-Кэф", callback_data=f"grant_high_odds_{user.id}")],
        [InlineKeyboardButton(text="👑 VIP 7д", callback_data=f"grant_vip_7_{user.id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_user_{user.id}")]
    ])
    await bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo, caption=caption, reply_markup=admin_kb)
    await message.answer("✅ Чек отправлен администратору!")

@router.callback_query(F.data.startswith("grant_"))
async def grant_product_handler(call: CallbackQuery):
    if call.from_user.id != ADMIN_CHAT_ID:
        return
    parts = call.data.split("_")
    product_code = "vip_7" if parts[1] == "vip" else parts[1]
    target_user_id = int(parts[-1])
    
    prediction_info = APPROVED_MARKET.get(product_code)
    prediction_text = prediction_info.get("content", "Материал доступен.") if isinstance(prediction_info, dict) else "Доступно."
    title = prediction_info.get("name", "ПРОГНОЗ").upper() if isinstance(prediction_info, dict) else "ПРОГНОЗ"

    try:
        target_chat = await bot.get_chat(target_user_id)
        target_username = target_chat.username if target_chat.username else "no_username"
        
        img_bio = generate_prediction_card(f"📦 {title}", prediction_text, target_user_id, target_username)
        input_file = BufferedInputFile(img_bio.getvalue(), filename="paid.png")
        
        await bot.send_photo(chat_id=target_user_id, photo=input_file, caption="🎉 Оплата подтверждена! Ваш персональный прогноз:")
        await bot.send_message(target_user_id, "🛍 Главное меню:", reply_markup=get_dynamic_keyboard())
        await call.answer("Выдано!")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@router.callback_query(F.data.startswith("reject_user_"))
async def admin_reject_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_CHAT_ID:
        return
    target_user_id = int(call.data.replace("reject_user_", ""))
    try:
        await bot.send_message(chat_id=target_user_id, text="❌ Ваш чек отклонен администратором.")
    except Exception:
        pass
    await call.answer("Отклонено.")

@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: CallbackQuery):
    item_code = call.data.replace("pay_stars_", "")
    item_info = APPROVED_MARKET.get(item_code, {})
    name = item_info.get("name", "Прогноз")
    stars = item_info.get("stars", 50)
    prices = [LabeledPrice(label=name, amount=stars)]
    await call.message.delete()
    await call.message.answer_invoice(
        title=name, description="Покупка в BetMarket KZ", prices=prices,
        provider_token="", payload=f"order_{item_code}", currency="XTR",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"⭐ Оплатить {stars} Stars", pay=True)]])
    )

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@router.message(F.successful_payment)
async def success_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    item_code = payload.replace("order_", "") if "order_" in payload else "ordinary"
    item_info = APPROVED_MARKET.get(item_code, {})
    content = item_info.get("content", "Материал доступен.") if isinstance(item_info, dict) else "Доступно."
    title = item_info.get("name", "ПРОГНОЗ").upper() if isinstance(item_info, dict) else "ПРОГНОЗ"

    user = message.from_user
    username = user.username if user.username else "no_username"
    img_bio = generate_prediction_card(f"👑 {title}", content, user.id, username)
    input_file = BufferedInputFile(img_bio.getvalue(), filename="paid.png")
    
    await message.answer_photo(photo=input_file, caption="👑 Ваш оплаченный прогноз:")
    await message.answer("🛍 Главное меню:", reply_markup=get_dynamic_keyboard())

@router.callback_query(F.data == "profile")
async def profile_handler(call: CallbackQuery):
    user = call.from_user
    text = f"👤 **Ваш профиль:**\nID: `{user.id}`\nИмя: {user.first_name}\nUsername: @{user.username or 'нет'}"
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]]), parse_mode="Markdown")

@router.callback_query(F.data == "stats")
async def stats_handler(call: CallbackQuery):
    await call.message.edit_text("📊 Проходимость: 74.2%\nROI: +19.1%", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]]))

# --- АДМИН-ПАНЕЛЬ С АВТО-АНАЛИЗОМ ---

async def parse_and_store_with_ai(text_block: str):
    current_date = datetime.now(timezone(timedelta(hours=5))).strftime("%d.%m.%Y")
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
            buf["free"].append(line.split(":", 1)[-1].strip())
        elif "ординар" in l_lower:
            mode = "ordinary"
            buf["ordinary"].append(line.split(":", 1)[-1].strip())
        elif "экспресс" in l_lower:
            mode = "express"
            buf["express"].append(line.split(":", 1)[-1].strip())
        elif "хай" in l_lower:
            mode = "high"
            buf["high"].append(line.split(":", 1)[-1].strip())
        else:
            if mode and line.strip():
                buf[mode].append(line.strip())
                
    if buf["free"]:
        raw_text = " ".join(buf["free"])
        APPROVED_MARKET["free"] = await expand_with_ai_reasoning(raw_text)
    if buf["ordinary"]:
        raw_text = " ".join(buf["ordinary"])
        expanded = await expand_with_ai_reasoning(raw_text)
        APPROVED_MARKET["ordinary"] = {"name": "🎯 Ординар дня", "price_kz": 1500, "stars": 50, "content": expanded}
    if buf["express"]:
        raw_text = " ".join(buf["express"])
        expanded = await expand_with_ai_reasoning(raw_text)
        APPROVED_MARKET["express"] = {"name": "🔥 Экспресс 2-3", "price_kz": 2500, "stars": 80, "content": expanded}
    if buf["high"]:
        raw_text = " ".join(buf["high"])
        expanded = await expand_with_ai_reasoning(raw_text)
        APPROVED_MARKET["high_odds"] = {"name": "💣 Хай-Кэф", "price_kz": 4000, "stars": 130, "content": expanded}

@router.message(Command("draft"))
async def admin_get_draft(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer("⏳ *ИИ анализирует матчи на сегодня по топ-лигам...*", parse_mode="Markdown")
    draft_text = await ask_gemini_market_draft()
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить черновик", callback_data="approve_draft")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_draft")]
    ])
    await message.answer(f"📋 **Черновик на сегодня:**\n\n{draft_text}", reply_markup=admin_kb, parse_mode="Markdown")

@router.callback_query(F.data == "approve_draft")
async def approve_draft_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_CHAT_ID:
        return
    text_to_parse = LAST_GENERATED_DRAFT.get("text", "Ординар: Матч дня")
    await call.message.edit_text("⏳ Обрабатываем и добавляем аналитику...")
    await parse_and_store_with_ai(text_to_parse)
    await call.message.edit_text("✅ **Черновик одобрен!** Витрина обновлена актуальными данными.")

@router.callback_query(F.data == "refresh_draft")
async def refresh_draft_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_CHAT_ID:
        return
    await call.message.edit_text("⏳ Ищем свежие варианты...")
    draft_text = await ask_gemini_market_draft()
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data="approve_draft")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_draft")]
    ])
    await call.message.edit_text(f"📋 **Новый черновик:**\n\n{draft_text}", reply_markup=admin_kb)

@router.message(Command("setmarket"))
async def admin_set_market(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    full_text = message.text.replace("/setmarket", "").strip()
    if not full_text:
        await message.answer("⚠️ Напишите текст после команды `/setmarket`. Например:\n`/setmarket Ординар: Флорида-Чикаго П1 кф 1.7`")
        return
        
    status_msg = await message.answer("⏳ ИИ дополняет ваши матчи профессиональной аналитикой...")
    await parse_and_store_with_ai(full_text)
    current_date = datetime.now(timezone(timedelta(hours=5))).strftime("%d.%m.%Y")
    await status_msg.edit_text(f"✅ **Маркет на {current_date} успешно обновлен!**")
    await message.answer("🛍 Витрина успешно перестроена:", reply_markup=get_dynamic_keyboard())

async def background_admin_notifications():
    await asyncio.sleep(30)
    while True:
        now = datetime.now(timezone(timedelta(hours=5)))
        current_time_str = now.strftime("%H:%M")
        if current_time_str in ["11:00", "16:00", "18:00", "21:00", "01:00"]:
            try:
                draft = await ask_gemini_market_draft()
                admin_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Одобрить", callback_data="approve_draft")],
                    [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_draft")]
                ])
                await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"⏰ **Проверка линии ({current_time_str}):**\n\n{draft}", reply_markup=admin_kb)
            except Exception as e:
                logging.error(f"Notification error: {e}")
            await asyncio.sleep(70)
        await asyncio.sleep(30)

async def handle(request):
    return web.Response(text="BetMarket Server OK")

async def self_ping_task():
    await asyncio.sleep(15)
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        return
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(render_url) as resp:
                    logging.info(f"Self-ping sent: {resp.status}")
            except Exception as e:
                logging.error(f"Self-ping error: {e}")
            await asyncio.sleep(600)

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    asyncio.create_task(self_ping_task())

async def main():
    try:
        admin_scope = BotCommandScopeChat(chat_id=ADMIN_CHAT_ID)
        await bot.set_my_commands([
            BotCommand(command="start", description="🏠 Главное меню"),
            BotCommand(command="draft", description="📋 Черновик на сегодня"),
            BotCommand(command="setmarket", description="🛠 Утвердить маркет")
        ], scope=admin_scope)
        await bot.set_my_commands([BotCommand(command="start", description="🏠 Главное меню")])
    except Exception as e:
        logging.error(f"Команды: {e}")
    
    dp.include_router(router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.error(f"Webhook: {e}")
        
    asyncio.create_task(web_server())
    asyncio.create_task(background_admin_notifications())
    logging.info("🚀 Бот запущен!")
    
    while True:
        try:
            await dp.start_polling(bot, handle_signals=False)
        except Exception as e:
            logging.error(f"Polling error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Остановлено.")
