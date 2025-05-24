import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, WebAppInfo, MenuButtonWebApp, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from datetime import datetime, timedelta
from database import Database
from prettytable import PrettyTable
import sqlite3

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

# Video path for welcome message
WELCOME_VIDEO = os.path.join("media", "IMG_6277.MOV")  # Video file in media directory

# Payment configurations
CURRENCY = "RUB"
SUBSCRIPTION_PLANS = {
    "test": {
        "price": 6000,     # 60 RUB = 6000 kopeks (minimum allowed price)
        "duration": 1/1440,  # 1 minute (1 day = 1440 minutes)
        "name": "Test Plan",
        "description": "1 minute test access"
    },
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

# Add after other constants
ADMIN_IDS = {int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",")} if os.getenv("ADMIN_IDS") else set()

def is_subscription_active(user_id):
    return db.is_subscription_active(user_id)

def get_remaining_time(user_id):
    days = db.get_remaining_time(user_id)
    if days < 1:  # If less than a day
        minutes = int(days * 24 * 60)  # Convert to minutes
        if minutes <= 0:
            return "expired"
        return f"{minutes} min"
    return f"{int(days)} days"

async def setup_menu_button(bot, chat_id=None, is_paid=False):
    """Setup the menu button with the appropriate URL based on payment status."""
    try:
        # Base URL for the redirect page
        base_url = "https://falsefood.github.io/telegram-mini-app/redirect.html"
        
        # Add subscription status as access parameter
        url = f"{base_url}?access={'true' if is_paid else 'false'}"
        
        logger.info(f"Setting up menu button for chat_id {chat_id} with URL: {url}")
        
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(
                text="Open App",
                web_app=WebAppInfo(url=url)
            )
        )
        logger.info("Menu button setup successful")
        
    except Exception as e:
        logger.error(f"Error setting up menu button: {e}")
        # Try to set up a basic menu button without parameters
        try:
            await bot.set_chat_menu_button(
                chat_id=chat_id,
                menu_button=MenuButtonWebApp(
                    text="Open App",
                    web_app=WebAppInfo(url=base_url)
                )
            )
        except Exception as e2:
            logger.error(f"Error setting up fallback menu button: {e2}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    # Delete previous messages if they exist
    try:
        # Try to delete the message that triggered the command
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Could not delete trigger message: {e}")

    user_id = update.effective_user.id
    subscription = db.get_subscription(user_id)
    is_paid = is_subscription_active(user_id)
    
    # Setup menu button with appropriate URL
    await setup_menu_button(context.bot, update.effective_chat.id, is_paid)
    
    keyboard = []
    
    if subscription:
        # User has or had a subscription - show text only
        if is_paid:
            # Active subscription
            current_plan = subscription["plan_id"]
            days_left = get_remaining_time(user_id)
            
            # Only show upgrade button if not on the highest plan
            if current_plan != "pro":
                keyboard.append([
                    InlineKeyboardButton("⬆️ Upgrade Plan", callback_data="upgrade_subscription")
                ])
            
            keyboard.append([
                InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=MINI_APP_URL))
            ])
            keyboard.append([
                InlineKeyboardButton(f"📅 {days_left} remaining", callback_data="profile")
            ])
            
            caption_text = (
                "🎉 *Welcome to our service\\!*\n\n"
                "Your subscription is active\\.\n"
                f"*Current Plan:* {SUBSCRIPTION_PLANS[current_plan]['name']}\n"
                f"*Time Left:* {days_left}"
            )
            
            # Send text message for active subscription
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Expired subscription
            last_plan = subscription["plan_id"]
            keyboard.append([
                InlineKeyboardButton("🔄 Renew Subscription", callback_data="subscriptions")
            ])
            
            # Get last payment info
            payment_history = db.get_payment_history(user_id)
            last_payment = payment_history[0] if payment_history else None
            last_payment_date = (
                datetime.fromtimestamp(last_payment["payment_time"]).strftime("%Y\\-%m\\-%d")
                if last_payment else "N/A"
            )
            
            caption_text = (
                "⚠️ *Subscription Expired*\n\n"
                f"*Previous Plan:* {SUBSCRIPTION_PLANS[last_plan]['name']}\n"
                f"*Last Payment:* {last_payment_date}\n\n"
                "To continue using our service, please renew your subscription\\."
            )
            
            # Send text message for expired subscription
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        # No subscription history - new user, show video
        keyboard = [[
            InlineKeyboardButton("💳 Subscribe Now", callback_data="subscriptions")
        ]]
        caption_text = "🎉 *Welcome to our service\\!*\n\nClick the button below to view available subscription plans:"
        
        # Try to send welcome video for new users only
        try:
            if os.path.exists(WELCOME_VIDEO):
                with open(WELCOME_VIDEO, 'rb') as video:
                    await context.bot.send_video(
                        chat_id=update.effective_chat.id,
                        video=video,
                        caption=caption_text,
                        parse_mode="MarkdownV2",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        supports_streaming=True,
                        width=1920,
                        height=1080
                    )
            else:
                logger.warning(f"Welcome video not found at path: {WELCOME_VIDEO}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=caption_text,
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks."""
    query = update.callback_query
    await query.answer()

    if query.data == "subscriptions" or query.data == "upgrade_subscription":
        user_id = update.effective_user.id
        subscription = db.get_subscription(user_id) if query.data == "upgrade_subscription" else None
        current_plan = subscription["plan_id"] if subscription else None
        
        keyboard = []
        
        # Always show test plan first if not upgrading
        if query.data != "upgrade_subscription":
            plan = SUBSCRIPTION_PLANS["test"]
            keyboard.append([
                InlineKeyboardButton(
                    f"🔬 {plan['name']} - {plan['price']/100}₽/1min (For Testing)",
                    callback_data="pay_test"
                )
            ])
            keyboard.append([
                InlineKeyboardButton("──────────────", callback_data="none")
            ])
        
        for plan_id, plan in SUBSCRIPTION_PLANS.items():
            # Skip test plan as it's handled above
            if plan_id == "test":
                continue
                
            # Skip current plan and lower plans when upgrading
            if current_plan and (plan_id == current_plan or 
                               (current_plan == "premium" and plan_id == "basic") or
                               (current_plan == "pro")):
                continue
                
            duration_text = f"{plan['duration']} days"
            if plan['duration'] >= 365:
                duration_text = f"{plan['duration']//365} year"
            price_rub = plan['price'] / 100
            
            button_text = f"{plan['name']} - {price_rub}₽/{duration_text}"
            if query.data == "upgrade_subscription":
                button_text = f"⬆️ Upgrade to {button_text}"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"pay_{plan_id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("« Back", callback_data="back_to_start")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = "Choose your subscription plan:\n\n"
        if query.data == "upgrade_subscription":
            message_text = "Choose your upgrade plan:\n\n"
        else:
            message_text = "Choose your subscription plan:\n\n"
            message_text += "🔬 Test Plan: 1 minute access (for testing)\n"
            message_text += "──────────────\n"
            
        message_text += "🔹 Basic Plan: 30 days access\n"
        message_text += "🔹 Premium Plan: 90 days access\n"
        message_text += "🔹 Pro Plan: 1 year access"
        
        try:
            await query.message.edit_text(
                message_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await query.message.reply_text(
                message_text,
                reply_markup=reply_markup
            )
    elif query.data == "none":
        # Do nothing for separator button
        return
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
        # Get current subscription status
        user_id = update.effective_user.id
        subscription = db.get_subscription(user_id)
        is_paid = is_subscription_active(user_id)
        
        keyboard = []
        caption_text = "Welcome to the bot\\! "
        
        try:
            # Delete the current message
            await query.message.delete()
            
            if subscription:
                # User has or had a subscription - show text only
                if is_paid:
                    # Active subscription
                    current_plan = subscription["plan_id"]
                    days_left = get_remaining_time(user_id)
                    
                    # Only show upgrade button if not on the highest plan
                    if current_plan != "pro":
                        keyboard.append([
                            InlineKeyboardButton("⬆️ Upgrade Plan", callback_data="upgrade_subscription")
                        ])
                    
                    keyboard.append([
                        InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=MINI_APP_URL))
                    ])
                    keyboard.append([
                        InlineKeyboardButton(f"📅 {days_left} remaining", callback_data="profile")
                    ])
                    
                    caption_text = (
                        "🎉 *Welcome to our service\\!*\n\n"
                        "Your subscription is active\\.\n"
                        f"*Current Plan:* {SUBSCRIPTION_PLANS[current_plan]['name']}\n"
                        f"*Time Left:* {days_left}"
                    )
                    
                    # Send text message for active subscription
                    sent_message = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=caption_text,
                        parse_mode="MarkdownV2",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    # Expired subscription
                    last_plan = subscription["plan_id"]
                    keyboard.append([
                        InlineKeyboardButton("🔄 Renew Subscription", callback_data="subscriptions")
                    ])
                    
                    # Get last payment info
                    payment_history = db.get_payment_history(user_id)
                    last_payment = payment_history[0] if payment_history else None
                    last_payment_date = (
                        datetime.fromtimestamp(last_payment["payment_time"]).strftime("%Y\\-%m\\-%d")
                        if last_payment else "N/A"
                    )
                    
                    caption_text = (
                        "⚠️ *Subscription Expired*\n\n"
                        f"*Previous Plan:* {SUBSCRIPTION_PLANS[last_plan]['name']}\n"
                        f"*Last Payment:* {last_payment_date}\n\n"
                        "To continue using our service, please renew your subscription\\."
                    )
                    
                    # Send text message for expired subscription
                    sent_message = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=caption_text,
                        parse_mode="MarkdownV2",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
            else:
                # No subscription history - new user, show video
                keyboard = [[
                    InlineKeyboardButton("💳 Subscribe Now", callback_data="subscriptions")
                ]]
                caption_text = "🎉 *Welcome to our service\\!*\n\nClick the button below to view available subscription plans:"
                
                # Try to send welcome video for new users only
                if os.path.exists(WELCOME_VIDEO):
                    with open(WELCOME_VIDEO, 'rb') as video:
                        sent_message = await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=video,
                            caption=caption_text,
                            parse_mode="MarkdownV2",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            supports_streaming=True,
                            width=1920,
                            height=1080
                        )
                else:
                    logger.warning(f"Welcome video not found at path: {WELCOME_VIDEO}")
                    sent_message = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=caption_text,
                        parse_mode="MarkdownV2",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
            
            # Store the message ID in user data to track it
            if not context.user_data.get('message_ids'):
                context.user_data['message_ids'] = set()
            context.user_data['message_ids'].add(sent_message.message_id)
            
        except Exception as e:
            logger.error(f"Error handling back button: {e}")
            # Fallback to simple message if something goes wrong
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

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
    status = "Active ✅" if days_left != "expired" else "Expired ❌"
    
    # Get payment history
    payment_history = db.get_payment_history(user_id)
    last_payment = payment_history[0] if payment_history else None
    
    message = (
        f"*📋 Your Profile*\n\n"
        f"*Subscription Status:* {status}\n"
        f"*Plan:* {plan_data['name']}\n"
        f"*Time Remaining:* {days_left}\n"
    )
    
    if last_payment:
        last_payment_date = datetime.fromtimestamp(last_payment["payment_time"]).strftime("%Y-%m-%d")
        message += f"\n*Last Payment:* {last_payment['amount']} {last_payment['currency']} on {last_payment_date}"
    
    await update.callback_query.message.reply_text(
        message,
        parse_mode="MarkdownV2"
    )
    await update.callback_query.answer()

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to view and manage database contents."""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ You are not authorized to use admin commands.")
        return

    # Check if there are any command arguments
    if context.args:
        if context.args[0] == "delete" and len(context.args) > 1:
            try:
                user_to_delete = int(context.args[1])
                # Delete user's subscription
                with sqlite3.connect(db.db_file) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_to_delete,))
                    conn.commit()
                await update.message.reply_text(f"✅ User {user_to_delete} has been removed from subscriptions.")
                return
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID. Please provide a valid number.")
                return
            except sqlite3.Error as e:
                await update.message.reply_text(f"❌ Database error: {str(e)}")
                return
    
    # Get all subscriptions
    with sqlite3.connect(db.db_file) as conn:
        cursor = conn.cursor()
        
        # Get subscriptions with user info from context
        cursor.execute("SELECT * FROM subscriptions")
        subscriptions = cursor.fetchall()
        
        # Get payments
        cursor.execute("SELECT * FROM payments")
        payments = cursor.fetchall()
        
        # Create subscription table
        sub_table = PrettyTable()
        sub_table.field_names = ["User ID", "Username", "Name", "Plan", "Purchase Date", "Expiry Date", "Status"]
        
        for sub in subscriptions:
            user_id = sub[0]
            try:
                # Try to get user info from Telegram
                user = await context.bot.get_chat(user_id)
                username = user.username or "N/A"
                name = user.first_name
                if user.last_name:
                    name += f" {user.last_name}"
            except:
                username = "N/A"
                name = "Unknown"
            
            purchase_date = datetime.fromtimestamp(sub[2]).strftime("%Y-%m-%d")
            expiry_date = datetime.fromtimestamp(sub[3]).strftime("%Y-%m-%d")
            is_active = "Active ✅" if sub[3] > datetime.now().timestamp() else "Expired ❌"
            sub_table.add_row([user_id, username, name, sub[1], purchase_date, expiry_date, is_active])
        
        # Create payments table
        pay_table = PrettyTable()
        pay_table.field_names = ["ID", "User ID", "Username", "Plan", "Amount", "Currency", "Date"]
        
        for payment in payments:
            user_id = payment[1]
            try:
                user = await context.bot.get_chat(user_id)
                username = user.username or "N/A"
            except:
                username = "N/A"
            
            payment_date = datetime.fromtimestamp(payment[5]).strftime("%Y-%m-%d")
            pay_table.add_row([
                payment[0], user_id, username, payment[2],
                payment[3], payment[4], payment_date
            ])
        
        # Send tables and instructions
        help_text = (
            "*Admin Commands:*\n"
            "• `/admin` \\- View all data\n"
            "• `/admin delete USER_ID` \\- Remove user's subscription\n"
            "\n"
            "*Current Data:*\n"
        )
        
        await update.message.reply_text(
            help_text + 
            "\n*Active Subscriptions:*\n"
            f"```\n{sub_table}\n```\n\n"
            "*Payment History:*\n"
            f"```\n{pay_table}\n```",
            parse_mode="MarkdownV2"
        )

# Add this new command handler function
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user their Telegram ID."""
    user = update.effective_user
    await update.message.reply_text(
        f"Your Telegram ID is: `{user.id}`\n"
        f"Add this ID to your .env file as:\n"
        f"`ADMIN_IDS={user.id}`",
        parse_mode="MarkdownV2"
    )

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to check subscription status."""
    user_id = update.effective_user.id
    subscription = db.get_subscription(user_id)
    
    if not subscription:
        keyboard = [
            [InlineKeyboardButton("💳 Get Subscription", callback_data="subscriptions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ You don't have any active subscriptions.\n"
            "Click below to view available plans:",
            reply_markup=reply_markup
        )
        return
    
    days_left = get_remaining_time(user_id)
    plan_data = SUBSCRIPTION_PLANS[subscription["plan_id"]]
    
    if days_left == "expired":
        keyboard = [
            [InlineKeyboardButton("🔄 Renew Subscription", callback_data="subscriptions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ Your subscription has expired!\n\n"
            f"*Previous Plan:* {plan_data['name']}\n"
            "*Status:* Expired ❌\n\n"
            "Click below to renew your subscription:",
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🔄 Extend Subscription", callback_data="subscriptions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"*Subscription Status*\n\n"
            f"*Current Plan:* {plan_data['name']}\n"
            f"*Status:* Active ✅\n"
            f"*Days Remaining:* {days_left}\n\n"
            f"Click below to extend your subscription:",
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

async def check_expired_subscriptions(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check for expired subscriptions and notify users."""
    try:
        with sqlite3.connect(db.db_file) as conn:
            cursor = conn.cursor()
            current_time = datetime.now().timestamp()
            
            # Get subscriptions that expired in the last 24 hours
            yesterday = current_time - 24*60*60
            cursor.execute("""
                SELECT user_id, plan_id, expiry_date 
                FROM subscriptions 
                WHERE expiry_date BETWEEN ? AND ?
                AND notified = 0  -- Only get non-notified expirations
            """, (yesterday, current_time))
            
            expired_subs = cursor.fetchall()
            
            for user_id, plan_id, expiry_date in expired_subs:
                plan_data = SUBSCRIPTION_PLANS[plan_id]
                keyboard = [
                    [InlineKeyboardButton("🔄 Renew Subscription", callback_data="subscriptions")],
                    [InlineKeyboardButton("👤 View Profile", callback_data="profile")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            "⚠️ *Your Subscription Has Expired\\!*\n\n"
                            f"*Previous Plan:* {plan_data['name']}\n"
                            "*Status:* Expired ❌\n\n"
                            "To continue using our service, please renew your subscription\\."
                        ),
                        parse_mode="MarkdownV2",
                        reply_markup=reply_markup
                    )
                    
                    # Mark as notified in database
                    cursor.execute("""
                        UPDATE subscriptions 
                        SET notified = 1 
                        WHERE user_id = ? AND expiry_date = ?
                    """, (user_id, expiry_date))
                    conn.commit()
                    
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id} about expired subscription: {e}")
                    
    except Exception as e:
        logger.error(f"Error in check_expired_subscriptions: {e}")

# Add this new command handler function
async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if user has access when they try to use the bot."""
    user_id = update.effective_user.id
    subscription = db.get_subscription(user_id)
    
    if not subscription or not is_subscription_active(user_id):
        keyboard = [
            [InlineKeyboardButton("💳 Get Subscription", callback_data="subscriptions")],
            [InlineKeyboardButton("👤 View Profile", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ *Access Restricted*\n\n"
            "Your subscription has expired or is not active\\. "
            "To continue using our service, please get a subscription\\.",
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )
        return False
    return True

def main() -> None:
    """Start the bot."""
    # Build the application with job queue
    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("subscription", check_subscription))
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Add payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Add profile handler
    application.add_handler(CallbackQueryHandler(profile_callback))

    # Add admin command
    application.add_handler(CommandHandler("admin", admin_command))

    # Schedule the subscription check job (run every minute for testing)
    if application.job_queue:
        application.job_queue.run_repeating(
            callback=check_expired_subscriptions,
            interval=60.0,  # Check every minute
            first=10.0
        )
    else:
        logger.warning("Job queue is not available. Subscription expiration checks will not run automatically.")

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 