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
            subscription_expiry DATE
        )
    """)
    conn.commit()
    conn.close()

# فراخوانی هنگام شروع ربات
init_db()

# --- پلن‌های اشتراک ---
SUBSCRIPTION_PLANS = {
    "monthly": {"price": 50000, "days": 30},
    "3months": {"price": 120000, "days": 90},
    "6months": {"price": 200000, "days": 180},
    "yearly": {"price": 350000, "days": 365}
}

# وضعیت‌ها
MENU, ESTEKHARE_TOPIC, GOOSHAYESH_TOPIC, FAL_HAFEZ_TOPIC = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📿 استخاره"), KeyboardButton("📜 دعای گشایش")],
        [KeyboardButton("📖 فال حافظ")]
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
    else:
        await update.message.reply_text("یکی از گزینه‌های منو را انتخاب کن.")
        return MENU

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
    await update.message.reply_text("گفتگو لغو شد.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)],
            ESTEKHARE_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, estekhare_handler)],
            GOOSHAYESH_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, gooshayesh_handler)],
            FAL_HAFEZ_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, hafez_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱ ماهه - ۵۰ هزار تومان")],
        [KeyboardButton("۳ ماهه - ۱۲۰ هزار تومان")],
        [KeyboardButton("۶ ماهه - ۲۰۰ هزار تومان")],
        [KeyboardButton("۱ ساله - ۳۵۰ هزار تومان")],
        [KeyboardButton("🔙 برگشت")]
    ]
    await update.message.reply_text(
        "پلن مورد نظر را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return "CHOOSING_PLAN"
    async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, plan: str):
    user_id = update.effective_user.id
    amount = SUBSCRIPTION_PLANS[plan]["price"]
    
    # درخواست به زیبال
    response = requests.post(
        "https://api.zibal.ir/v1/request",
        json={
            "merchant": "ZIBAL_MERCHANT_ID",  # جایگزین کن با مرچنت کد خودت!
            "amount": amount,
            "callbackUrl": "https://your-domain.com/callback",  # جایگزین کن با آدرس ریلوی تو
            "description": f"اشتراک {plan}",
        },
    )
    
    if response.json().get("result") == 100:
        payment_url = f"https://gateway.zibal.ir/start/{response.json()['trackId']}"
        await update.message.reply_text(f"✅ برای پرداخت به لینک زیر بروید:\n\n{payment_url}")
    else:
        await update.message.reply_text("❌ خطا در اتصال به درگاه پرداخت.")

    async def choose_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
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
    return ConversationHandler.END
    
def main():
    app = Application.builder().token(TOKEN).build()
    
    # هندلر مکالمه اصلی
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)],
            ESTEKHARE_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, estekhare_handler)],
            GOOSHAYESH_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, gooshayesh_handler)],
            FAL_HAFEZ_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, hafez_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # هندلر اشتراک
    payment_conv = ConversationHandler(
        entry_points=[CommandHandler("subscribe", subscribe)],
        states={
            "CHOOSING_PLAN": [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_plan)]
        },
        fallbacks=[]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(payment_conv)
    app.run_polling()
