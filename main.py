import json
import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os

TOKEN = os.environ.get("TOKEN")  # یا هر اسمی که خودت انتخاب کنی، فقط باید با Render هماهنگ باشه
bot = telebot.TeleBot(TOKEN)

# === مسیر فایل‌ها ===
SUBS_FILE = 'subscriptions.json'
WALLET_FILE = 'wallets.json'

# === توابع کمکی فایل‌ها ===
def load_subscriptions():
    try:
        with open(SUBS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {}

def save_subscriptions(data):
    with open(SUBS_FILE, 'w') as f:
        json.dump(data, f)

def load_wallets():
    try:
        with open(WALLET_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {}

def save_wallets(data):
    with open(WALLET_FILE, 'w') as f:
        json.dump(data, f)

# === بررسی اشتراک فعال ===
def check_subscription(user_id):
    subs = load_subscriptions()
    if str(user_id) in subs:
        expiry = datetime.datetime.strptime(subs[str(user_id)], '%Y-%m-%d')
        return datetime.datetime.now() < expiry
    return False

# === شارژ کیف پول ===
async def charge_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallets = load_wallets()
    wallets[str(user_id)] = wallets.get(str(user_id), 0) + 1000  # شارژ فرضی 1000 تومان
    save_wallets(wallets)
    await update.message.reply_text("✅ کیف پول با موفقیت ۱۰۰۰ تومان شارژ شد.")

# === خرید اشتراک ===
async def buy_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallets = load_wallets()
    balance = wallets.get(str(user_id), 0)
    
    price = 1000  # قیمت اشتراک یک روزه به‌صورت تستی

    if balance >= price:
        wallets[str(user_id)] = balance - price
        save_wallets(wallets)

        expiry_date = datetime.datetime.now() + datetime.timedelta(days=1)
        subs = load_subscriptions()
        subs[str(user_id)] = expiry_date.strftime('%Y-%m-%d')
        save_subscriptions(subs)

        await update.message.reply_text("🎉 اشتراک شما با موفقیت فعال شد تا فردا.")
    else:
        await update.message.reply_text("❌ موجودی کیف پول کافی نیست. لطفاً شارژ کنید.")

# === دستور /start و منو ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📿 استخاره", "🕊 دعای گشایش"],
        ["📜 فال حافظ"],
        ["💳 شارژ کیف پول", "🛒 خرید اشتراک"]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, resize_keyboard=True, one_time_keyboard=False
    )
    await update.message.reply_text(
        "سلام! به ربات فال‌پلاس خوش اومدی 🌟\nیکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=reply_markup
    )

# === دستور استخاره ===
async def estekhare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if check_subscription(user_id):
        await update.message.reply_text("📿 نتیجه استخاره شما: خوب است! اعتماد کن و اقدام کن.")
    else:
        await update.message.reply_text("❌ ابتدا اشتراک تهیه کنید یا کیف پول را شارژ نمایید.")

# === دعای گشایش ===
async def gooshayesh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if check_subscription(user_id):
        await update.message.reply_text("🕊 دعای گشایش:\nاللّهُمَّ افْتَحْ لِی أَبْوَابَ رَحْمَتِکَ...")
    else:
        await update.message.reply_text("❌ ابتدا اشتراک تهیه کنید یا کیف پول را شارژ نمایید.")

# === فال حافظ ===
async def fal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if check_subscription(user_id):
        await update.message.reply_text("📜 فال حافظ شما:\nدل می‌رود ز دستم صاحب دلان خدا را...")
    else:
        await update.message.reply_text("❌ ابتدا اشتراک تهیه کنید یا کیف پول را شارژ نمایید.")

# === مدیریت متن دکمه‌ها ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📿 استخاره":
        await estekhare(update, context)
    elif text == "🕊 دعای گشایش":
        await gooshayesh(update, context)
    elif text == "📜 فال حافظ":
        await fal(update, context)
    elif text == "💳 شارژ کیف پول":
        await charge_wallet(update, context)
    elif text == "🛒 خرید اشتراک":
        await buy_subscription(update, context)
    else:
        await update.message.reply_text("⛔ دستور نامعتبر است. لطفاً از منو استفاده کنید.")

# === راه‌اندازی ربات ===
def main():
    app = Application.builder().token("TOKEN").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("✅ ربات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
