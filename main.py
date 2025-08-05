import os
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

# متغیر محیطی برای توکن
BOT_TOKEN = os.getenv("bot-token")

# لود داده‌ها از فایل‌ها
with open('estekhare.json', encoding='utf-8') as f:
    estekhare_data = json.load(f)

with open('gooshayesh.json', encoding='utf-8') as f:
    gooshayesh_data = json.load(f)

with open('hafez.json', encoding='utf-8') as f:
    hafez_data = json.load(f)

# تعریف وضعیت‌ها
MENU, ESTEKHARE_TOPIC, gooshayesh_TOPIC, FAL_HAFEZ_TOPIC = range(4)

# شروع ربات و نمایش منوی اصلی
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

# هندلر منوی اصلی
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📿 استخاره":
        await update.message.reply_text("موضوع استخاره را وارد کن:")
        return ESTEKHARE_TOPIC
    elif text == "📜 دعای گشایش":
        await update.message.reply_text("موضوع دعا را وارد کن:")
        return gooshayesh_TOPIC
    elif text == "📖 فال حافظ":
        await update.message.reply_text("موضوع موردنظر برای فال حافظ را وارد کن:")
        return FAL_HAFEZ_TOPIC
    else:
        await update.message.reply_text("یکی از گزینه‌های منو را انتخاب کن.")
        return MENU

# استخاره
async def estekhare_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    result = estekhare_data.get(topic, "موضوعی با این عنوان پیدا نشد.")
    await update.message.reply_text(result)
    return await start(update, context)

# دعا
async def gooshayesh_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    result = gooshayesh_data.get(topic, "موضوعی با این عنوان پیدا نشد.")
    await update.message.reply_text(result)
    return await start(update, context)

# فال حافظ
async def hafez_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    result = hafez_data.get(topic, "موضوعی با این عنوان پیدا نشد.")
    await update.message.reply_text(result)
    return await start(update, context)

# کنسل کردن گفتگو
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("گفتگو لغو شد.")
    return ConversationHandler.END

# اجرای اپلیکیشن
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)],
            ESTEKHARE_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, estekhare_handler)],
            gooshayesh_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, gooshayesh_handler)],
            FAL_HAFEZ_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, hafez_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.run_polling()
