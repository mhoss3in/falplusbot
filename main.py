import telebot
from telebot import types
import json
import os

TOKEN = os.environ.get("BOT_TOKEN")  # با نام متغیر درست در Render
bot = telebot.TeleBot(TOKEN)

# بارگذاری فایل‌های json
with open("estekhare.json", "r", encoding="utf-8") as f:
    estekhare = json.load(f)

with open("gooshayesh.json", "r", encoding="utf-8") as f:
    gooshayesh = json.load(f)

with open("hafez.json", "r", encoding="utf-8") as f:
    hafez = json.load(f)

# منوی اصلی با دکمه‌های پنجره‌ای
def send_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("📿 استخاره")
    btn2 = types.KeyboardButton("🙏 دعای گشایش")
    btn3 = types.KeyboardButton("📖 فال حافظ")
    markup.add(btn1, btn2, btn3)
    bot.send_message(chat_id, "یکی از گزینه‌های زیر رو انتخاب کن:", reply_markup=markup)

# هر پیامی بیاد، منوی اصلی رو نشون می‌دیم
@bot.message_handler(func=lambda m: True)
def all_messages_handler(message):
    if message.text == "📿 استخاره":
        bot.send_message(message.chat.id, "موضوع استخاره‌ات رو بنویس:")
        # ادامه در مرحله بعد اضافه می‌شه
    elif message.text == "🙏 دعای گشایش":
        bot.send_message(message.chat.id, "موضوع دعای گشایش رو بنویس:")
        # ادامه در مرحله بعد اضافه می‌شه
    elif message.text == "📖 فال حافظ":
        bot.send_message(message.chat.id, "موضوع فال حافظ رو بنویس:")
        # ادامه در مرحله بعد اضافه می‌شه
    else:
        send_main_menu(message.chat.id)

bot.infinity_polling()
