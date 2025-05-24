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
from datetime import datetime
from database import Database

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
SUBSCRIPTION_PLANS = {
    "basic": {
        "price": 6000,    # 60 RUB = 6000 kopeks
        "duration": 30,   # 30 days
        "name": "Basic Plan",
        "description": "30 days access to basic features"
    },
    "premium": {
        "price": 12000,   # 120 RUB = 12000 kopeks
        "duration": 90,   # 90 days
        "name": "Premium Plan",
        "description": "90 days access with premium features"
    },
    "pro": {
        "price": 24000,   # 240 RUB = 24000 kopeks
        "duration": 365,  # 365 days
        "name": "Pro Plan",
        "description": "1 year access with all premium features"
    }
}

# Initialize database
db = Database()

def is_subscription_active(user_id):
    return db.is_subscription_active(user_id)

def get_remaining_time(user_id):
    return db.get_remaining_time(user_id)

async def setup_menu_button(bot, chat_id=None, is_paid=False):
    """Setup the menu button with the appropriate URL based on payment status."""
    url = MINI_APP_URL if is_paid else REDIRECT_URL
    await bot.set_chat_menu_button(
        chat_id=chat_id,
        menu_button=MenuButtonWebApp(
            text="Open App",
            web_app=WebAppInfo(url=url)
        )
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    is_paid = is_subscription_active(user_id)
    
    # Setup menu button with appropriate URL
    await setup_menu_button(context.bot, update.effective_chat.id, is_paid)
    
    keyboard = [
        [
            InlineKeyboardButton("💳 Subscriptions", callback_data="subscriptions"),
        ]
    ]
    
    # Add Mini App button only for paid users
    if is_paid:
        days_left = get_remaining_time(user_id)
        keyboard.append([
            InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=MINI_APP_URL))
        ])
        keyboard.append([
            InlineKeyboardButton(f"📅 {days_left} days remaining", callback_data="profile")
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
        keyboard = []
        for plan_id, plan in SUBSCRIPTION_PLANS.items():
            duration_text = f"{plan['duration']} days"
            if plan['duration'] >= 365:
                duration_text = f"{plan['duration']//365} year"
            price_rub = plan['price'] / 100
            keyboard.append([
                InlineKeyboardButton(
                    f"{plan['name']} - {price_rub}₽/{duration_text}",
                    callback_data=f"pay_{plan_id}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("« Back", callback_data="back_to_start")
        ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "Choose your subscription plan:\n\n"
            "🔹 Basic Plan: 30 days access\n"
            "🔹 Premium Plan: 90 days access\n"
            "🔹 Pro Plan: 1 year access",
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
    if plan not in SUBSCRIPTION_PLANS:
        raise ValueError("Invalid plan")
        
    plan_data = SUBSCRIPTION_PLANS[plan]
    title = f"{plan_data['name']} Subscription"
    description = plan_data['description']
    payload = f"subscription_{plan}"
    prices = [LabeledPrice(label=plan_data['name'], amount=plan_data['price'])]

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
    plan_id = payment_info.invoice_payload.split('_')[1]
    plan_data = SUBSCRIPTION_PLANS[plan_id]
    
    user_id = update.effective_user.id
    
    # Add subscription to database
    db.add_subscription(user_id, plan_id, plan_data['duration'])
    
    # Record payment
    db.add_payment(
        user_id,
        plan_id,
        payment_info.total_amount / 100,
        payment_info.currency
    )
    
    # Update menu button for this user to point to the main app
    await context.bot.set_chat_menu_button(
        chat_id=update.effective_chat.id,
        menu_button=MenuButtonWebApp(
            text="Open App",
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
    )
    
    days_left = get_remaining_time(user_id)
    keyboard = [
        [
            InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=MINI_APP_URL))
        ],
        [
            InlineKeyboardButton(f"📅 {days_left} days remaining", callback_data="profile")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Thank you for your payment! Your {plan_data['name']} subscription is now active.\n"
        f"Amount paid: {payment_info.total_amount / 100} {payment_info.currency}\n"
        f"Duration: {plan_data['duration']} days\n\n"
        "Click the button below to access your subscription:",
        reply_markup=reply_markup
    )

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle profile button callback."""
    user_id = update.callback_query.from_user.id
    subscription = db.get_subscription(user_id)
    
    if not subscription:
        await update.callback_query.message.reply_text(
            "*📋 Your Profile*\n\n"
            "*Subscription Status:* Not Active ❌\n"
            "*Plan:* None",
            parse_mode="MarkdownV2"
        )
        return
    
    days_left = get_remaining_time(user_id)
    plan_data = SUBSCRIPTION_PLANS[subscription["plan_id"]]
    status = "Active ✅" if days_left > 0 else "Expired ❌"
    
    # Get payment history
    payment_history = db.get_payment_history(user_id)
    last_payment = payment_history[0] if payment_history else None
    
    message = (
        f"*📋 Your Profile*\n\n"
        f"*Subscription Status:* {status}\n"
        f"*Plan:* {plan_data['name']}\n"
        f"*Time Remaining:* {days_left} days\n"
    )
    
    if last_payment:
        last_payment_date = datetime.fromtimestamp(last_payment["payment_time"]).strftime("%Y-%m-%d")
        message += f"\n*Last Payment:* {last_payment['amount']} {last_payment['currency']} on {last_payment_date}"
    
    await update.callback_query.message.reply_text(
        message,
        parse_mode="MarkdownV2"
    )
    await update.callback_query.answer()

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Add payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Add profile handler
    application.add_handler(CallbackQueryHandler(profile_callback))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 