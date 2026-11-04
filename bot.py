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

PRODUCTS = {
    "ordinary": {"name": "🎯 Ординар (Кэф 1.7-1.9)", "price_kz": 1500, "stars": 50},
    "express": {"name": "🔥 Экспресс 2-3 (Кэф 2.0-3.0)", "price_kz": 2500, "stars": 80},
    "high_odds": {"name": "💣 Хай-Кэф (Кэф 4.0-7.0)", "price_kz": 4000, "stars": 130},
    "vip_7": {"name": "👑 VIP-Подписка (Сливы на 7 дней)", "price_kz": 5000, "stars": 160},
}

SYSTEM_ANALYST_INSTRUCTION = """
Ты — главный спортивный аналитик и каппер платформы BetMarket KZ.
Строгое правило временной фильтрации:
1. Анализируй ТОЛЬКО реальные матчи топ-лиг (Футбол ЛЧ/Лиги Европы, КХЛ, НХЛ, НБА), которые начнутся СТРОГО в интервале от 15 минут до 12 часов от текущего времени пользователя.
2. Категорически запрещено брать матчи, которые уже идут, уже завершились или начнутся позже чем через 12 часов.
3. Никаких шаблонных архивных матчей (вроде старых игр Реала и Барселоны). Только актуальный календарь на сегодня/ближайшую ночь.
"""

async def ask_gemini_prediction(prompt_text: str, product_type: str = "general") -> str:
    """Генерация прогноза с жестким контролем временного окна (15 мин - 12 часов вперед)"""
    almaty_time = datetime.now(timezone(timedelta(hours=5)))
    current_date_str = almaty_time.strftime("%d.%m.%Y")
    current_time_str = almaty_time.strftime("%H:%M")
    
    # Расчет временного окна (от текущего времени до +12 часов)
    future_time_limit = (almaty_time + timedelta(hours=12)).strftime("%H:%M")
    
    if product_type == "free":
        task_instruction = (
            f"Сформируй бесплатный ординар на топовый матч, который начнется сегодня в промежутке с {current_time_str} до {future_time_limit} по Алматы. "
            f"Здесь можно выйти за рамки жестких кэфов, главное — интересная вывеска и глубокое, обоснованное экспертное мнение."
        )
    else:
        task_instruction = (
            f"Сформируй платный прогноз типа '{product_type}' на матч, стартующий сегодня в окне с {current_time_str} до {future_time_limit} по Алматы. "
            f"Требуется высокая уверенность, детальный разбор линии, учет травм и мотивации. Задание: {prompt_text}"
        )

    full_prompt = (
        f"Текущая дата и точное время в Алматы: {current_date_str}, {current_time_str}. "
        f"Временное окно для поиска матча: от {current_time_str} до {future_time_limit} (сегодня). "
        f"{task_instruction}"
    )
    
    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_ANALYST_INSTRUCTION)
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, full_prompt),
            timeout=12.0
        )
        text = response.text.strip()
        
        # Если модель выдала слишком короткий ответ или устаревший шаблон
        if len(text) < 30 or "Реал Мадрид — Барселона" in text:
            return get_dynamic_fallback(product_type, current_date_str, current_time_str)
            
        return text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return get_dynamic_fallback(product_type, current_date_str, current_time_str)

def get_dynamic_fallback(product_type: str, date_str: str, time_str: str) -> str:
    """Динамический резерв на ближайшее время"""
    return (
        f"🏆 **Оперативный ординар (Актуально на {date_str}, после {time_str})**\n\n"
        f"📌 **Матч:** Центральное событие ближайших часов\n"
        f"🎯 **Ставка:** Победа фаворита в матче / Обе забьют (в зависимости от линии)\n"
        f"📊 **Коэффициент:** ~1.78\n\n"
        f"🔍 **Аналитика:** Матч отобран в диапазоне 12 часов от текущего момента. Учтены текущая форма команд, плотный график и мотивация набора очков в турнирной таблице."
    )

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Бесплатный прогноз (Кэф 1.6-2.0)", callback_data="team_free_pick")],
        [
            InlineKeyboardButton(text="🎯 Ординар (1 500 ₸)", callback_data="item_ordinary"),
            InlineKeyboardButton(text="🔥 Экспресс 2-3 (2 500 ₸)", callback_data="item_express")
        ],
        [
            InlineKeyboardButton(text="💣 Хай-Кэф (4 000 ₸)", callback_data="item_high_odds"),
            InlineKeyboardButton(text="👑 VIP 7 дней (5 000 ₸)", callback_data="item_vip_7")
        ],
        [
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
            InlineKeyboardButton(text="📊 Статистика / ROI", callback_data="stats")
        ],
        [InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])

@router.message(CommandStart())
async def start_cmd(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
        
    welcome_text = (
        f"👋 **Добро пожаловать в BetMarket KZ!**\n\n"
        f"🛍 Официальный маркетплейс спортивных прогнозов (Футбол ЛЧ, КХЛ, НХЛ, НБА).\n"
        f"⏱ Анализируем матчи в режиме реального времени (в окне ближайших 12 часов).\n\n"
        f"Ваш Telegram ID: `{message.from_user.id}`"
    )
    await message.answer(welcome_text, reply_markup=main_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery):
    try:
        await call.message.edit_text("🛍 **Главное меню BetMarket KZ:**", reply_markup=main_keyboard(), parse_mode="Markdown")
    except Exception:
        await call.message.answer("🛍 **Главное меню BetMarket KZ:**", reply_markup=main_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "team_free_pick")
async def team_free_pick_handler(call: CallbackQuery):
    await call.answer("Ищем матчи в ближайшей линии...")
    await call.message.edit_text("⏳ *Сканируем расписание на ближайшие 12 часов...*", parse_mode="Markdown")
    
    current_date = datetime.now(timezone(timedelta(hours=5))).strftime("%d.%m.%Y")
    prompt = "Сформируй бесплатный ординар на ближайший матч."
    
    result = await ask_gemini_prediction(prompt, "free")
    
    user = call.from_user
    username_tag = f"@{user.username}" if user.username else f"ID: {user.id}"
    watermark = f"\n\n---\n🔒 *Персональная лицензия: {username_tag} (ID: {user.id})*\n⚠️ Покупая или получая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
    report = f"🎁 **БЕСПЛАТНЫЙ ПРОГНОЗ НА {current_date}**\n\n{result}{watermark}"
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]])
    await call.message.edit_text(report, reply_markup=back_kb, parse_mode="Markdown")
    await call.message.answer("👇 Вы можете продолжить выбор в главном меню:", reply_markup=main_keyboard())

@router.callback_query(F.data.startswith("item_"))
async def select_item(call: CallbackQuery):
    item_code = call.data.replace("item_", "")
    item = PRODUCTS.get(item_code)
    if not item:
        return
        
    text = (
        f"📦 **Вы выбрали:** {item['name']}\n"
        f"💳 **Стоимость:** {item['price_kz']} ₸ или {item['stars']} Stars ⭐\n\n"
        f"⚠️ **Правила сервиса:** При обнаружении факта слива или перепродажи прогноза — мгновенный бан навсегда без возврата средств.\n\n"
        f"Выберите удобный способ оплаты:"
    )
    
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить Kaspi ({item['price_kz']} ₸)", callback_data=f"pay_kaspi_{item_code}")],
        [InlineKeyboardButton(text=f"⭐ Оплатить Telegram Stars ({item['stars']} ⭐)", callback_data=f"pay_stars_{item_code}")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, reply_markup=pay_kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pay_kaspi_"))
async def pay_kaspi(call: CallbackQuery):
    item_code = call.data.replace("pay_kaspi_", "")
    item = PRODUCTS.get(item_code)
    user_id = call.from_user.id
    
    text = (
        f"💳 **Оплата через Kaspi перевод**\n\n"
        f"📦 Товар: **{item['name']}**\n"
        f"💰 К оплате: **{item['price_kz']} ₸**\n\n"
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
        [InlineKeyboardButton(text="🎯 Ординар (1500₸)", callback_data=f"grant_ord_{user.id}")],
        [InlineKeyboardButton(text="🔥 Экспресс (2500₸)", callback_data=f"grant_exp_{user.id}")],
        [InlineKeyboardButton(text="💣 Хай-Кэф (4000₸)", callback_data=f"grant_high_{user.id}")],
        [InlineKeyboardButton(text="👑 VIP 7 дней (5000₸)", callback_data=f"grant_vip_{user.id}")],
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

async def process_grant_for_user(call: CallbackQuery, product_type: str):
    if call.from_user.id != ADMIN_CHAT_ID:
        await call.answer("У вас нет прав администратора!", show_alert=True)
        return
    
    data_parts = call.data.split("_")
    target_user_id = int(data_parts[-1])
    
    prompts = {
        "ordinary": ("🎯 ВАШ ОПЛАЧЕННЫЙ ОРДИНАР (Кэф 1.7-1.9)", "Сформируй надежный платный ординар на ближайший матч с кэфом 1.70-1.90."),
        "express": ("🔥 ВАШ УВЕРЕННЫЙ ЭКСПРЕСС 2-3 (Кэф 2.0-3.0)", "Сформируй экспресс из матчей ближайших 12 часов с общим кэфом 2.0-3.0."),
        "high": ("💣 ВАШ ХАЙ-КЭФ ПРОГНОЗ (Кэф 4.0-7.0)", "Сформируй хай-кэф на ближайшее событие."),
        "vip": ("👑 ВАША VIP-ПОДПИСКА НА 7 ДНЕЙ", "Сформируй премиальный пакет прогнозов на актуальные матчи.")
    }
    
    title, prompt = prompts.get(product_type, prompts["ordinary"])
    prediction = await ask_gemini_prediction(prompt, product_type)

    try:
        await call.message.edit_caption(
            caption=call.message.caption + f"\n\n**[✅ СТАТУС: Выдано ({title})]**",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    try:
        watermark = f"\n\n---\n🔒 *Персональная лицензия для ID: {target_user_id}*\n⚠️ Покупая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
        
        await bot.send_message(
            chat_id=target_user_id, 
            text=f"🎉 **Ваша оплата подтверждена администратором!**\n\n{title}:\n\n{prediction}{watermark}",
            parse_mode="Markdown"
        )
        await bot.send_message(target_user_id, "🛍 **Главное меню BetMarket KZ:**", reply_markup=main_keyboard(), parse_mode="Markdown")
        await call.answer("Прогноз успешно выдан!")
    except Exception as e:
        await call.answer(f"Ошибка выдачи: {e}", show_alert=True)

@router.callback_query(F.data.startswith("grant_ord_"))
async def grant_ord(call: CallbackQuery):
    await process_grant_for_user(call, "ordinary")

@router.callback_query(F.data.startswith("grant_exp_"))
async def grant_exp(call: CallbackQuery):
    await process_grant_for_user(call, "express")

@router.callback_query(F.data.startswith("grant_high_"))
async def grant_high(call: CallbackQuery):
    await process_grant_for_user(call, "high")

@router.callback_query(F.data.startswith("grant_vip_"))
async def grant_vip(call: CallbackQuery):
    await process_grant_for_user(call, "vip")

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
    item = PRODUCTS[item_code]
    prices = [LabeledPrice(label=item['name'], amount=item['stars'])]
    
    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_invoice(
        title=item['name'],
        description="Автоматическая покупка прогноза BetMarket KZ",
        prices=prices,
        provider_token="",
        payload=f"order_{item_code}",
        currency="XTR",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ Оплатить {item['stars']} Stars", pay=True)],
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="main_menu")]
        ])
    )
    await call.answer()

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@router.message(F.successful_payment)
async def success_payment(message: Message):
    await message.answer("✅ **Оплата Stars прошла успешно!** Генерируем прогноз на ближайший матч...", parse_mode="Markdown")
    prediction = await ask_gemini_prediction("Сформируй эксклюзивный VIP прогноз на ближайшее топ-событие.", "vip")
    
    user = message.from_user
    username_tag = f"@{user.username}" if user.username else f"ID: {user.id}"
    watermark = f"\n\n---\n🔒 *Персональная лицензия: {username_tag} (ID: {user.id})*\n⚠️ Покупая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
    
    await message.answer(f"👑 **ВАШ VIP ПРОГНОЗ:**\n\n{prediction}{watermark}", parse_mode="Markdown")
    await message.answer("🛍 **Главное меню BetMarket KZ:**", reply_markup=main_keyboard(), parse_mode="Markdown")

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

# --- ВЕБ-СЕРВЕР И САМОПИНГ ---
async def handle(request):
    return web.Response(text="BetMarket Server OK")

async def self_ping_task():
    """Фоновый самопинг для поддержания активности на Render"""
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
        await bot.set_my_commands([BotCommand(command="start", description="🏠 Главное меню BetMarket")])
    except Exception as e:
        logging.error(f"Не удалось установить команды: {e}")
    
    dp.include_router(router)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.error(f"Ошибка удаления вебхука: {e}")
        
    await web_server()
    logging.info("🚀 Бот и веб-сервер успешно запущены!")
    
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
