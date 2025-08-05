import os
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

# گرفتن توکن از متغیر محیطی
TOKEN = os.environ.get("BOT_TOKEN")

# اگر توکن موجود نبود، خطا بده
if not TOKEN:
    raise ValueError("توکن بات تلگرام پیدا نشد! لطفاً متغیر محیطی BOT_TOKEN را در Render تنظیم کن.")

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات شما با موفقیت فعال است.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
