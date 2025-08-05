import os
import json
import sqlite3
import random
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
MERCHANT_KEY = os.environ.get("ZIBAL_MERCHANT_KEY")  # کلید درگاه زیبال
CARD_NUMBER = "6037-XXXX-XXXX-XXXX"  # شماره کارت برای پرداخت کارت به کارت

if not TOKEN:
    raise ValueError("BOT_TOKEN is missing!")

# --- تعرفه‌ها ---
SERVICE_PRICES = {
    "estekhare": 5000,
    "gooshayesh": 7000,
    "hafez": 10000
}

SUBSCRIPTION_PLANS = {
    "monthly": {"price": 30000, "days": 30},
    "yearly": {"price": 250000, "days": 365}
}

# --- دیتابیس ---
def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            subscription_expiry DATE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            type TEXT,  # 'charge', 'payment', 'subscription'
            status TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ref_id TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- وضعیت‌های گفتگو ---
(
    MENU,
    SERVICE_SELECTION,
    PAYMENT_METHOD,
    CHARGE_AMOUNT,
    CARD_PAYMENT,
    SUBSCRIPTION_PLAN,
    WAITING_RECEIPT
) = range(7)

# --- منوی اصلی ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, subscription_expiry FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone() or (0, None)
    conn.close()

    keyboard = [
        [KeyboardButton("📿 استخاره"), KeyboardButton("📜 دعای گشایش")],
        [KeyboardButton("📖 فال حافظ")],
        [KeyboardButton("💰 کیف پول"), KeyboardButton("🔔 اشتراک")],
        [KeyboardButton("📋 تاریخچه پرداخت‌ها")]
    ]
    
    message = (
        f"💰 موجودی: {user_data[0]:,} تومان\n"
        f"🔔 اشتراک: {'فعال تا ' + user_data[1] if user_data[1] and datetime.strptime(user_data[1], '%Y-%m-%d') > datetime.now() else 'غیرفعال'}\n\n"
        "لطفا گزینه مورد نظر را انتخاب کنید:"
    )
    
    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MENU

# --- سیستم پرداخت ---
async def handle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_map = {
        "📿 استخاره": ("estekhare", SERVICE_PRICES["estekhare"]),
        "📜 دعای گشایش": ("gooshayesh", SERVICE_PRICES["gooshayesh"]),
        "📖 فال حافظ": ("hafez", SERVICE_PRICES["hafez"])
    }
    
    if update.message.text in service_map:
        service, price = service_map[update.message.text]
        user_id = update.effective_user.id
        
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT balance, subscription_expiry FROM users WHERE user_id = ?", (user_id,))
        balance, expiry = cursor.fetchone() or (0, None)
        
        # بررسی اشتراک فعال
        if expiry and datetime.strptime(expiry, "%Y-%m-%d") > datetime.now():
            await deliver_service(update, service)
        # بررسی موجودی
        elif balance >= price:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
            cursor.execute("""
                INSERT INTO transactions (user_id, amount, type, status)
                VALUES (?, ?, 'payment', 'completed')
            """, (user_id, price, service))
            conn.commit()
            await deliver_service(update, service)
        else:
            await update.message.reply_text(
                f"موجودی کافی نیست!\nقیمت سرویس: {price:,} تومان\nموجودی شما: {balance:,} تومان\n\n"
                "لطفاً از بخش کیف پول اقدام به شارژ کنید."
            )
        conn.close()
    return MENU

async def deliver_service(update: Update, service: str):
    with open(f'{service}.json', encoding='utf-8') as f:
        data = json.load(f)
    result = random.choice(list(data.values()))
    
    await update.message.reply_text(
        f"🔮 نتیجه {service}:\n\n{result}\n\n"
        "برای استفاده مجدد /start را بزنید"
    )

# --- سیستم کیف پول و اشتراک ---
async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("➕ شارژ کیف پول")],
        [KeyboardButton("🔙 بازگشت")]
    ]
    await update.message.reply_text(
        "مدیریت کیف پول:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return PAYMENT_METHOD

async def payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "➕ شارژ کیف پول":
        keyboard = [
            [KeyboardButton("💳 درگاه پرداخت"), KeyboardButton("📲 کارت به کارت")],
            [KeyboardButton("🔙 بازگشت")]
        ]
        await update.message.reply_text(
            "روش شارژ را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return CHARGE_AMOUNT
    return MENU

async def charge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "💳 درگاه پرداخت":
        await update.message.reply_text("مبلغ مورد نظر برای شارژ را وارد کنید (تومان):")
        return CHARGE_AMOUNT
    elif update.message.text == "📲 کارت به کارت":
        await update.message.reply_text(
            f"💳 برای شارژ کیف پول:\n\n"
            f"شماره کارت: {CARD_NUMBER}\n"
            f"به نام: [نام صاحب کارت]\n\n"
            "پس از واریز، تصویر رسید را ارسال کنید."
        )
        return WAITING_RECEIPT
    return MENU

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        if amount < 10000:
            await update.message.reply_text("حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است.")
            return CHARGE_AMOUNT
            
        response = requests.post(
            "https://api.zibal.ir/v1/request",
            json={
                "merchant": MERCHANT_KEY,
                "amount": amount,
                "callbackUrl": f"https://yourdomain.com/callback/{update.effective_user.id}",
                "description": "شارژ کیف پول ربات"
            },
            timeout=10
        )
        
        if response.json().get("result") == 100:
            track_id = response.json()["trackId"]
            conn = sqlite3.connect("bot.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transactions 
                (user_id, amount, type, status, ref_id)
                VALUES (?, ?, 'charge', 'pending', ?)
            """, (update.effective_user.id, amount, track_id))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                f"برای پرداخت {amount:,} تومان به لینک زیر مراجعه کنید:\n\n"
                f"https://gateway.zibal.ir/start/{track_id}\n\n"
                "پس از پرداخت، موجودی شما اضافه خواهد شد."
            )
        else:
            await update.message.reply_text("خطا در اتصال به درگاه پرداخت")
    except ValueError:
        await update.message.reply_text("لطفاً فقط عدد وارد کنید!")
    return MENU

async def verify_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text(
            "رسید پرداخت دریافت شد و در حال بررسی است.\n"
            "پس از تایید، موجودی کیف پول شما اضافه خواهد شد."
        )
        # اینجا می‌توانید سیستم تایید دستی پیاده‌سازی کنید
    return MENU

# --- سیستم اشتراک ---
async def subscription_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱ ماهه - ۳۰,۰۰۰ تومان")],
        [KeyboardButton("۱ ساله - ۲۵۰,۰۰۰ تومان")],
        [KeyboardButton("🔙 بازگشت")]
    ]
    await update.message.reply_text(
        "پلن اشتراک را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SUBSCRIPTION_PLAN

async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_map = {
        "۱ ماهه - ۳۰,۰۰۰ تومان": ("monthly", 30000),
        "۱ ساله - ۲۵۰,۰۰۰ تومان": ("yearly", 250000)
    }
    
    if update.message.text in plan_map:
        plan, price = plan_map[update.message.text]
        user_id = update.effective_user.id
        
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0] or 0
        
        if balance >= price:
            expiry_date = (datetime.now() + timedelta(days=SUBSCRIPTION_PLANS[plan]["days"])).strftime("%Y-%m-%d")
            cursor.execute("UPDATE users SET balance = balance - ?, subscription_expiry = ? WHERE user_id = ?", 
                          (price, expiry_date, user_id))
            cursor.execute("""
                INSERT INTO transactions (user_id, amount, type, status)
                VALUES (?, ?, 'subscription', 'completed')
            """, (user_id, price))
            conn.commit()
            await update.message.reply_text(
                f"✅ اشتراک {plan} با موفقیت فعال شد!\n"
                f"تاریخ انقضا: {expiry_date}"
            )
        else:
            await update.message.reply_text(
                f"موجودی کافی نیست!\nقیمت اشتراک: {price:,} تومان\nموجودی شما: {balance:,} تومان"
            )
        conn.close()
    return MENU

# --- تابع اصلی ---
def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU: [
                MessageHandler(filters.Regex("^(📿 استخاره|📜 دعای گشایش|📖 فال حافظ)$"), handle_service),
                MessageHandler(filters.Regex("^💰 کیف پول$"), wallet_menu),
                MessageHandler(filters.Regex("^🔔 اشتراک$"), subscription_menu),
            ],
            PAYMENT_METHOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, payment_method),
            ],
            CHARGE_AMOUNT: [
                MessageHandler(filters.Regex("^💳 درگاه پرداخت$"), charge_amount),
                MessageHandler(filters.Regex("^📲 کارت به کارت$"), charge_amount),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_payment),
            ],
            SUBSCRIPTION_PLAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subscription),
            ],
            WAITING_RECEIPT: [
                MessageHandler(filters.PHOTO, verify_receipt),
            ],
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: start(u,c))]
    )
    
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
