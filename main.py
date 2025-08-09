import os
import json
import sqlite3
import random
import logging
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
    CallbackQueryHandler,
    JobQueue
)

# --- تنظیمات پایه ---
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
CARD_NUMBER = os.environ.get("CARD_NUMBER", "6037-XXXX-XXXX-XXXX")
CARD_OWNER = os.environ.get("CARD_OWNER", "نام صاحب کارت")

# --- تنظیمات لاگ‌گیری ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

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
 TOPIC_INPUT, CHARGE_AMOUNT, 
 SUBSCRIPTION_MENU, CONFIRM_PAYMENT,
 PAYMENT_HISTORY, SERVICE_HISTORY) = range(8)

# --- مدیریت پایگاه داده ---
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect("bot.db", check_same_thread=False)
        self.init_db()
    
    def init_db(self):
        cursor = self.conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                subscription_expiry TEXT,
                register_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                status TEXT,
                date TEXT DEFAULT CURRENT_TIMESTAMP,
                ref_id TEXT UNIQUE,
                admin_approved BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Create service_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_type TEXT,
                topic TEXT,
                result TEXT,
                date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Create payment_requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_requests (
                ref_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                photo_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                admin_message_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        self.conn.commit()
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    
    def get_user_balance(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def update_balance(self, user_id, amount, transaction_type="charge", approved=False):
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
            
            if amount != 0:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            
            ref_id = f"{transaction_type}_{user_id}_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
            cursor.execute("""
                INSERT INTO transactions 
                (user_id, amount, type, status, ref_id, admin_approved)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, amount, transaction_type, 'completed' if approved else 'pending', ref_id, approved))
            
            self.conn.commit()
            return True, ref_id
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی موجودی: {e}")
            return False, None
    
    def save_service_history(self, user_id, service_type, topic, result):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO service_history 
                (user_id, service_type, topic, result)
                VALUES (?, ?, ?, ?)
            """, (user_id, service_type, topic, result))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطا در ذخیره تاریخچه خدمات: {e}")
            return False
    
    def get_user_service_history(self, user_id, service_type=None, limit=10, offset=0):
        cursor = self.conn.cursor()
        if service_type:
            cursor.execute("""
                SELECT topic, result, date 
                FROM service_history 
                WHERE user_id = ? AND service_type = ?
                ORDER BY date DESC
                LIMIT ? OFFSET ?
            """, (user_id, service_type, limit, offset))
        else:
            cursor.execute("""
                SELECT service_type, topic, result, date 
                FROM service_history 
                WHERE user_id = ?
                ORDER BY date DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
        return cursor.fetchall()
    
    def get_transaction_history(self, user_id, limit=10, offset=0):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT type, amount, status, date 
            FROM transactions 
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        return cursor.fetchall()
    
    def update_subscription(self, user_id, plan_type):
        try:
            days = SUBSCRIPTIONS[plan_type]["days"]
            price = SUBSCRIPTIONS[plan_type]["price"]
            expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            
            cursor = self.conn.cursor()
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
            
            self.conn.commit()
            return True, expiry_date
        except Exception as e:
            logger.error(f"خطا در بروزرسانی اشتراک: {e}")
            return False, None
    
    def save_payment_request(self, ref_id, user_id, amount, photo_id, expires_at, admin_message_id=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO payment_requests 
                (ref_id, user_id, amount, photo_id, expires_at, admin_message_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ref_id, user_id, amount, photo_id, expires_at, admin_message_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving payment request: {e}")
            return False
    
    def get_payment_request(self, ref_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM payment_requests WHERE ref_id = ?", (ref_id,))
        return cursor.fetchone()
    
    def update_payment_status(self, ref_id, status):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE payment_requests 
                SET status = ? 
                WHERE ref_id = ?
            """, (status, ref_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
            return False
    
    def update_admin_message_id(self, ref_id, message_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE payment_requests 
                SET admin_message_id = ? 
                WHERE ref_id = ?
            """, (message_id, ref_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating admin message ID: {e}")
            return False
    
    def cleanup_expired_payments(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM payment_requests 
                WHERE expires_at < datetime('now')
                AND status = 'pending'
            """)
            self.conn.commit()
            return cursor.rowcount
        except Exception as e:
            logger.error(f"Error cleaning up expired payments: {e}")
            return 0

# --- مقداردهی اولیه ---
db = DatabaseManager()

# --- مدیریت پرداخت ---
class PaymentManager:
    @staticmethod
    def generate_payment_receipt(amount):
        return (
            f"برای شارژ {amount:,} تومان از طریق کارت به کارت:\n\n"
            f"شماره کارت: {CARD_NUMBER}\n"
            f"به نام: {CARD_OWNER}\n\n"
            "پس از واریز، تصویر رسید را ارسال کنید."
        )
    
    @staticmethod
    def validate_amount(amount_text):
        try:
            amount = int(amount_text.replace(',', '').replace('،', '').replace(' ', '').replace('تومان', ''))
            if amount <= 0:
                return False, 0
            return True, amount
        except ValueError:
            return False, 0

# --- دستورات ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    balance = user[1] if user else 0
    sub_expiry = user[2] if user and user[2] else "غیرفعال"

    keyboard = [
        [KeyboardButton("📿 استخاره"), KeyboardButton("📜 دعای گشایش")],
        [KeyboardButton("📖 فال حافظ")],
        [KeyboardButton("💰 شارژ کیف پول"), KeyboardButton("🔔 اشتراک")],
        [KeyboardButton("📋 تاریخچه پرداخت‌ها"), KeyboardButton("📜 تاریخچه خدمات")]
    ]
    
    await update.message.reply_text(
        "🌟 به ربات ما خوش آمدید! 🌟\n\n"
        "لطفاً از منوی زیر گزینه مورد نظر خود را انتخاب کنید:\n\n"
        f"💰 موجودی: {balance:,} تومان\n"
        f"🔔 وضعیت اشتراک: {sub_expiry}",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MAIN_MENU

async def handle_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_map = {
        "📿 استخاره": "estekhare",
        "📜 دعای گشایش": "gooshayesh",
        "📖 فال حافظ": "hafez"
    }
    
    if update.message.text in service_map:
        context.user_data['selected_service'] = service_map[update.message.text]
        await update.message.reply_text(
            "لطفاً موضوع مورد نظر خود را وارد کنید (حداکثر 100 کاراکتر):",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت")]], resize_keyboard=True)
        )
        return TOPIC_INPUT
    
    return MAIN_MENU

async def handle_topic_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 بازگشت":
        return await start(update, context)
    
    topic = update.message.text.strip()
    if len(topic) > 100:
        await update.message.reply_text("موضوع وارد شده بسیار طولانی است! لطفاً حداکثر 100 کاراکتر وارد کنید.")
        return TOPIC_INPUT
    
    service_type = context.user_data['selected_service']
    user_id = update.effective_user.id
    user_balance = db.get_user_balance(user_id)
    
    if user_balance < PRICES[service_type]:
        await update.message.reply_text(
            f"موجودی شما برای این سرویس کافی نیست!\n"
            f"قیمت سرویس: {PRICES[service_type]:,} تومان\n"
            f"موجودی فعلی: {user_balance:,} تومان\n\n"
            "لطفاً ابتدا کیف پول خود را شارژ کنید.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("💰 شارژ کیف پول"), KeyboardButton("🔙 بازگشت")]], resize_keyboard=True)
        )
        return MAIN_MENU
    
    try:
        with open(f'{service_type}.json', encoding='utf-8') as f:
            data = json.load(f)
        
        available_results = [v for k, v in data.items() if topic.lower() in k.lower()]
        
        if not available_results:
            await update.message.reply_text(
                "نتیجه‌ای برای این موضوع یافت نشد.\n"
                "لطفاً موضوع دیگری را امتحان کنید.",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت")]], resize_keyboard=True)
            )
            return TOPIC_INPUT
        
        selected_result = random.choice(available_results)
        
        # کسر هزینه و ذخیره تاریخچه
        success, _ = db.update_balance(user_id, -PRICES[service_type], f"service_{service_type}", True)
        if success:
            db.save_service_history(user_id, service_type, topic, selected_result)
            await update.message.reply_text(
                f"🔮 نتیجه {service_type} برای موضوع '{topic}':\n\n{selected_result}\n\n"
                f"💰 مبلغ {PRICES[service_type]:,} تومان از حساب شما کسر شد.\n"
                "برای استفاده مجدد /start را بزنید",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "خطا در پردازش درخواست! لطفاً مجدداً تلاش کنید.",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
            )
        
        return MAIN_MENU
    except Exception as e:
        logger.error(f"خطا در پردازش سرویس: {e}")
        await update.message.reply_text(
            "خطایی در سیستم رخ داده است! لطفاً بعداً تلاش کنید.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
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
        await update.message.reply_text("لطفاً مبلغ مورد نظر را به تومان وارد کنید (حداقل 10,000 تومان):")
        return CHARGE_AMOUNT
    
    is_valid, amount = PaymentManager.validate_amount(text)
    if not is_valid or amount < 10000:
        await update.message.reply_text("لطفاً یک مبلغ معتبر وارد کنید (حداقل 10,000 تومان)!")
        return CHARGE_AMOUNT
    
    context.user_data['charge_amount'] = amount
    
    await update.message.reply_text(
        PaymentManager.generate_payment_receipt(amount),
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت")]], resize_keyboard=True)
    )
    return CONFIRM_PAYMENT

async def confirm_card_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 بازگشت":
        return await wallet_charge(update, context)
    
    if update.message.photo:
        user_id = update.effective_user.id
        amount = context.user_data.get('charge_amount', 0)
        
        if amount <= 0:
            await update.message.reply_text("مبلغ پرداخت نامعتبر است!")
            return CHARGE_AMOUNT
        
        # ثبت تراکنش
        success, ref_id = db.update_balance(user_id, 0, "charge", False)
        
        if success:
            expires_at = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            
            # ذخیره در پایگاه داده
            db.save_payment_request(
                ref_id=ref_id,
                user_id=user_id,
                amount=amount,
                photo_id=update.message.photo[-1].file_id,
                expires_at=expires_at
            )
            
            # ارسال به ادمین برای تایید
            admin_text = (
                f"📌 درخواست شارژ جدید\n\n"
                f"👤 کاربر: {update.effective_user.full_name} (آیدی: {user_id})\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"🆔 کد پیگیری: {ref_id}\n"
                f"⏳ انقضا: {expires_at}"
            )
            
            keyboard = [
                [InlineKeyboardButton("✅ تایید پرداخت", callback_data=f"approve_{ref_id}")],
                [InlineKeyboardButton("❌ رد پرداخت", callback_data=f"reject_{ref_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                sent_msg = await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=update.message.photo[-1].file_id,
                    caption=admin_text,
                    reply_markup=reply_markup
                )
                # ذخیره message_id در دیتابیس
                db.update_admin_message_id(ref_id, sent_msg.message_id)
            except Exception as e:
                logger.error(f"خطا در ارسال پیام به ادمین: {e}")
                await update.message.reply_text(
                    "خطا در ارسال درخواست به ادمین! لطفاً بعداً تلاش کنید.",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
                )
                return MAIN_MENU
            
            await update.message.reply_text(
                "✅ رسید پرداخت دریافت شد و برای تایید به ادمین ارسال شد.\n\n"
                f"🆔 کد پیگیری: {ref_id}\n"
                f"⏳ اعتبار درخواست: تا {expires_at}",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "خطا در ثبت درخواست پرداخت! لطفاً مجدداً تلاش کنید.",
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
        try:
            await query.message.reply_text("شما دسترسی ادمین ندارید!")
        except Exception as e:
            logger.error(f"خطا در ارسال پیام به غیرادمین: {e}")
        return
    
    action, ref_id = query.data.split('_', 1)
    
    # دریافت اطلاعات از دیتابیس
    payment_request = db.get_payment_request(ref_id)
    if not payment_request:
        try:
            await query.edit_message_caption(
                caption="⚠️ اطلاعات پرداخت یافت نشد یا منقضی شده است.",
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"خطا در ویرایش پیام: {e}")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ اطلاعات پرداخت برای ref_id {ref_id} یافت نشد!"
            )
        return
    
    user_id = payment_request[1]
    amount = payment_request[2]
    admin_message_id = payment_request[7]
    
    try:
        if action == "approve":
            # افزایش موجودی کاربر
            success, _ = db.update_balance(user_id, amount, "charge", True)
            
            if success:
                # به روزرسانی وضعیت پرداخت
                db.update_payment_status(ref_id, "completed")
                
                # اطلاع به کاربر
                new_balance = db.get_user_balance(user_id)
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ پرداخت شما تایید شد!\n\n"
                             f"💰 مبلغ: {amount:,} تومان\n"
                             f"💳 موجودی جدید: {new_balance:,} تومان\n"
                             f"🆔 کد پیگیری: {ref_id}"
                    )
                except Exception as e:
                    logger.error(f"خطا در ارسال پیام به کاربر: {e}")
                
                # ویرایش پیام اصلی
                try:
                    await query.edit_message_caption(
                        caption=f"✅ تراکنش تایید شد\n\n"
                               f"👤 کاربر: {query.message.caption.split('👤')[1].split('💰')[0].strip()}\n"
                               f"💰 مبلغ: {amount:,} تومان\n"
                               f"🆔 کد پیگیری: {ref_id}\n"
                               f"🔄 وضعیت: تایید شده",
                        reply_markup=None
                    )
                except Exception as e:
                    logger.error(f"خطا در ویرایش پیام: {e}")
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"✅ تراکنش {ref_id} تایید شد.\n💰 مبلغ: {amount:,} تومان"
                    )
        
        elif action == "reject":
            # رد تراکنش
            db.update_payment_status(ref_id, "rejected")
            
            # اطلاع به کاربر
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ درخواست شارژ شما رد شد.\n\n"
                         f"🆔 کد پیگیری: {ref_id}\n"
                         f"💰 مبلغ: {amount:,} تومان\n\n"
                         "لطفاً با پشتیبانی تماس بگیرید."
                )
            except Exception as e:
                logger.error(f"خطا در ارسال پیام به کاربر: {e}")
            
            # ویرایش پیام اصلی
            try:
                await query.edit_message_caption(
                    caption=f"❌ تراکنش رد شد\n\n"
                           f"👤 کاربر: {query.message.caption.split('👤')[1].split('💰')[0].strip()}\n"
                           f"💰 مبلغ: {amount:,} تومان\n"
                           f"🆔 کد پیگیری: {ref_id}\n"
                           f"🔄 وضعیت: رد شده",
                    reply_markup=None
                )
            except Exception as e:
                logger.error(f"خطا در ویرایش پیام: {e}")
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"❌ تراکنش {ref_id} رد شد."
                )
    
    except Exception as e:
        logger.error(f"خطا در پردازش درخواست ادمین: {e}")
        try:
            await query.edit_message_caption(
                caption=f"❌ خطا در پردازش درخواست: {str(e)}",
                reply_markup=None
            )
        except:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❌ خطا در پردازش درخواست: {str(e)}"
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
        "۱ ماهه - ۳۰,۰۰۰ تومان": "monthly",
        "۳ ماهه - ۸۰,۰۰۰ تومان": "3months",
        "۶ ماهه - ۱۵۰,۰۰۰ تومان": "6months",
        "۱ ساله - ۲۵۰,۰۰۰ تومان": "yearly"
    }
    
    if text in plan_map:
        plan = plan_map[text]
        user_id = update.effective_user.id
        user_balance = db.get_user_balance(user_id)
        price = SUBSCRIPTIONS[plan]["price"]
        
        if user_balance >= price:
            keyboard = [
                [KeyboardButton(f"✅ بله، اشتراک {plan} را فعال کن")],
                [KeyboardButton("❌ خیر، انصراف")]
            ]
            context.user_data['selected_plan'] = plan
            await update.message.reply_text(
                f"آیا مایلید اشتراک {plan} به مبلغ {price:,} تومان از حساب شما کسر شود؟\n\n"
                f"💰 موجودی فعلی: {user_balance:,} تومان\n"
                f"💰 مبلغ اشتراک: {price:,} تومان\n"
                f"💰 موجودی پس از کسر: {user_balance - price:,} تومان",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return SUBSCRIPTION_MENU
        else:
            await update.message.reply_text(
                "موجودی کیف پول شما برای این اشتراک کافی نیست!\n"
                "لطفاً ابتدا کیف پول خود را شارژ کنید.",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("💰 شارژ کیف پول"), KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
            )
            return MAIN_MENU
    elif text.startswith("✅ بله"):
        plan = context.user_data.get('selected_plan')
        if not plan:
            return await start(update, context)
        
        user_id = update.effective_user.id
        success, expiry_date = db.update_subscription(user_id, plan)
        
        if success:
            await update.message.reply_text(
                f"✅ اشتراک {plan} با موفقیت فعال شد!\n"
                f"تاریخ انقضا: {expiry_date}\n\n"
                "برای بازگشت به منوی اصلی /start را بزنید."
            )
        else:
            await update.message.reply_text(
                "خطا در فعال‌سازی اشتراک! لطفاً بعداً تلاش کنید.",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
            )
        return MAIN_MENU
    elif text.startswith("❌ خیر"):
        return await start(update, context)
    
    return MAIN_MENU

async def show_payment_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    transactions = db.get_transaction_history(user_id)
    
    if not transactions:
        await update.message.reply_text(
            "تاریخچه پرداخت‌های شما خالی است.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
        )
        return MAIN_MENU
    
    history_text = "📋 تاریخچه پرداخت‌های شما:\n\n"
    for i, (t_type, amount, status, date) in enumerate(transactions, 1):
        history_text += (
            f"{i}. نوع: {t_type}\n"
            f"💰 مبلغ: {amount:,} تومان\n"
            f"🔄 وضعیت: {status}\n"
            f"📅 تاریخ: {date}\n\n"
        )
    
    if len(transactions) == 10:
        history_text += "برای مشاهده تراکنش‌های بیشتر، بعداً مجدداً تلاش کنید."
    
    await update.message.reply_text(
        history_text,
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
    )
    return MAIN_MENU

async def show_service_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = db.get_user_service_history(user_id)
    
    if not history:
        await update.message.reply_text(
            "تاریخچه خدمات شما خالی است.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
        )
        return MAIN_MENU
    
    history_text = "📜 تاریخچه خدمات شما:\n\n"
    for i, (s_type, topic, result, date) in enumerate(history, 1):
        history_text += (
            f"{i}. نوع: {s_type}\n"
            f"📌 موضوع: {topic}\n"
            f"📅 تاریخ: {date}\n\n"
        )
    
    if len(history) == 10:
        history_text += "برای مشاهده سرویس‌های بیشتر، بعداً مجدداً تلاش کنید."
    
    await update.message.reply_text(
        history_text,
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)
    )
    return MAIN_MENU

async def cleanup_expired_payments(context: ContextTypes.DEFAULT_TYPE):
    count = db.cleanup_expired_payments()
    if count > 0:
        logger.info(f"تمیزکاری پرداخت‌های منقضی شده: {count} مورد حذف شد")

# --- اجرای ربات ---
def main():
    app = Application.builder().token(TOKEN).build()
    
    # تنظیم کار دوره‌ای برای پاکسازی پرداخت‌های منقضی
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(
            cleanup_expired_payments,
            interval=timedelta(hours=6),
            first=10
        )
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^(📿 استخاره|📜 دعای گشایش|📖 فال حافظ)$"), handle_service_selection),
                MessageHandler(filters.Regex("^💰 شارژ کیف پول$"), wallet_charge),
                MessageHandler(filters.Regex("^🔔 اشتراک$"), subscription_menu),
                MessageHandler(filters.Regex("^📋 تاریخچه پرداخت‌ها$"), show_payment_history),
                MessageHandler(filters.Regex("^📜 تاریخچه خدمات$"), show_service_history),
                MessageHandler(filters.Regex("^🔙 بازگشت"), start)
            ],
            TOPIC_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic_input),
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
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^(approve|reject)_"))
    
    logger.info("ربات در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    main()
