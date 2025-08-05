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

# --- تنظیمات اولیه ---
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

# --- دیتابیس ---
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

# --- وضعیت‌ها ---
(
    MENU, 
    ESTEKHARE_TOPIC, 
    GOOSHAYESH_TOPIC, 
    FAL_HAFEZ_TOPIC,
    CHOOSING_PLAN,
    WALLET_MENU
) = range(6)

# --- منوی اصلی با دکمه اشتراک ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📿 استخاره"), KeyboardButton("📜 دعای گشایش")],
        [KeyboardButton("📖 فال حافظ"), KeyboardButton("💳 اشتراک")],  # اضافه شد
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
    elif text == "💳 اشتراک":  # اضافه شد
        return await subscribe(update, context)
    elif text == "👤 حساب کاربری":
        return await account_handler(update, context)
    elif text == "💰 کیف پول":
        return await wallet_handler(update, context)
    else:
        await update.message.reply_text("لطفاً یک گزینه معتبر انتخاب کنید.")
        return MENU

# --- بقیه توابع بدون تغییر ---
# [همان توابع account_handler, wallet_handler, subscribe, choose_plan, 
# handle_payment, estekhare_handler, gooshayesh_handler, hafez_handler, cancel 
# که در کد قبلی وجود داشتند]

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
