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

# تنظیمات پایه
TOKEN = os.environ.get("BOT_TOKEN")
MERCHANT_KEY = "zibal_merchant_key"  # جایگزین با کلید واقعی
ADMIN_CARD = "6037-XXXX-XXXX-XXXX"  # شماره کارت برای پرداخت کارت به کارت

if not TOKEN:
    raise ValueError("توکن ربات تنظیم نشده است!")

# تعرفه خدمات
PRICES = {
    "estekhare": 5000,
    "gooshayesh": 7000,
    "hafez": 10000
}

# پلن‌های اشتراک
SUBSCRIPTIONS = {
    "monthly": {"price": 30000, "days": 30},
    "yearly": {"price": 250000, "days": 365}
}

# وضعیت‌های مکالمه
(MAIN_MENU, SERVICE_SELECTION, 
 PAYMENT_METHOD, CHARGE_AMOUNT,
 SUBSCRIPTION_MENU, CONFIRM_PAYMENT) = range(6)

# --- توابع دیتابیس ---
def init_db():
    """ایجاد ساختار دیتابیس"""
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
    """دریافت اطلاعات کاربر"""
    with sqlite3.connect("bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def update_balance(user_id, amount):
    """به‌روزرسانی موجودی کاربر"""
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
    """منوی اصلی"""
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
    """پردازش درخواست خدمات"""
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
            # کاربر اشتراک فعال دارد
            await deliver_service(update, service)
        elif user and user[1] >= price:
            # پرداخت از کیف پول
            update_balance(user_id, -price)
            await deliver_service(update, service)
        else:
            # موجودی کافی نیست
            await update.message.reply_text(
                f"موجودی کافی نیست! قیمت سرویس: {price:,} تومان\n"
                "لطفا از بخش کیف پول اقدام به شارژ کنید."
            )
    return MAIN_MENU

async def deliver_service(update: Update, service: str):
    """ارسال نتیجه سرویس"""
    with open(f'{service}.json', encoding='utf-8') as f:
        data = json.load(f)
    result = random.choice(list(data.values()))
    
    await update.message.reply_text(
        f"🔮 نتیجه {service}:\n\n{result}\n\n"
        "برای استفاده مجدد /start را بزنید"
    )

# --- سیستم پرداخت و اشتراک ---
async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی کیف پول"""
    keyboard = [
        [KeyboardButton("💳 درگاه پرداخت"), KeyboardButton("📲 کارت به کارت")],
        [KeyboardButton("🔙 بازگشت")]
    ]
    await update.message.reply_text(
        "روش شارژ را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return PAYMENT_METHOD

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پرداخت"""
    if update.message.text == "💳 درگاه پرداخت":
        await update.message.reply_text("مبلغ مورد نظر را وارد کنید (تومان):")
        return CHARGE_AMOUNT
    elif update.message.text == "📲 کارت به کارت":
        await update.message.reply_text(
            f"💳 برای شارژ حساب:\n\n"
            f"شماره کارت: {ADMIN_CARD}\n"
            f"به نام: [نام شما]\n\n"
            "پس از واریز، رسید را ارسال کنید."
        )
        return CONFIRM_PAYMENT
    return MAIN_MENU

async def process_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش درخواست شارژ"""
    try:
        amount = int(update.message.text)
        if amount < 10000:
            await update.message.reply_text("حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است.")
            return CHARGE_AMOUNT
        
        # شبیه‌سازی درگاه پرداخت
        ref_id = f"zibal_{random.randint(10000, 99999)}"
        update_balance(update.effective_user.id, amount)
        
        await update.message.reply_text(
            f"✅ موجودی شما با موفقیت {amount:,} تومان شارژ شد!\n"
            f"کد پیگیری: {ref_id}"
        )
        return MAIN_MENU
    except ValueError:
        await update.message.reply_text("لطفا فقط عدد وارد کنید!")
        return CHARGE_AMOUNT

# --- اجرای ربات ---
def main():
    # مقداردهی اولیه دیتابیس
    init_db()
    
    # تنظیمات ربات
    app = Application.builder().token(TOKEN).build()
    
    # مدیریت مکالمات
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^(📿 استخاره|📜 دعای گشایش|📖 فال حافظ)$"), handle_service),
                MessageHandler(filters.Regex("^💰 کیف پول$"), wallet_menu),
                MessageHandler(filters.Regex("^🔔 اشتراک$"), subscription_menu),
            ],
            PAYMENT_METHOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment),
            ],
            CHARGE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_charge),
            ],
            CONFIRM_PAYMENT: [
                MessageHandler(filters.PHOTO, confirm_card_payment),
            ],
        },
        fallbacks=[CommandHandler('cancel', start)]
    )
    
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
