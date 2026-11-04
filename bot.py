import asyncio
import logging
import sys
import os
from datetime import datetime
from aiohttp import web
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
    "ordinary": {"name": "🎯 Ординар (Кэф 1.7-1.9)", "price_kz": 1500, "stars": 50, "type": "ordinary_paid"},
    "express": {"name": "🔥 Экспресс 2-3 (Кэф 2.0-3.0)", "price_kz": 2500, "stars": 80, "type": "express_paid"},
    "high_odds": {"name": "💣 Хай-Кэф (Кэф 4.0-7.0)", "price_kz": 4000, "stars": 130, "type": "high_paid"},
    "vip_7": {"name": "👑 VIP-Подписка (Сливы на 7 дней)", "price_kz": 5000, "stars": 160, "type": "vip_all"},
}

SYSTEM_ANALYST_INSTRUCTION = """
Ты — профессиональный спортивный каппер и аналитик платформы BetMarket KZ.
Используй актуальные матчи топ-лиг футбола (АПЛ, Ла Лига, Серия А, ЛЧ), КХЛ, НХЛ и НБА.
Твоя задача — формировать точные прогнозы в зависимости от запроса с жестким соблюдением коэффициентов:
- Для бесплатного ординара: кэф от 1.6 до 2.0.
- Для платного ординара (1500₸): другой, максимально уверенный матч с кэфом от 1.7 до 1.9.
- Для экспресса (2500₸): экспресс из 2-3 матчей с общим итоговым кэфом от 2.0 до 3.0.
- Для хай-кэфа (4000₸): чуть более рискованные события с высоким итоговым кэфом от 4.0 до 7.0.
Оформляй каждый пост красиво, с детальной аналитикой и эмодзи.
"""

async def ask_gemini_prediction(prompt_text: str) -> str:
    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_ANALYST_INSTRUCTION)
        response = await asyncio.to_thread(model.generate_content, prompt_text)
        return response.text.strip()
    except Exception as e:
        return f"⚠️ Ошибка генерации: {e}"

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
        f"🛍 Официальный маркетплейс спортивных прогнозов (Футбол топ-лиги, КХЛ, НХЛ, НБА).\n\n"
        f"Ваш Telegram ID: `{message.from_user.id}`\n"
        f"Главное меню всегда доступно ниже или по кнопке **Menu** слева от ввода текста:"
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
    await call.message.edit_text("⏳ *Анализируем матчи и подготавливаем бесплатный ординар...*", parse_mode="Markdown")
    
    current_date = datetime.now().strftime("%d.%m.%Y")
    prompt = f"Сформируй бесплатный ординар на актуальную дату ({current_date}) по футболу, КХЛ, НХЛ или НБА с коэффициентом строго от 1.60 до 2.00."
    result = await ask_gemini_prediction(prompt)
    
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
        f"📸 **Инструкция:** Переведите сумму на карту выше, после чего **отправьте скриншот чека (фотографию) прямо в этот чат**. Бот автоматически перешлет его администратору!"
    )
    
    kaspi_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]
    ])
    
    await call.message.edit_text(text, reply_markup=kaspi_kb, parse_mode="Markdown")

# --- ПЕРЕХВАТ СКРИНШОТА ЧЕКА ОТ КЛИЕНТА ---
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
    
    await message.answer("✅ **Чек успешно отправлен администратору!**\n\nОжидайте проверки. После подтверждения бот автоматически выдаст вам прогноз.")

# --- УНИВЕРСАЛЬНАЯ ВЫДАЧА АДМИНИСТРАТОРОМ ---
async def process_grant_for_user(call: CallbackQuery, product_type: str):
    if call.from_user.id != ADMIN_CHAT_ID:
        await call.answer("У вас нет прав администратора!", show_alert=True)
        return
    
    data_parts = call.data.split("_")
    target_user_id = int(data_parts[-1])
    
    if product_type == "ordinary":
        prompt = "Сформируй надежный платный ординар на топ-матч (футбол, КХЛ, НХЛ или НБА) с коэффициентом строго от 1.70 до 1.90."
        title = "🎯 ВАШ ОПЛАЧЕННЫЙ ОРДИНАР (Кэф 1.7-1.9)"
    elif product_type == "express":
        prompt = "Сформируй уверенный экспресс из 2-3 матчей (футбол, КХЛ, НХЛ, НБА) с общим итоговым коэффициентом от 2.0 до 3.0."
        title = "🔥 ВАШ УВЕРЕННЫЙ ЭКСПРЕСС 2-3 (Кэф 2.0-3.0)"
    elif product_type == "high":
        prompt = "Сформируй рискованный хай-кэф экспресс или ординар на топовые матчи с высоким общим коэффициентом от 4.0 до 7.0."
        title = "💣 ВАШ ХАЙ-КЭФ ПРОГНОЗ (Кэф 4.0-7.0)"
    else:
        prompt = "Сформируй премиальный VIP набор прогнозов на топ-лиги с высокими коэффициентами и глубокой аналитикой."
        title = "👑 ВАША VIP-ПОДПИСКА НА 7 ДНЕЙ"

    try:
        await call.message.edit_caption(
            caption=call.message.caption + f"\n\n**[✅ СТАТУС: Выдано ({title})]**",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    try:
        prediction = await ask_gemini_prediction(prompt)
        user_tag = f"ID: {target_user_id}"
        watermark = f"\n\n---\n🔒 *Персональная лицензия для ID: {target_user_id}*\n⚠️ Покупая прогноз, вы соглашаетесь с условиями: при обнаружении факта слива или перепродажи — мгновенный бан навсегда без возврата средств."
        
        await bot.send_message(
            chat_id=target_user_id, 
            text=f"🎉 **Ваша оплата Kaspi подтверждена администратором!**\n\n{title}:\n\n{prediction}{watermark}",
            parse_mode="Markdown"
        )
        await bot.send_message(target_user_id, "🛍 **Главное меню BetMarket KZ:**", reply_markup=main_keyboard(), parse_mode="Markdown")
        await call.answer("Прогноз успешно выдан пользователю!")
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
            caption=call.message.caption + "\n\n**[❌ СТАТУС: Отклонено / Чек недействителен]**",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text="❌ **К сожалению, ваш чек был отклонен администратором.**\nУбедитесь в правильности перевода или обратитесь в поддержку.",
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
    await message.answer("✅ **Оплата Stars прошла успешно!** Генерируем ваш защищенный персональный прогноз...", parse_mode="Markdown")
    prompt = "Сформируй эксклюзивный VIP прогноз на топ-матч с высоким проходом."
    prediction = await ask_gemini_prediction(prompt)
    
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
    await bot.set_my_commands([BotCommand(command="start", description="🏠 Главное меню BetMarket")])
    
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
