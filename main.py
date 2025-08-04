import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# بارگذاری فایل‌های JSON
with open("estekhare.json", "r", encoding="utf-8") as f:
    estekhare = json.load(f)

with open("gooshayesh.json", "r", encoding="utf-8") as f:
    gooshayesh = json.load(f)

with open("hafez.json", "r", encoding="utf-8") as f:
    hafez = json.load(f)

# هندلر فرمان /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! خوش اومدی 🌟\n/estekhare\n/gooshayesh\n/fal")

# هندلر فرمان /estekhare
async def estekhare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = "ازدواج"
    reply = estekhare.get(topic, "چیزی پیدا نشد.")
    await update.message.reply_text(reply)

# هندلر فرمان /gooshayesh
async def gooshayesh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = "رزق"
    reply = gooshayesh.get(topic, "چیزی پیدا نشد.")
    await update.message.reply_text(reply)

# هندلر فرمان /fal
async def fal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = "عشق"
    reply = hafez.get(topic, "چیزی پیدا نشد.")
    await update.message.reply_text(reply)

# تابع اصلی اجرا
def main():
    TOKEN = os.environ.get("TOKEN")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estekhare", estekhare_command))
    app.add_handler(CommandHandler("gooshayesh", gooshayesh_command))
    app.add_handler(CommandHandler("fal", fal_command))

    print("ربات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
