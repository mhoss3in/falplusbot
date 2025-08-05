import os
import json
import sqlite3
from datetime import datetime, timedelta
import requests
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is missing!")

# لود داده‌ها
with open('estekhare.json', encoding='utf-8') as f:
    estekhare_data = json.load(f)

with open('gooshayesh.json', encoding='utf-8') as f:
    gooshayesh_data = json.load(f)

with open('hafez.json', encoding='utf-8') as f:
    hafez_data = json.load(f)

# --- تنظیمات دیتابیس ---
def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            phone TEXT,
            subscription_expiry DATE,
            wallet_balance INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- پلن‌های اشتراک ---
SUBSCRIPTION_PLANS = {
    "monthly": {"price": 50000, "days": 30},
    "3months": {"price": 120000, "days": 90},
    "6months": {"price": 200000, "days": 180},
    "yearly": {"price": 350000, "days": 365}
}

# وضعیت‌ها
(
    MENU, 
    ESTEKHARE_TOPIC, 
    GOOSHAYESH_TOPIC, 
    FAL_HAFEZ_TOPIC,
    CHOOSING_PLAN,
    WALLET_MENU
) = range(6)

# --- توابع اصلی ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📿 استخاره"), KeyboardButton("📜 دعای گشایش")],
        [KeyboardButton("📖 فال حافظ")],
        [KeyboardButton("👤 حساب کاربری"), KeyboardButton("💰 کیف پول")]
    ]
    await update.message.reply_text(
        "سلام! یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📿 استخاره":
        await update.message.reply_text("موضوع استخاره را وارد کن:")
        return ESTEKHARE_TOPIC
    elif text == "📜 دعای گشایش":
        await update.message.reply_text("موضوع دعا را وارد کن:")
        return GOOSHAYESH_TOPIC
    elif text == "📖 فال حافظ":
        await update.message.reply_text("موضوع موردنظر برای فال حافظ را وارد کن:")
        return FAL_HAFEZ_TOPIC
    elif text == "👤 حساب کاربری":
        return await account_handler(update, context)
    elif text == "💰 کیف پول":
        return await wallet_handler(update, context)
    else:
        await update.message.reply_text("لطفاً یک گزینه معتبر انتخاب کنید.")
        return MENU

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT subscription_expiry, wallet_balance FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if user_data:
        expiry_date = user_data[0] or "فعال نیست"
        balance = user_data[1] or 0
    else:
        expiry_date = "فعال نیست"
        balance = 0
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
    
    conn.close()
    
    await update.message.reply_text(
        f"👤 اطلاعات حساب کاربری:\n\n"
        f"📅 اشتراک: {expiry_date}\n"
        f"💰 موجودی کیف پول: {balance:,} تومان\n\n"
        f"برای بازگشت /start را بزنید"
    )
    return MENU

async def wallet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("➕ افزایش اعتبار")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    await update.message.reply_text(
        "💰 مدیریت کیف پول:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return WALLET_MENU

async def wallet_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 بازگشت به منوی اصلی":
        return await start(update, context)
    elif text == "➕ افزایش اعتبار":
        await update.message.reply_text("این بخش در حال توسعه است...")
        return WALLET_MENU
    else:
        await update.message.reply_text("لطفاً یک گزینه معتبر انتخاب کنید.")
        return WALLET_MENU

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱ ماهه - ۵۰ هزار تومان")],
        [KeyboardButton("۳ ماهه - ۱۲۰ هزار تومان")],
        [KeyboardButton("۶ ماهه - ۲۰۰ هزار تومان")],
        [KeyboardButton("۱ ساله - ۳۵۰ هزار تومان")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    await update.message.reply_text(
        "پلن مورد نظر را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSING_PLAN

async def choose_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 بازگشت به منوی اصلی":
        return await start(update, context)
    
    plan_mapping = {
        "۱ ماهه - ۵۰ هزار تومان": "monthly",
        "۳ ماهه - ۱۲۰ هزار تومان": "3months",
        "۶ ماهه - ۲۰۰ هزار تومان": "6months",
        "۱ ساله - ۳۵۰ هزار تومان": "yearly"
    }
    
    plan = plan_mapping.get(text)
    if plan:
        await handle_payment(update, context, plan)
    else:
        await update.message.reply_text("لطفاً یک گزینه معتبر انتخاب کنید.")
    return CHOOSING_PLAN

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, plan: str):
    amount = SUBSCRIPTION_PLANS[plan]["price"]
    
    # در اینجا می‌توانید درگاه پرداخت خود را پیاده‌سازی کنید
    await update.message.reply_text(
        f"✅ در حال اتصال به درگاه پرداخت برای اشتراک {plan} به مبلغ {amount:,} تومان...\n\n"
        "این بخش در حال توسعه است. برای تست می‌توانید از دکمه بازگشت استفاده کنید."
    )

async def estekhare_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    result = estekhare_data.get(topic, "موضوعی با این عنوان پیدا نشد.")
    await update.message.reply_text(result)
    return MENU

async def gooshayesh_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    result = gooshayesh_data.get(topic, "موضوعی با این عنوان پیدا نشد.")
    await update.message.reply_text(result)
    return MENU

async def hafez_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    result = hafez_data.get(topic, "موضوعی با این عنوان پیدا نشد.")
    await update.message.reply_text(result)
    return MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler),
            ],
            ESTEKHARE_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, estekhare_handler),
            ],
            GOOSHAYESH_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gooshayesh_handler),
            ],
            FAL_HAFEZ_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, hafez_handler),
            ],
            CHOOSING_PLAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_plan),
            ],
            WALLET_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_menu_handler),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
