import os
import json
import sqlite3
import random
from datetime import datetime, timedelta
from telegram import (
    Update, 
    KeyboardButton, 
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
    CallbackQueryHandler
)

# --- تنظیمات پایه ---
TOKEN = os.environ.get("BOT_TOKEN")
# آیدی ادمین از متغیر محیطی دریافت می‌شود
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # مقدار پیش‌فرض 0 اگر متغیر تنظیم نشده باشد
if not TOKEN:
    raise ValueError("توکن ربات تنظیم نشده است!")
if ADMIN_ID == 0:
    raise ValueError("آیدی ادمین تنظیم نشده است!")

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
 CHARGE_AMOUNT, SUBSCRIPTION_MENU,
 CONFIRM_PAYMENT) = range(5)

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
                admin_approved BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        conn.commit()

def get_user(user_id):
    with sqlite3.connect("bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def update_balance(user_id, amount, transaction_type="charge", approved=False):
    try:
        with sqlite3.connect("bot.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            
            ref_id = f"{transaction_type}_{random.randint(10000, 99999)}"
            cursor.execute("""
                INSERT INTO transactions 
                (user_id, amount, type, status, ref_id, admin_approved)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, amount, transaction_type, 'completed' if approved else 'pending', ref_id, approved))
            
            conn.commit()
            return True, ref_id
    except Exception as e:
        print(f"خطا در به‌روزرسانی موجودی: {e}")
        return False, None

# --- توابع اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    balance = user[1] if user else 0
    sub_expiry = user[2] if user and user[2] else "غیرفعال"

    keyboard = [
        [KeyboardButton("📿 استخاره"), KeyboardButton("📜 دعای گشایش")],
        [KeyboardButton("📖 فال حافظ")],
        [KeyboardButton("💰 شارژ کیف پول"), KeyboardButton("🔔 اشتراک")],
        [KeyboardButton("📋 تاریخچه پرداخت‌ها")]
    ]
    
    # پیام خوش‌آمدگویی جدید
    await update.message.reply_text(
        "🌟 به ربات ما خوش آمدید! 🌟\n\n"
        "لطفاً از منوی زیر گزینه مورد نظر خود را انتخاب کنید:\n\n"
        f"💰 موجودی: {balance:,} تومان\n"
        f"🔔 وضعیت اشتراک: {sub_expiry}",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MAIN_MENU

async def wallet_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰,۰۰۰ تومان"), KeyboardButton("۵۰,۰۰۰ تومان")],
        [KeyboardButton("۱۰۰,۰۰۰ تومان"), KeyboardButton("مبلغ دلخواه")],
        [KeyboardButton("🔙 بازگشت")]
    ]
    await update.message.reply_text(
        "لطفاً مبلغ مورد نظر برای شارژ را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHARGE_AMOUNT

async def handle_charge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🔙 بازگشت":
        return await start(update, context)
    
    if text == "مبلغ دلخواه":
        await update.message.reply_text("لطفاً مبلغ مورد نظر را وارد کنید (تومان):")
        return CHARGE_AMOUNT
    
    try:
        amount = int(text.replace(',', '').replace('،', '').replace(' ', '').replace('تومان', ''))
        context.user_data['charge_amount'] = amount
        
        await update.message.reply_text(
            f"برای شارژ {amount:,} تومان از طریق کارت به کارت:\n\n"
            "شماره کارت: 6037-XXXX-XXXX-XXXX\n"
            "به نام: [نام صاحب کارت]\n\n"
            "پس از واریز، تصویر رسید را ارسال کنید.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت")]], resize_keyboard=True)
        )
        return CONFIRM_PAYMENT
    except ValueError:
        await update.message.reply_text("لطفاً یک مبلغ معتبر وارد کنید!")
        return CHARGE_AMOUNT

async def confirm_card_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 بازگشت":
        return await wallet_charge(update, context)
    
    if update.message.photo:
        user_id = update.effective_user.id
        amount = context.user_data.get('charge_amount', 10000)
        
        # ثبت تراکنش به صورت pending
        with sqlite3.connect("bot.db") as conn:
            cursor = conn.cursor()
            ref_id = f"card_{random.randint(10000, 99999)}"
            cursor.execute("""
                INSERT INTO transactions 
                (user_id, amount, type, status, ref_id, admin_approved)
                VALUES (?, ?, 'charge', 'pending', ?, 0)
            """, (user_id, amount, ref_id))
            conn.commit()
        
        # ارسال به ادمین برای تایید با دکمه‌های اینلاین
        admin_text = (
            f"📌 درخواست شارژ جدید\n\n"
            f"👤 کاربر: {update.effective_user.full_name} (آیدی: {user_id})\n"
            f"💰 مبلغ: {amount:,} تومان\n"
            f"🆔 کد پیگیری: {ref_id}"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ تایید پرداخت", callback_data=f"approve_{ref_id}")],
            [InlineKeyboardButton("❌ رد پرداخت", callback_data=f"reject_{ref_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=admin_text,
            reply_markup=reply_markup
        )
        
        await update.message.reply_text(
            "✅ رسید پرداخت دریافت شد و برای تایید به ادمین ارسال شد.\n"
            "پس از تایید ادمین، موجودی به کیف پول شما اضافه خواهد شد.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
        )
        return MAIN_MENU
    else:
        await update.message.reply_text("لطفاً تصویر رسید پرداخت را ارسال کنید.")
        return CONFIRM_PAYMENT

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.message.reply_text("شما دسترسی ادمین ندارید!")
        return
    
    action, ref_id = query.data.split('_', 1)
    
    with sqlite3.connect("bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount FROM transactions WHERE ref_id = ?", (ref_id,))
        transaction = cursor.fetchone()
        
        if not transaction:
            await query.edit_message_text("تراکنش یافت نشد!")
            return
            
        user_id, amount = transaction
        
        if action == "approve":
            # تایید تراکنش
            cursor.execute("""
                UPDATE transactions 
                SET status = 'completed', admin_approved = 1 
                WHERE ref_id = ?
            """, (ref_id,))
            
            # افزایش موجودی کاربر
            cursor.execute("""
                UPDATE users 
                SET balance = balance + ? 
                WHERE user_id = ?
            """, (amount, user_id))
            
            conn.commit()
            
            # اطلاع به کاربر
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ پرداخت شما تایید شد!\n\n💰 مبلغ {amount:,} تومان به کیف پول شما اضافه شد."
            )
            
            # ویرایش پیام اصلی
            await query.edit_message_caption(
                caption=f"✅ تراکنش {ref_id} تایید شد.",
                reply_markup=None
            )
            
        elif action == "reject":
            # رد تراکنش
            cursor.execute("""
                UPDATE transactions 
                SET status = 'rejected', admin_approved = 0 
                WHERE ref_id = ?
            """, (ref_id,))
            conn.commit()
            
            # اطلاع به کاربر
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ درخواست شارژ شما توسط ادمین رد شد.\n\nلطفاً با پشتیبانی تماس بگیرید."
            )
            
            # ویرایش پیام اصلی
            await query.edit_message_caption(
                caption=f"❌ تراکنش {ref_id} رد شد.",
                reply_markup=None
            )

# --- سایر توابع ---
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
            update_balance(user_id, -price, "payment", True)
            await deliver_service(update, service)
        else:
            await update.message.reply_text(
                f"موجودی کافی نیست! قیمت سرویس: {price:,} تومان\n"
                "لطفاً از بخش کیف پول اقدام به شارژ کنید."
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
                    (user_id, amount, type, status, admin_approved)
                    VALUES (?, ?, 'subscription', 'completed', 1)
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
                MessageHandler(filters.Regex("^💰 شارژ کیف پول$"), wallet_charge),
                MessageHandler(filters.Regex("^🔔 اشتراک$"), subscription_menu),
                MessageHandler(filters.Regex("^📋 تاریخچه پرداخت‌ها$"), lambda u,c: start(u,c)),
                MessageHandler(filters.Regex("^🔙 بازگشت"), start)
            ],
            CHARGE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_charge_amount),
                MessageHandler(filters.Regex("^🔙 بازگشت"), start)
            ],
            SUBSCRIPTION_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subscription),
                MessageHandler(filters.Regex("^🔙 بازگشت"), start)
            ],
            CONFIRM_PAYMENT: [
                MessageHandler(filters.PHOTO | filters.TEXT & filters.Regex("^🔙 بازگشت"), confirm_card_payment)
            ],
        },
        fallbacks=[CommandHandler('cancel', start)]
    )
    
    app.add_handler(conv_handler)
    
    # اضافه کردن هندلر برای دکمه‌های اینلاین
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^(approve|reject)_"))
    
    app.run_polling()

if __name__ == "__main__":
    main()
