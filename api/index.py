from flask import Flask, request
import telebot
from telebot import types
import requests
import os
import pymongo
import google.generativeai as genai

# ---------------- CONFIG ----------------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = "4322c10a72e6944a7"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")

BANNER_URL = "https://i.ibb.co/FbFMQpf1/thumb-400-anime-boy-5725.webp"

OWNER_ID = 6356015122
SUPPORT_BOT = "https://t.me/Sudeep_support_bot"
BOT_USERNAME = "Animesarchingbot"

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ---------------- GEMINI ----------------
model = None
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
    except:
        model = None

# ---------------- MONGO ----------------
users_collection = None
if MONGO_URI:
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client["MySearchBotDB"]
        users_collection = db["users"]
    except:
        pass

def add_user(message):
    if not users_collection:
        return
    try:
        users_collection.update_one(
            {"_id": message.chat.id},
            {"$set": {
                "first_name": message.chat.first_name,
                "username": message.chat.username,
                "type": message.chat.type
            }},
            upsert=True
        )
    except:
        pass

# ---------------- AI CHECK ----------------
def is_search_query(text):
    ignore = ["hi", "hello", "hey", "gm", "gn", "help", "start"]
    if text.lower() in ignore:
        return False

    if not model:
        return True

    try:
        r = model.generate_content(
            f"Is '{text}' a Movie or Anime name? Reply YES or NO"
        )
        return "YES" in r.text.upper()
    except:
        return True

def build_query(text):
    return f"{text} Hindi Dubbed Telegram Channel site:t.me"

# ---------------- GOOGLE ----------------
def google_search(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": SEARCH_ENGINE_ID,
            "q": query,
            "num": 5
        }
        data = requests.get(url, params=params).json()
        if "items" not in data:
            return []
        return [{
            "title": i["title"][:30] + "...",
            "link": i["link"].split("?")[0]
        } for i in data["items"]]
    except:
        return []

def get_image(text):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": SEARCH_ENGINE_ID,
            "q": text + " anime wallpaper",
            "searchType": "image",
            "num": 1
        }
        d = requests.get(url, params=params).json()
        if "items" in d:
            return d["items"][0]["link"]
    except:
        pass
    return None

# ---------------- ROUTES ----------------
@app.route("/", methods=["GET"])
def home():
    return "Bot Alive", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(
            request.get_data().decode("utf-8")
        )
        bot.process_new_updates([update])
        return "OK", 200
    return "INVALID", 403

# ---------------- START ----------------
@bot.message_handler(commands=["start", "help"])
def start(message):
    add_user(message)

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎬 Movies", callback_data="movie"),
        types.InlineKeyboardButton("⛩ Anime", callback_data="anime")
    )
    kb.add(
        types.InlineKeyboardButton("➕ Add to Group",
        url=f"https://t.me/{BOT_USERNAME}?startgroup=true")
    )
    kb.add(
        types.InlineKeyboardButton("👤 Owner", url=f"tg://user?id={OWNER_ID}"),
        types.InlineKeyboardButton("💬 Support", url=SUPPORT_BOT)
    )

    caption = (
        "<blockquote><b>🤖 Anime & Movie Search Bot</b>\n\n"
        "• Search Anime\n"
        "• Search Movies\n"
        "• Works in Groups</blockquote>"
    )

    bot.send_photo(
        message.chat.id,
        BANNER_URL,
        caption=caption,
        parse_mode="HTML",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    if c.data == "movie":
        bot.answer_callback_query(c.id, "Movie name likho (Stree 2)")
    elif c.data == "anime":
        bot.answer_callback_query(c.id, "Anime name likho (Naruto)")
    elif c.data == "close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except:
            pass

# ---------------- MESSAGE ----------------
@bot.message_handler(func=lambda m: True)
def msg(m):
    if not m.text or m.text.startswith("/"):
        return

    if m.chat.type in ["group", "supergroup"]:
        if len(m.text) > 50 or not is_search_query(m.text):
            return
        try:
            bot.delete_message(m.chat.id, m.message_id)
        except:
            pass

    query = build_query(m.text)
    results = google_search(query)
    image = get_image(m.text)

    kb = types.InlineKeyboardMarkup()
    for r in results:
        kb.add(types.InlineKeyboardButton("📂 " + r["title"], url=r["link"]))
    kb.add(types.InlineKeyboardButton("❌ Close", callback_data="close"))

    caption = f"<blockquote>🔎 <b>Result:</b> {m.text.title()}</blockquote>"

    if image:
        bot.send_photo(m.chat.id, image, caption=caption,
                       parse_mode="HTML", reply_markup=kb)
    else:
        bot.send_message(m.chat.id, caption,
                         parse_mode="HTML", reply_markup=kb)
