import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, WebAppInfo, MenuButtonWebApp
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
PAYMENT_TOKEN = "381764678:TEST:125040"  # Test payment token

# Mini App URLs
MINI_APP_URL = "https://falsefood.github.io/telegram-mini-app/"
REDIRECT_URL = "https://falsefood.github.io/telegram-mini-app/redirect.html"  # URL to your redirect page

# Payment configurations
CURRENCY = "RUB"
PRICES = {
    "basic": 6000,    # 60 RUB = 6000 kopeks
    "premium": 12000, # 120 RUB = 12000 kopeks
    "pro": 24000     # 240 RUB = 24000 kopeks
}

# Store paid users (in a real app, this should be in a database)
paid_users = set()

async def setup_menu_button(bot):
    """Setup the menu button with redirect URL."""
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Open App",
            web_app=WebAppInfo(url=REDIRECT_URL)
        )
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    # Setup menu button first
    await setup_menu_button(context.bot)
    
    keyboard = [
        [
            InlineKeyboardButton("💳 Subscriptions", callback_data="subscriptions"),
        ]
    ]
    
    # Check if user has paid
    if update.effective_user.id in paid_users:
        keyboard.append([
            InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=MINI_APP_URL))
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome! Choose your subscription plan:",
        reply_markup=reply_markup
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks."""
    query = update.callback_query
    await query.answer()

    if query.data == "subscriptions":
        keyboard = [
            [
                InlineKeyboardButton("Basic Plan - 60₽/month", callback_data="pay_basic"),
            ],
            [
                InlineKeyboardButton("Premium Plan - 120₽/month", callback_data="pay_premium"),
            ],
            [
                InlineKeyboardButton("Pro Plan - 240₽/month", callback_data="pay_pro"),
            ],
            [
                InlineKeyboardButton("« Back", callback_data="back_to_start"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "Choose your subscription plan:\n\n"
            "🔹 Basic Plan: Basic features\n"
            "🔹 Premium Plan: Advanced features\n"
            "🔹 Pro Plan: All features + priority support",
            reply_markup=reply_markup
        )
    elif query.data.startswith("pay_"):
        plan = query.data.replace("pay_", "")
        try:
            await send_invoice(query.message.chat.id, plan, context.bot)
            await query.message.reply_text(
                "Use this test card for payment:\n"
                "Card: 1111 1111 1111 1026\n"
                "Expiry: 12/22\n"
                "CVC: 000"
            )
        except Exception as e:
            logger.error(f"Payment error: {e}")
            await query.message.reply_text("Sorry, there was an error processing your payment request. Please try again later.")
    elif query.data == "back_to_start":
        await start(query, context)

async def send_invoice(chat_id: int, plan: str, bot) -> None:
    """Send invoice for payment."""
    price = PRICES.get(plan, PRICES["basic"])
    
    title = f"{plan.title()} Plan Subscription"
    description = f"Subscribe to {plan.title()} Plan - Monthly subscription"
    payload = f"subscription_{plan}"
    prices = [LabeledPrice(label=f"{plan.title()} Plan", amount=price)]

    try:
        await bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token=PAYMENT_TOKEN,
            currency=CURRENCY,
            prices=prices,
            start_parameter="subscription",
            need_name=True,
            need_phone_number=True,
            is_flexible=False,
            protect_content=True
        )
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        raise

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the pre-checkout callback."""
    query = update.pre_checkout_query
    try:
        await query.answer(ok=True)
    except Exception as e:
        logger.error(f"Pre-checkout error: {e}")
        await query.answer(ok=False, error_message="Payment processing failed. Please try again.")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful payment."""
    payment_info = update.message.successful_payment
    plan = payment_info.invoice_payload.split('_')[1].title()
    
    # Add user to paid users
    user_id = update.effective_user.id
    paid_users.add(user_id)
    
    # Update menu button for this user to point to the main app
    await context.bot.set_chat_menu_button(
        chat_id=update.effective_chat.id,
        menu_button=MenuButtonWebApp(
            text="Open App",
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
    )
    
    # Create keyboard with Mini App button
    keyboard = [
        [
            InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=MINI_APP_URL))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Thank you for your payment! Your {plan} Plan subscription is now active.\n"
        f"Amount paid: {payment_info.total_amount / 100} {payment_info.currency}\n\n"
        "Click the button below to access your subscription:",
        reply_markup=reply_markup
    )

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Add payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 