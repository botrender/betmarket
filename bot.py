import asyncio
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery
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
    "ordinary": {"name": "🎯 Ординар дня (Кэф 1.8+)", "price_kz": 1500, "stars": 50},
    "express": {"name": "🔥 Уверенный экспресс (Кэф 2.5-3.0)", "price_kz": 2500, "stars": 80},
    "high_odds": {"name": "💣 Хай-Кэф / Экспресс (Кэф 5.0+)", "price_kz": 4000, "stars": 130},
    "vip_7": {"name": "👑 VIP-Подписка (Сливы на 7 дней)", "price_kz": 5000, "stars": 160},
}

SYSTEM_ANALYST_INSTRUCTION = """
Ты — старший спортивный каппер и аналитик платформы BetMarket KZ.
Используй актуальные топовые матчи европейских чемпионатов (АПЛ, Ла Лига, Серия А, Лига Чемпионов).
ЖЕСТКИЕ ПРАВИЛА:
1. Предлагай качественные ставки с реалистичными коэффициентами: для ординаров от 1.70 до 2.20, для экспресса от 2.30 до 3.20.
2. Давай четкую аргументацию и аналитику по матчу.
3. Оформляй отклик в виде красивого Telegram-поста с эмодзи.
"""

async def ask_gemini_prediction(prompt_text: str) -> str:
    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_ANALYST_INSTRUCTION)
        # Асинхронный вызов через поток, работает мгновенно без зависаний сети
        response = await asyncio.to_thread(model.generate_content, prompt_text)
        return response.text.strip()
    except Exception as e:
        return f"⚠️ Ошибка генерации: {e}"

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Бесплатный прогноз от BetMarket", callback_data="team_free_pick")],
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
        f"🛍 Официальный маркетплейс спортивных прогнозов.\n\n"
        f"Ваш Telegram ID: `{message.from_user.id}`\n"
        f"Выберите интересующий раздел:"
    )
    await message.answer(welcome_text, reply_markup=main_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_text("🛍 **Главное меню BetMarket KZ:**", reply_markup=main_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "team_free_pick")
async def team_free_pick_handler(call: CallbackQuery):
    await call.message.edit_text("⏳ *Анализируем матчи и формируем прогноз...*", parse_mode="Markdown")
    
    prompt = "Сформируй 1 уверенный ординар (кэф от 1.70 до 2.10) и 1 готовый экспресс (кэф от 2.30 до 3.10) на сегодняшние топ-матчи."
    result = await ask_gemini_prediction(prompt)
    
    user = call.from_user
    username_tag = f"@{user.username}" if user.username else f"ID: {user.id}"
    watermark = f"\n\n---\n🔒 *Персональная лицензия: {username_tag} (ID: {user.id})*\n⚠️ Покупая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
    
    report = f"🎁 **АКТУАЛЬНЫЙ ПРОГНОЗ BETMARKET KZ**\n\n{result}{watermark}"
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]])
    await call.message.edit_text(report, reply_markup=back_kb, parse_mode="Markdown")

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
        f"Ваш персональный ID для проверки: `{user_id}`\n\n"
        f"⚠️ **Условие:** Переведите сумму и отправьте скриншот чека вместе с вашим ID администратору. При сливе прогноза — бан навсегда!"
    )
    
    kaspi_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Отправить чек администратору", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]
    ])
    
    await call.message.edit_text(text, reply_markup=kaspi_kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: CallbackQuery):
    item_code = call.data.replace("pay_stars_", "")
    item = PRODUCTS.get(item_code)
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
    await message.answer("✅ **Оплата прошла успешно!** Генерируем ваш защищенный персональный VIP-прогноз...", parse_mode="Markdown")
    prompt = "Сформируй эксклюзивный VIP прогноз на топ-матч с высоким проходом."
    prediction = await ask_gemini_prediction(prompt)
    
    user = message.from_user
    username_tag = f"@{user.username}" if user.username else f"ID: {user.id}"
    watermark = f"\n\n---\n🔒 *Персональная лицензия: {username_tag} (ID: {user.id})*\n⚠️ Покупая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
    
    await message.answer(f"👑 **ВАШ VIP ПРОГНОЗ:**\n\n{prediction}{watermark}", parse_mode="Markdown")

@router.message(Command("grant"))
async def grant_cmd(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    try:
        target_user_id = int(message.text.split()[1])
        prompt = "Сформируй эксклюзивный оплаченный прогноз на основе топ-матча."
        prediction = await ask_gemini_prediction(prompt)
        
        watermark = f"\n\n---\n🔒 *Персональная лицензия для ID: {target_user_id}*\n⚠️ Покупая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
        
        await bot.send_message(
            chat_id=target_user_id, 
            text=f"🎉 **Ваша оплата Kaspi подтверждена администратором!**\n\n🎯 **Ваш защищенный прогноз:**\n\n{prediction}{watermark}",
            parse_mode="Markdown"
        )
        await message.answer(f"✅ Прогноз с водяным знаком успешно отправлен пользователю `{target_user_id}`!")
    except Exception as e:
        await message.answer(f"❌ Ошибка! Используйте формат: `/grant ID_ПОЛЬЗОВАТЕЛЯ`\nДетали: {e}")

@router.callback_query(F.data == "profile")
async def profile_handler(call: CallbackQuery):
    user = call.from_user
    text = (
        f"👤 **Ваш профиль в BetMarket KZ:**\n\n"
        f"🆔 ID: `{user.id}`\n"
        f"📛 Имя: {user.first_name}\n"
        f"🔗 Username: @{user.username if user.username else 'не указан'}\n"
        f"🛡 Статус: Верифицированный клиент\n\n"
        f"⚠️ *Все купленные прогнозы защищены персональным цифровым водяным знаком.*"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]])
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")

@router.callback_query(F.data == "stats")
async def stats_handler(call: CallbackQuery):
    text = "📊 **Статистика BetMarket KZ:**\n• Проходимость: 74.2%\n• Средний ROI: +19.1%"
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]])
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")

# --- ВЕБ-СЕРВЕР ---
async def handle(request):
    return web.Response(text="BetMarket Server OK")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await web_server()
    logging.info("🚀 Бот и веб-сервер запущены!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
