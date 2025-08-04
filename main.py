
import telebot
import json
import os

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# بارگذاری فایل‌های json
with open("estekhare.json", "r", encoding="utf-8") as f:
    estekhare = json.load(f)

with open("gooshayesh.json", "r", encoding="utf-8") as f:
    gooshayesh = json.load(f)

with open("hafez.json", "r", encoding="utf-8") as f:
    hafez = json.load(f)

@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "سلام! خوش اومدی 🌟\n/estekhare\n/gooshayesh\n/fal")

@bot.message_handler(commands=["estekhare"])
def handle_estekhare(message):
    topic = "ازدواج"
    reply = estekhare.get(topic, "چیزی پیدا نشد.")
    bot.send_message(message.chat.id, reply)

@bot.message_handler(commands=["gooshayesh"])
def handle_gooshayesh(message):
    topic = "رزق"
    reply = gooshayesh.get(topic, "چیزی پیدا نشد.")
    bot.send_message(message.chat.id, reply)

@bot.message_handler(commands=["fal"])
def handle_fal(message):
    topic = "عشق"
    reply = hafez.get(topic, "چیزی پیدا نشد.")
    bot.send_message(message.chat.id, reply)

bot.infinity_polling()
