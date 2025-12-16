from flask import Flask, request
import telebot
from telebot import types 
import google.generativeai as genai
import requests
import os
import pymongo

# --- CONFIG ---
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
SEARCH_ENGINE_ID = os.environ.get('SEARCH_ENGINE_ID')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
MONGO_URI = os.environ.get('MONGO_URI')

# --- IMAGE URL (Ye kaam kar raha hai) ---
BANNER_URL = "https://i.ibb.co/FbFMQpf1/thumb-400-anime-boy-5725.webp"

bot = telebot.TeleBot(TOKEN, threaded=False)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
app = Flask(__name__)

# --- MONGODB CONNECTION ---
db_connected = False
users_collection = None
try:
    if MONGO_URI:
        client = pymongo.MongoClient(MONGO_URI)
        db = client['MySearchBotDB']
        users_collection = db['users']
        db_connected = True
except: pass

def add_user_to_db(message):
    if db_connected and users_collection is not None:
        try:
            users_collection.update_one(
                {'_id': message.chat.id}, 
                {'$set': {
                    'first_name': message.chat.first_name,
                    'username': message.chat.username,
                    'type': message.chat.type
                }}, upsert=True)
        except: pass

# --- DELETE MESSAGE HELPER ---
def delete_user_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except: pass

# --- SMART SEARCH LOGIC ---
def is_search_query(text):
    ignore_words = ['hi', 'hello', 'hey', 'start', 'help', 'admin']
    if text.lower() in ignore_words: return False
    return True

def get_smart_query(user_text):
    # Simple query banao taaki result milne ke chance badh jayein
    return f"{user_text} Telegram Channel"

def google_search(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
        
        # Request bhejo
        res = requests.get(url, params=params).json()
        
        # Agar Google ne Error diya (Quota ya Key Error)
        if 'error' in res:
            print(f"Google Error: {res['error']}")
            return []

        if 'items' not in res: 
            return []
            
        results = []
        for i in res['items']:
            title = i.get('title', 'Link').replace('Telegram:', '').strip()[:30] + "..."
            link = i.get('link', '').split('?')[0]
            results.append({'title': title, 'link': link})
        return results
    except Exception as e:
        print(f"Code Error: {e}")
        return []

def get_google_image(user_text):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': user_text + " wallpaper", 'searchType': 'image', 'num': 1}
        res = requests.get(url, params=params).json()
        if 'items' in res: return res['items'][0]['link']
    except: pass
    return None

# --- HANDLERS ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return ''
    return 'Bot is Alive!', 200

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    delete_user_message(message.chat.id, message.message_id)
    add_user_to_db(message)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    # Row 1: Movies & Anime
    markup.add(
        types.InlineKeyboardButton("🎬 Movies", callback_data="guide_movie"),
        types.InlineKeyboardButton("⛩ Anime", callback_data="guide_anime")
    )
    # Row 2: Add to Group
    markup.add(types.InlineKeyboardButton("➕ Add to Group", url="https://t.me/Animesarchingbot?startgroup=true"))
    
    # Row 3: Owner & Support (ADDED ✅)
    markup.add(
        types.InlineKeyboardButton("👤 Owner", url="tg://user?id=6356015122"),
        types.InlineKeyboardButton("💬 Support", url="https://t.me/Sudeep_support_bot")
    )
    
    caption = (
        "<blockquote><b>🤖 Most Powerful Full Anime Search Bot</b>\n\n"
        "• Search any Anime\n"
        "• Search any Movie\n"
        "• Add to Group for more!</blockquote>"
    )
    
    try:
        bot.send_photo(message.chat.id, BANNER_URL, caption=caption, reply_markup=markup, parse_mode="HTML", has_spoiler=True)
    except:
        bot.send_photo(message.chat.id, BANNER_URL, caption=caption, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    # Group filter logic
    if message.chat.type in ['group', 'supergroup']:
        if not is_search_query(message.text): return
        delete_user_message(message.chat.id, message.message_id)
        is_spoiler = True
    else:
        is_spoiler = False
    
    add_user_to_db(message)
    bot.send_chat_action(message.chat.id, 'upload_photo')
    
    query = get_smart_query(message.text)
    results = google_search(query)
    image_url = get_google_image(message.text)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    if results:
        for item in results:
            markup.add(types.InlineKeyboardButton(f"📂 {item['title']}", url=item['link']))
        
        spoiler_tag = "<span class='tg-spoiler'>" if is_spoiler else "<blockquote>"
        end_tag = "</span>" if is_spoiler else "</blockquote>"
        caption = f"{spoiler_tag}🔎 <b>Result:</b> {message.text.title()}{end_tag}"
    else:
        # Error Message change kiya taaki user samjhe
        caption = "<blockquote>😕 <b>No results found.</b>\n(Check Bot Admin API Keys or Spelling)</blockquote>"
        is_spoiler = False
        
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="delete_msg"))
    
    try:
        if image_url:
            bot.send_photo(message.chat.id, image_url, caption=caption, parse_mode="HTML", reply_markup=markup, has_spoiler=is_spoiler)
        else:
            bot.send_message(message.chat.id, caption, parse_mode="HTML", reply_markup=markup)
    except: pass

