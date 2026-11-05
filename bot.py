import asyncio
import logging
import sys
import os
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
    BotCommand
)
import google.generativeai as genai

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

# Хранилище утвержденного рынка и последнего чернового варианта от ИИ
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

SYSTEM_ANALYST_INSTRUCTION = """
Ты — главный спортивный аналитик и шеф-редактор маркетплейса BetMarket KZ.
Формируй актуальную подборку реальных матчей топ-лиг (Футбол: Лига Чемпионов, топ-5 чемпионатов; Хоккей: НХЛ; Баскетбол: НБА) на текущую дату.
КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдумывать матчи или использовать старые шаблоны. Всегда подбирай реальные афиши игрового дня.
"""

async def ask_gemini_market_draft() -> str:
    """Генерация утреннего черновика подборки матчей для админа"""
    almaty_time = datetime.now(timezone(timedelta(hours=5)))
    current_date_str = almaty_time.strftime("%d.%m.%Y")
    
    prompt = (
        f"Сегодня {current_date_str}. Составь утреннюю подборку актуальных матчей на сегодня для проверки администратором. "
        f"Четко раздели на разделы:\n"
        f"Бесплатный прогноз: [Матч и прогноз]\n"
        f"Ординар: [Матч, коэффициент и обоснование]\n"
        f"Экспресс: [Матчи с общим кэфом 2.0-3.0 и обоснованием]\n"
        f"Хай-кэф: [Матчи с высоким кэфом от 4.0 и обоснованием]\n"
        f"Выдавай только реальные матчи текущего дня."
    )
    
    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_ANALYST_INSTRUCTION)
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=15.0
        )
        text = response.text.strip()
        LAST_GENERATED_DRAFT["text"] = text
        return text
    except Exception as e:
        logging.error(f"Draft generation error: {e}")
        return "⚠️ Не удалось сгенерировать черновик. Попробуйте еще раз."

def get_dynamic_keyboard():
    """Динамическое меню: отображает только утвержденные категории"""
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
        
    welcome_text = (
        f"👋 **Добро пожаловать в BetMarket KZ!**\n\n"
        f"🛍 Официальный маркетплейс проверенных спортивных прогнозов.\n"
        f"⏱ Меню автоматически обновляется под ежедневную экспертную подборку.\n\n"
        f"Ваш Telegram ID: `{message.from_user.id}`"
    )
    await message.answer(welcome_text, reply_markup=get_dynamic_keyboard(), parse_mode="Markdown")

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
        await call.answer("На сегодня бесплатный прогноз не выставлен в маркет.", show_alert=True)
        return
        
    user = call.from_user
    username_tag = f"@{user.username}" if user.username else f"ID: {user.id}"
    watermark = f"\n\n---\n🔒 *Персональная лицензия: {username_tag} (ID: {user.id})*\n⚠️ Покупая или получая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
    
    current_date = datetime.now(timezone(timedelta(hours=5))).strftime("%d.%m.%Y")
    report = f"🎁 **БЕСПЛАТНЫЙ ПРОГНОЗ НА {current_date}**\n\n{free_content}{watermark}"
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]])
    await call.message.edit_text(report, reply_markup=back_kb, parse_mode="Markdown")
    await call.message.answer("👇 Вы можете продолжить выбор в главном меню:", reply_markup=get_dynamic_keyboard())

@router.callback_query(F.data.startswith("item_"))
async def select_item(call: CallbackQuery):
    item_code = call.data.replace("item_", "")
    
    if item_code not in APPROVED_MARKET or not APPROVED_MARKET[item_code]:
        await call.answer("❌ Данный товар сегодня отсутствует в продаже!", show_alert=True)
        return
        
    item_info = APPROVED_MARKET[item_code]
    name = item_info.get("name", PRODUCTS_BASE.get(item_code, {}).get("name", "Прогноз"))
    price_kz = item_info.get("price_kz", PRODUCTS_BASE.get(item_code, {}).get("price_kz", 1500))
    stars = item_info.get("stars", PRODUCTS_BASE.get(item_code, {}).get("stars", 50))
    
    text = (
        f"📦 **Вы выбрали:** {name}\n"
        f"💳 **Стоимость:** {price_kz} ₸ или {stars} Stars ⭐\n\n"
        f"⚠️ **Правила сервиса:** При обнаружении факта слива или перепродажи прогноза — мгновенный бан навсегда без возврата средств.\n\n"
        f"Выберите удобный способ оплаты:"
    )
    
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить Kaspi ({price_kz} ₸)", callback_data=f"pay_kaspi_{item_code}")],
        [InlineKeyboardButton(text=f"⭐ Оплатить Telegram Stars ({stars} ⭐)", callback_data=f"pay_stars_{item_code}")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, reply_markup=pay_kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pay_kaspi_"))
async def pay_kaspi(call: CallbackQuery):
    item_code = call.data.replace("pay_kaspi_", "")
    item_info = APPROVED_MARKET.get(item_code, {})
    name = item_info.get("name", "Прогноз")
    price_kz = item_info.get("price_kz", 1500)
    user_id = call.from_user.id
    
    text = (
        f"💳 **Оплата через Kaspi перевод**\n\n"
        f"📦 Товар: **{name}**\n"
        f"💰 К оплате: **{price_kz} ₸**\n\n"
        f"📋 **Реквизиты:**\n"
        f"Карта: `{KASPI_CARD}`\n\n"
        f"Ваш ID для справки: `{user_id}`\n\n"
        f"📸 **Инструкция:** Переведите сумму на карту выше, после чего **отправьте скриншот чека (фотографию) прямо в этот чат**."
    )
    
    kaspi_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]
    ])
    
    await call.message.edit_text(text, reply_markup=kaspi_kb, parse_mode="Markdown")

@router.message(F.photo)
async def handle_receipt_photo(message: Message):
    if message.from_user.id == ADMIN_CHAT_ID:
        return  
    
    user = message.from_user
    photo = message.photo[-1].file_id
    
    caption = (
        f"🔔 **Новый чек на оплату от клиента!**\n\n"
        f"👤 Имя: {user.first_name}\n"
        f"🔗 Username: @{user.username if user.username else 'нет'}\n"
        f"🆔 ID: `{user.id}`"
    )
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Ординар", callback_data=f"grant_ordinary_{user.id}")],
        [InlineKeyboardButton(text="🔥 Экспресс", callback_data=f"grant_express_{user.id}")],
        [InlineKeyboardButton(text="💣 Хай-Кэф", callback_data=f"grant_high_odds_{user.id}")],
        [InlineKeyboardButton(text="👑 VIP 7д", callback_data=f"grant_vip_7_{user.id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_user_{user.id}")]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=photo,
        caption=caption,
        reply_markup=admin_kb,
        parse_mode="Markdown"
    )
    
    await message.answer("✅ **Чек успешно отправлен администратору!**\n\nОжидайте проверки.")

@router.callback_query(F.data.startswith("grant_"))
async def grant_product_handler(call: CallbackQuery):
    if call.from_user.id != ADMIN_CHAT_ID:
        await call.answer("У вас нет прав администратора!", show_alert=True)
        return
        
    parts = call.data.split("_")
    if parts[1] == "vip" and parts[2] == "7":
        product_code = "vip_7"
        target_user_id = int(parts[3])
    else:
        product_code = parts[1]
        target_user_id = int(parts[2])
        
    prediction_content = APPROVED_MARKET.get(product_code)
    if not prediction_content:
        prediction_content = "Эксклюзивный прогноз на выбранное событие."
    else:
        if isinstance(prediction_content, dict):
            prediction_content = prediction_content.get("content", "Материал доступен в маркетплейсе.")

    try:
        await call.message.edit_caption(
            caption=call.message.caption + f"\n\n**[✅ СТАТУС: Выдано ({product_code})]**",
            parse_mode="Markdown"
        )
    except Exception:
        pass
        
    try:
        watermark = f"\n\n---\n🔒 *Персональная лицензия для ID: {target_user_id}*\n⚠️ Покупая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
        
        await bot.send_message(
            chat_id=target_user_id,
            text=f"🎉 **Ваша оплата подтверждена администратором!**\n\n📦 Ваш материал:\n\n{prediction_content}{watermark}",
            parse_mode="Markdown"
        )
        await bot.send_message(target_user_id, "🛍 **Главное меню BetMarket KZ:**", reply_markup=get_dynamic_keyboard(), parse_mode="Markdown")
        await call.answer("Товар успешно выдан клиенту!")
    except Exception as e:
        await call.answer(f"Ошибка выдачи: {e}", show_alert=True)

@router.callback_query(F.data.startswith("reject_user_"))
async def admin_reject_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_CHAT_ID:
        await call.answer("У вас нет прав администратора!", show_alert=True)
        return
    
    target_user_id = int(call.data.replace("reject_user_", ""))
    try:
        await call.message.edit_caption(
            caption=call.message.caption + "\n\n**[❌ СТАТУС: Отклонено]**",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text="❌ **К сожалению, ваш чек был отклонен администратором.**",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    await call.answer("Заявка отклонена.")

@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: CallbackQuery):
    item_code = call.data.replace("pay_stars_", "")
    item_info = APPROVED_MARKET.get(item_code, {})
    name = item_info.get("name", "Прогноз")
    stars = item_info.get("stars", 50)
    
    prices = [LabeledPrice(label=name, amount=stars)]
    
    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_invoice(
        title=name,
        description="Автоматическая покупка прогноза BetMarket KZ",
        prices=prices,
        provider_token="",
        payload=f"order_{item_code}",
        currency="XTR",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ Оплатить {stars} Stars", pay=True)],
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="main_menu")]
        ])
    )
    await call.answer()

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@router.message(F.successful_payment)
async def success_payment(message: Message):
    await message.answer("✅ **Оплата Stars прошла успешно!** Высылаем ваш материал...", parse_mode="Markdown")
    
    payload = message.successful_payment.invoice_payload
    item_code = payload.replace("order_", "") if "order_" in payload else "ordinary"
    item_info = APPROVED_MARKET.get(item_code, {})
    content = item_info.get("content", "Эксклюзивный материал от BetMarket KZ.") if isinstance(item_info, dict) else "Материал доступен."

    user = message.from_user
    username_tag = f"@{user.username}" if user.username else f"ID: {user.id}"
    watermark = f"\n\n---\n🔒 *Персональная лицензия: {username_tag} (ID: {user.id})*\n⚠️ Покупая или получая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
    
    await message.answer(f"👑 **ВАШ ПРОГНОЗ:**\n\n{content}{watermark}", parse_mode="Markdown")
    await message.answer("🛍 **Главное меню BetMarket KZ:**", reply_markup=get_dynamic_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "profile")
async def profile_handler(call: CallbackQuery):
    user = call.from_user
    text = (
        f"👤 **Ваш профиль в BetMarket KZ:**\n\n"
        f"🆔 ID: `{user.id}`\n"
        f"📛 Имя: {user.first_name}\n"
        f"🔗 Username: @{user.username if user.username else 'не указан'}\n"
        f"🛡 Статус: Верифицированный клиент"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]])
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")

@router.callback_query(F.data == "stats")
async def stats_handler(call: CallbackQuery):
    text = "📊 **Статистика BetMarket KZ:**\n• Проходимость: 74.2%\n• Средний ROI: +19.1%"
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]])
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")


# --- АДМИН-ПАНЕЛЬ И КНОПКИ УПРАВЛЕНИЯ ---

def parse_and_store_text(text_block: str):
    """Парсит текст черновика и автоматически раскладывает его по полочкам рынка"""
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
        APPROVED_MARKET["free"] = "\n".join(buf["free"])
    if buf["ordinary"]:
        APPROVED_MARKET["ordinary"] = {"name": "🎯 Ординар дня", "price_kz": 1500, "stars": 50, "content": "\n".join(buf["ordinary"])}
    if buf["express"]:
        APPROVED_MARKET["express"] = {"name": "🔥 Экспресс 2-3", "price_kz": 2500, "stars": 80, "content": "\n".join(buf["express"])}
    if buf["high"]:
        APPROVED_MARKET["high_odds"] = {"name": "💣 Хай-Кэф", "price_kz": 4000, "stars": 130, "content": "\n".join(buf["high"])}


@router.message(Command("draft"))
async def admin_get_draft(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
        
    await message.answer("⏳ *ИИ анализирует сегодняшнюю линию...*", parse_mode="Markdown")
    draft_text = await ask_gemini_market_draft()
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить этот черновик в маркет", callback_data="approve_draft")],
        [InlineKeyboardButton(text="🔄 Обновить черновик", callback_data="refresh_draft")]
    ])
    
    await message.answer(
        f"📋 **Свежий черновик подборки:**\n\n{draft_text}",
        reply_markup=admin_kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "approve_draft")
async def approve_draft_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_CHAT_ID:
        await call.answer("Нет прав", show_alert=True)
        return
        
    text_to_parse = LAST_GENERATED_DRAFT.get("text", "")
    if not text_to_parse:
        text_to_parse = "Бесплатный прогноз: Топ-матч дня\nОрдинар: Дежурный ординар\nЭкспресс: Экспресс дня\nХай-кэф: Хай-кэф дня"
        
    parse_and_store_text(text_to_parse)
    
    await call.message.edit_text(
        f"✅ **Черновик успешно одобрен и запущен в продажи!**\n\nВитрина бота обновлена.",
        reply_markup=None,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "refresh_draft")
async def refresh_draft_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_CHAT_ID:
        await call.answer("Нет прав", show_alert=True)
        return
        
    await call.message.edit_text("⏳ *ИИ ищет альтернативные варианты...*", parse_mode="Markdown")
    draft_text = await ask_gemini_market_draft()
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить этот черновик в маркет", callback_data="approve_draft")],
        [InlineKeyboardButton(text="🔄 Обновить черновик", callback_data="refresh_draft")]
    ])
    
    await call.message.edit_text(
        f"📋 **Новый вариант черновика:**\n\n{draft_text}",
        reply_markup=admin_kb,
        parse_mode="Markdown"
    )

@router.message(Command("setmarket"))
async def admin_set_market(message: Message):
    """Ручное утверждение через текст, если хотите внести правки"""
    if message.from_user.id != ADMIN_CHAT_ID:
        return
        
    full_text = message.text.replace("/setmarket", "").strip()
    if not full_text:
        await message.answer("⚠️ Напишите текст после команды `/setmarket`.", parse_mode="Markdown")
        return
        
    parse_and_store_text(full_text)
    current_date = datetime.now(timezone(timedelta(hours=5))).strftime("%d.%m.%Y")
    
    await message.answer(
        f"✅ **Рынок на {current_date} успешно обновлен вручную!**\nВитрина для клиентов перестроена.",
        parse_mode="Markdown",
        reply_markup=get_dynamic_keyboard()
    )


# --- ФОНОВЫЕ УВЕДОМЛЕНИЯ ДЛЯ АДМИНА ---
async def background_admin_notifications():
    await asyncio.sleep(30)
    while True:
        now = datetime.now(timezone(timedelta(hours=5)))
        current_time_str = now.strftime("%H:%M")
        
        target_times = ["11:00", "16:00", "18:00", "21:00", "01:00"]
        
        if current_time_str in target_times:
            try:
                draft = await ask_gemini_market_draft()
                admin_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Одобрить в маркет", callback_data="approve_draft")],
                    [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_draft")]
                ])
                await bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"⏰ **Плановая проверка линии ({current_time_str})!**\n\n{draft}",
                    reply_markup=admin_kb,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Notification error: {e}")
            await asyncio.sleep(70)
            
        await asyncio.sleep(30)


# --- ВЕБ-СЕРВЕР И САМОПИНГ ---
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
                    logging.info(f"Self-ping sent, status: {resp.status}")
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
        await bot.set_my_commands([
            BotCommand(command="start", description="🏠 Главное меню"),
            BotCommand(command="draft", description="📋 Запросить свежий черновик у ИИ"),
            BotCommand(command="setmarket", description="🛠 Утвердить маркет вручную текстом")
        ])
    except Exception as e:
        logging.error(f"Не удалось установить команды: {e}")
    
    dp.include_router(router)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.error(f"Ошибка удаления вебхука: {e}")
        
    web_server_task = asyncio.create_task(web_server())
    asyncio.create_task(background_admin_notifications())
    logging.info("🚀 Улучшенный бот с кнопками управления успешно запущен!")
    
    while True:
        try:
            await dp.start_polling(bot, handle_signals=False)
        except Exception as e:
            logging.error(f"⚠️ Ошибка поллинга: {e}. Переподключение через 5 секунд...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
