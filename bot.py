import os
import json
import logging
import sys
from datetime import datetime
from typing import Dict

print("Python version:", sys.version)
print("Current working directory:", os.getcwd())
print("PYTHONPATH:", os.environ.get("PYTHONPATH", "Not set"))

try:
    from dotenv import load_dotenv
    print("python-dotenv imported successfully")
except ImportError as e:
    print("Failed to import python-dotenv:", e)
    sys.exit(1)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
    print("python-telegram-bot core imported successfully")
except ImportError as e:
    print("Failed to import python-telegram-bot:", e)
    sys.exit(1)

try:
    from telegram.ext import (
        Application,
        CommandHandler,
        CallbackQueryHandler,
        PreCheckoutQueryHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
    print("python-telegram-bot extensions imported successfully")
except ImportError as e:
    print("Failed to import python-telegram-bot extensions:", e)
    sys.exit(1)

from telegram.error import TelegramError

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Check required environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")
if not PAYMENT_PROVIDER_TOKEN:
    raise ValueError("PAYMENT_PROVIDER_TOKEN environment variable is not set")

logger.info("Bot token: %s", BOT_TOKEN[:10] + "..." if BOT_TOKEN else "Not set")
logger.info("Payment provider token: %s", PAYMENT_PROVIDER_TOKEN[:10] + "..." if PAYMENT_PROVIDER_TOKEN else "Not set")
logger.info("Test mode: %s", "Yes" if PAYMENT_PROVIDER_TOKEN and "TEST" in PAYMENT_PROVIDER_TOKEN.upper() else "No")

# Payment configurations
PAYMENT_CONFIGS = {
    "sub_basic": {
        "title": "Разовый платеж",
        "description": "Единоразовый доступ к сервису. Включает базовые функции и доступ к закрытому разделу.",
        "payload": "basic_plan",
        "price": 60.00,
    },
    "sub_premium": {
        "title": "Премиум подписка",
        "description": "Месячный доступ ко всем функциям. Включает расширенные возможности и приоритетную поддержку.",
        "payload": "premium_plan",
        "price": 80.00,
    },
    "sub_pro": {
        "title": "Про подписка",
        "description": "Годовой доступ со всеми преимуществами. Максимальный набор функций и VIP поддержка.",
        "payload": "pro_plan",
        "price": 100.00,
    },
}

# In-memory storage for subscriptions
subscriptions: Dict[int, Dict[str, any]] = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user_id = update.effective_user.id
    
    if user_id in subscriptions and subscriptions[user_id].get("active", False):
        await show_protected_menu(update, context)
        return

    keyboard = [[InlineKeyboardButton("💳 Оплатить подписку", callback_data="menu_subscriptions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "*👋 Добро пожаловать\\!*\n\n"
        "Для доступа к закрытому меню необходима подписка\\.\n"
        "Выберите тариф для оплаты:",
        parse_mode="MarkdownV2",
        reply_markup=reply_markup,
    )

async def show_protected_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the protected menu for subscribed users."""
    keyboard = [
        [InlineKeyboardButton("📋 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(
        "*🎉 Добро пожаловать в закрытый раздел\\!*\n\nВыберите нужный пункт меню:",
        parse_mode="MarkdownV2",
        reply_markup=reply_markup,
    )

async def subscription_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the subscription plans menu."""
    keyboard = [
        [InlineKeyboardButton("💳 Разовый платеж - 60₽", callback_data="sub_basic")],
        [InlineKeyboardButton("💎 Подписка на месяц - 80₽", callback_data="sub_premium")],
        [InlineKeyboardButton("👑 Подписка на год - 100₽", callback_data="sub_pro")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.reply_text(
        "*💰 Выберите тариф для оплаты:*",
        parse_mode="MarkdownV2",
        reply_markup=reply_markup,
    )
    await update.callback_query.answer()

async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle subscription plan selection."""
    query = update.callback_query
    plan_id = query.data

    if plan_id not in PAYMENT_CONFIGS:
        await query.answer("Неверный тариф")
        return

    try:
        config = PAYMENT_CONFIGS[plan_id]
        provider_token = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
        is_test = "TEST" in provider_token.upper()
        
        title = f"[TEST] {config['title']}" if is_test else config['title']
        description = config['description']
        if is_test:
            description += ("\n\n🔧 TEST MODE 🔧\nUse these test cards:\n"
                        "• 4111 1111 1111 1111 (Success)\n"
                        "• 4242 4242 4242 4242 (Success)")

        # Create a simplified provider data structure
        provider_data = {
            "receipt": {
                "items": [{
                    "description": config['title'],
                    "quantity": "1",
                    "amount": {
                        "value": str(config['price']),
                        "currency": "RUB"
                    },
                    "vat_code": 1
                }]
            }
        }

        logger.info("Sending invoice for plan %s with price %.2f RUB", plan_id, config['price'])
        logger.debug("Provider data: %s", json.dumps(provider_data))

        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=title,
            description=description,
            payload=config['payload'],
            provider_token=provider_token,
            currency="RUB",
            prices=[LabeledPrice("Оплата заказа", int(config['price'] * 100))],
            need_phone_number=True,
            send_phone_number_to_provider=True,
            provider_data=provider_data
        )
        await query.answer()
        logger.info("Invoice sent successfully")

    except TelegramError as e:
        error_msg = f"Failed to create payment: {str(e)}"
        logger.error(error_msg)
        await query.answer(error_msg[:200])  # Telegram limits callback answers to 200 characters
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await query.answer("Произошла ошибка. Попробуйте позже.")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the pre-checkout callback."""
    query = update.pre_checkout_query
    try:
        logger.info("Pre-checkout query received: %s", query.invoice_payload)
        await query.answer(ok=True)
        logger.info("Pre-checkout approved")
    except Exception as e:
        logger.error("Pre-checkout error: %s", str(e), exc_info=True)
        await query.answer(ok=False, error_message="Произошла ошибка при проверке платежа")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful payments."""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    
    logger.info(f"Payment successful - Amount: {payment.total_amount/100} {payment.currency}")
    
    subscriptions[user_id] = {
        "active": True,
        "plan": payment.invoice_payload,
        "timestamp": datetime.now().timestamp(),
    }
    
    await update.message.reply_text(
        "*✅ Оплата прошла успешно\\!*\n\n"
        "Ваша подписка активирована\\. "
        "Теперь у вас есть доступ к закрытому разделу\\.",
        parse_mode="MarkdownV2",
    )

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle profile button callback."""
    user_id = update.callback_query.from_user.id
    sub = subscriptions.get(user_id, {"active": False, "plan": None})
    
    status = "Активна ✅" if sub.get("active") else "Не активна ❌"
    plan_names = {
        "basic_plan": "Базовый",
        "premium_plan": "Премиум",
        "pro_plan": "Про",
        None: "Нет подписки",
    }
    plan = plan_names.get(sub.get("plan"))
    
    await update.callback_query.message.reply_text(
        f"*📋 Ваш профиль*\n\n"
        f"*Статус подписки:* {status}\n"
        f"*Тариф:* {plan}",
        parse_mode="MarkdownV2",
    )
    await update.callback_query.answer()

async def info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle info button callback."""
    await update.callback_query.message.reply_text(
        "*ℹ️ Информация*\n\n"
        "Это закрытый раздел с дополнительной информацией\\.\n"
        "Здесь вы можете узнать больше о наших услугах\\.",
        parse_mode="MarkdownV2",
    )
    await update.callback_query.answer()

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(os.getenv("BOT_TOKEN", "")).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(subscription_menu, pattern="^menu_subscriptions$"))
    application.add_handler(CallbackQueryHandler(handle_subscription, pattern="^sub_"))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile$"))
    application.add_handler(CallbackQueryHandler(info_callback, pattern="^info$"))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()