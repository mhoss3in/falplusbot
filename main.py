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
    """ایجاد و تنظیم ساختار دیتابیس"""
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
        conn.commit()

def get_user(user_id):
    """دریافت اطلاعات کاربر از دیتابیس"""
    with sqlite3.connect("bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def update_balance(user_id, amount):
    """به‌روزرسانی موجودی کاربر با مدیریت تراکنش"""
    try:
        with sqlite3.connect("bot.db") as conn:
            cursor = conn.cursor()
            # ایجاد کاربر اگر وجود نداشته باشد
            cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
            # به‌روزرسانی موجودی
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            # ثبت تراکنش
            ref_id = f"charge_{random.randint(10000, 99999)}"
            cursor.execute("""
                INSERT INTO transactions 
                (user_id, amount, type, status, ref_id)
                VALUES (?, ?, 'charge', 'completed', ?)
            """, (user_id, amount, ref_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"خطا در به‌روزرسانی موجودی: {e}")
        return False

# --- توابع اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی ربات"""
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

async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی مدیریت کیف پول"""
    user = get_user(update.effective_user.id)
    balance = user[1] if user else 0
    
    keyboard = [
        [KeyboardButton("💳 شارژ با درگاه پرداخت")],
        [KeyboardButton("📲 شارژ با کارت به کارت")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    
    await update.message.reply_text(
        f"💼 کیف پول شما\n\n"
        f"💰 موجودی فعلی: {balance:,} تومان\n\n"
        "لطفاً روش شارژ را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return PAYMENT_METHOD

async def handle_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش انتخاب روش پرداخت"""
    text = update.message.text
    
    if text == "💳 شارژ با درگاه پرداخت":
        await update.message.reply_text(
            "لطفاً مبلغ مورد نظر برای شارژ را وارد کنید (تومان):\n\n"
            "مثال: 50000 یا 50,000"
        )
        return CHARGE_AMOUNT
    elif text == "📲 شارژ با کارت به کارت":
        await update.message.reply_text(
            "برای شارژ کیف پول از طریق کارت به کارت:\n\n"
            "شماره کارت: 6037-XXXX-XXXX-XXXX\n"
            "به نام: [نام صاحب کارت]\n\n"
            "پس از واریز، تصویر رسید را ارسال کنید."
        )
        return CONFIRM_PAYMENT
    elif text == "🔙 بازگشت به منوی اصلی":
        return await start(update, context)
    
    return PAYMENT_METHOD

async def process_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش شارژ کیف پول"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text == "🔙 بازگشت":
        return await wallet_menu(update, context)
    
    try:
        # پردازش مبلغ ورودی
        amount = int(text.replace(',', '').replace('،', '').replace(' ', ''))
        
        if amount < 10000:
            await update.message.reply_text("حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است.")
            return CHARGE_AMOUNT
        
        # انجام عملیات شارژ
        if update_balance(user_id, amount):
            user = get_user(user_id)
            await update.message.reply_text(
                f"✅ موجودی شما با موفقیت {amount:,} تومان شارژ شد!\n"
                f"💰 موجودی جدید: {user[1]:,} تومان\n\n"
                "برای بازگشت به منوی اصلی /start را بزنید."
            )
            return MAIN_MENU
        else:
            await update.message.reply_text(
                "⚠️ خطا در پردازش درخواست شارژ!\n"
                "لطفاً مجدداً تلاش کنید."
            )
            return CHARGE_AMOUNT
            
    except ValueError:
        await update.message.reply_text(
            "⚠️ لطفاً فقط عدد وارد کنید!\n"
            "مثال:\n50000\nیا\n50,000"
        )
        return CHARGE_AMOUNT

async def confirm_card_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید پرداخت کارت به کارت"""
    if update.message.photo:
        # در اینجا می‌توانید سیستم تایید دستی/خودکار را پیاده‌سازی کنید
        amount = 10000  # مقدار پیش‌فرض یا از کاربر دریافت شود
        user_id = update.effective_user.id
        
        if update_balance(user_id, amount):
            await update.message.reply_text(
                f"✅ پرداخت شما تأیید و مبلغ {amount:,} تومان به کیف پول شما اضافه شد!\n"
                "برای بازگشت به منوی اصلی /start را بزنید."
            )
        else:
            await update.message.reply_text(
                "⚠️ خطا در ثبت پرداخت!\n"
                "لطفاً با پشتیبانی تماس بگیرید."
            )
    else:
        await update.message.reply_text(
            "لطفاً تصویر رسید پرداخت را ارسال کنید."
        )
        return CONFIRM_PAYMENT
    
    return MAIN_MENU

# --- سایر توابع (سرویس‌ها و اشتراک) ---
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
            await deliver_service(update, service)
        elif user and user[1] >= price:
            update_balance(user_id, -price)
            await deliver_service(update, service)
        else:
            await update.message.reply_text(
                f"موجودی کافی نیست! قیمت سرویس: {price:,} تومان\n"
                "لطفاً از بخش کیف پول اقدام به شارژ کنید."
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

async def subscription_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اشتراک"""
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
    """پردازش انتخاب اشتراک"""
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
                f"تاریخ انقضا: {expiry_date}\n\n"
                "برای بازگشت به منوی اصلی /start را بزنید."
            )
        else:
            await update.message.reply_text(
                "موجودی کیف پول شما برای این اشتراک کافی نیست!\n"
                "لطفاً ابتدا کیف پول خود را شارژ کنید."
            )
    return MAIN_MENU

# --- تنظیم و اجرای ربات ---
def main():
    """تابع اصلی اجرای ربات"""
    # مقداردهی اولیه دیتابیس
    init_db()
    
    # ساخت برنامه ربات
    app = Application.builder().token(TOKEN).build()
    
    # مدیریت مکالمات
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_method),
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
