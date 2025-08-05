import os
import json
import sqlite3
import random
from datetime import datetime, timedelta
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# --- تنظیمات پایه ---
TOKEN = os.environ.get("BOT_TOKEN")
MERCHANT_KEY = "zibal_merchant_key"
ADMIN_CARD = "6037-XXXX-XXXX-XXXX"

if not TOKEN:
    raise ValueError("توکن ربات تنظیم نشده است!")

# --- تعرفه‌ها و پلن‌ها ---
PRICES = {
    "estekhare": 5000,
    "gooshayesh": 7000,
    "hafez": 10000
}

SUBSCRIPTIONS = {
    "monthly": {"price": 30000, "days": 30},
    "3months": {"price": 80000, "days": 90},
    "6months": {"price": 150000, "days": 180},
    "yearly": {"price": 250000, "days": 365}
}

# --- وضعیت‌های مکالمه ---
(MAIN_MENU, SERVICE_SELECTION, 
 PAYMENT_METHOD, CHARGE_AMOUNT,
 SUBSCRIPTION_MENU, CONFIRM_PAYMENT) = range(6)

# --- توابع دیتابیس ---
def init_db():
    with sqlite3.connect("bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                subscription_expiry TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                status TEXT,
                date TEXT DEFAULT CURRENT_TIMESTAMP,
                ref_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

def get_user(user_id):
    with sqlite3.connect("bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def update_balance(user_id, amount):
    with sqlite3.connect("bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)
        """, (user_id,))
        cursor.execute("""
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        """, (amount, user_id))
        conn.commit()

# --- توابع اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    balance = user[1] if user else 0
    sub_expiry = user[2] if user and user[2] else "غیرفعال"

    keyboard = [
        [KeyboardButton("📿 استخاره"), KeyboardButton("📜 دعای گشایش")],
        [KeyboardButton("📖 فال حافظ")],
        [KeyboardButton("💰 کیف پول"), KeyboardButton("🔔 اشتراک")],
        [KeyboardButton("📋 تاریخچه پرداخت‌ها")]
    ]
    
    await update.message.reply_text(
        f"💰 موجودی: {balance:,} تومان\n"
        f"🔔 اشتراک: {sub_expiry}\n\n"
        "لطفا گزینه مورد نظر را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MAIN_MENU

async def handle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_map = {
        "📿 استخاره": ("estekhare", PRICES["estekhare"]),
        "📜 دعای گشایش": ("gooshayesh", PRICES["gooshayesh"]),
        "📖 فال حافظ": ("hafez", PRICES["hafez"])
    }
    
    if update.message.text in service_map:
        service, price = service_map[update.message.text]
        user_id = update.effective_user.id
        user = get_user(user_id)
        
        if user and user[2] and datetime.strptime(user[2], "%Y-%m-%d") > datetime.now():
            await deliver_service(update, service)
        elif user and user[1] >= price:
            update_balance(user_id, -price)
            await deliver_service(update, service)
        else:
            await update.message.reply_text(
                f"موجودی کافی نیست! قیمت سرویس: {price:,} تومان\n"
                "لطفا از بخش کیف پول اقدام به شارژ کنید."
            )
    return MAIN_MENU

async def deliver_service(update: Update, service: str):
    with open(f'{service}.json', encoding='utf-8') as f:
        data = json.load(f)
    result = random.choice(list(data.values()))
    
    await update.message.reply_text(
        f"🔮 نتیجه {service}:\n\n{result}\n\n"
        "برای استفاده مجدد /start را بزنید"
    )

async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("➕ شارژ کیف پول")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    await update.message.reply_text(
        "مدیریت کیف پول:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return PAYMENT_METHOD

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ شارژ کیف پول":
        keyboard = [
            [KeyboardButton("💳 درگاه پرداخت"), KeyboardButton("📲 کارت به کارت")],
            [KeyboardButton("🔙 بازگشت")]
        ]
        await update.message.reply_text(
            "روش شارژ را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return CHARGE_AMOUNT
    elif text == "🔙 بازگشت به منوی اصلی":
        return await start(update, context)
    return MAIN_MENU

async def process_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # بررسی دکمه بازگشت
    if text == "🔙 بازگشت":
        return await wallet_menu(update, context)
    
    try:
        # تبدیل متن به عدد
        amount = int(text)
        
        # بررسی حداقل مبلغ
        if amount < 10000:
            await update.message.reply_text("حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است.")
            return CHARGE_AMOUNT
        
        # ایجاد کد پیگیری
        ref_id = f"zibal_{random.randint(10000, 99999)}"
        
        # افزایش موجودی کاربر
        update_balance(update.effective_user.id, amount)
        
        # ثبت تراکنش
        with sqlite3.connect("bot.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transactions 
                (user_id, amount, type, status, ref_id)
                VALUES (?, ?, 'charge', 'completed', ?)
            """, (update.effective_user.id, amount, ref_id))
            conn.commit()
        
        # ارسال پیام موفقیت
        await update.message.reply_text(
            f"✅ موجودی شما با موفقیت {amount:,} تومان شارژ شد!\n"
            f"کد پیگیری: {ref_id}\n\n"
            f"💰 موجودی جدید: {get_user(update.effective_user.id)[1]:,} تومان"
        )
        return await start(update, context)
        
    except ValueError:
        await update.message.reply_text(
            "⚠️ لطفاً فقط عدد وارد کنید!\n"
            "مثال: 50000 یا 100000"
        )
        return CHARGE_AMOUNT

async def subscription_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱ ماهه - ۳۰,۰۰۰ تومان")],
        [KeyboardButton("۳ ماهه - ۸۰,۰۰۰ تومان")],
        [KeyboardButton("۶ ماهه - ۱۵۰,۰۰۰ تومان")],
        [KeyboardButton("۱ ساله - ۲۵۰,۰۰۰ تومان")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    await update.message.reply_text(
        "پلن اشتراک مورد نظر را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SUBSCRIPTION_MENU

async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 بازگشت به منوی اصلی":
        return await start(update, context)
    
    plan_map = {
        "۱ ماهه - ۳۰,۰۰۰ تومان": ("monthly", 30000),
        "۳ ماهه - ۸۰,۰۰۰ تومان": ("3months", 80000),
        "۶ ماهه - ۱۵۰,۰۰۰ تومان": ("6months", 150000),
        "۱ ساله - ۲۵۰,۰۰۰ تومان": ("yearly", 250000)
    }
    
    if text in plan_map:
        plan, price = plan_map[text]
        user_id = update.effective_user.id
        user = get_user(user_id)
        
        if user and user[1] >= price:
            expiry_date = (datetime.now() + timedelta(days=SUBSCRIPTIONS[plan]["days"])).strftime("%Y-%m-%d")
            
            with sqlite3.connect("bot.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users 
                    SET balance = balance - ?, subscription_expiry = ?
                    WHERE user_id = ?
                """, (price, expiry_date, user_id))
                
                cursor.execute("""
                    INSERT INTO transactions 
                    (user_id, amount, type, status)
                    VALUES (?, ?, 'subscription', 'completed')
                """, (user_id, price))
                conn.commit()
            
            await update.message.reply_text(
                f"✅ اشتراک {plan} با موفقیت فعال شد!\n"
                f"تاریخ انقضا: {expiry_date}"
            )
        else:
            await update.message.reply_text(
                "موجودی کیف پول شما برای این اشتراک کافی نیست!"
            )
    return await start(update, context)

async def confirm_card_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text(
            "رسید پرداخت دریافت شد و در حال بررسی است.\n"
            "پس از تایید، موجودی به کیف پول شما اضافه خواهد شد."
        )
    return await start(update, context)

def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^(📿 استخاره|📜 دعای گشایش|📖 فال حافظ)$"), handle_service),
                MessageHandler(filters.Regex("^💰 کیف پول$"), wallet_menu),
                MessageHandler(filters.Regex("^🔔 اشتراک$"), subscription_menu),
                MessageHandler(filters.Regex("^📋 تاریخچه پرداخت‌ها$"), lambda u,c: start(u,c)),
                MessageHandler(filters.Regex("^🔙 بازگشت"), start)
            ],
            PAYMENT_METHOD: [
                MessageHandler(filters.Regex("^💳 درگاه پرداخت$"), lambda u,c: process_charge(u,c)),
                MessageHandler(filters.Regex("^📲 کارت به کارت$"), lambda u,c: confirm_card_payment(u,c)),
                MessageHandler(filters.Regex("^🔙 بازگشت"), start)
            ],
            CHARGE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_charge),
                MessageHandler(filters.Regex("^🔙 بازگشت"), wallet_menu)
            ],
            SUBSCRIPTION_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subscription),
                MessageHandler(filters.Regex("^🔙 بازگشت"), start)
            ],
            CONFIRM_PAYMENT: [
                MessageHandler(filters.PHOTO, confirm_card_payment),
                MessageHandler(filters.Regex("^🔙 بازگشت"), start)
            ],
        },
        fallbacks=[CommandHandler('cancel', start)]
    )
    
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
