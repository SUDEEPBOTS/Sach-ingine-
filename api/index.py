from flask import Flask, request
import telebot
from telebot import types 
import requests
import os
import pymongo
import google.generativeai as genai

# --- CONFIG ---
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
SEARCH_ENGINE_ID = os.environ.get('SEARCH_ENGINE_ID')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
MONGO_URI = os.environ.get('MONGO_URI')

BANNER_URL = "https://i.ibb.co/FbFMQpf1/thumb-400-anime-boy-5725.webp"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- DEBUG: CHECK KEYS ON START ---
print(f"DEBUG: Token Present? {bool(TOKEN)}")
print(f"DEBUG: Google Key Present? {bool(GOOGLE_API_KEY)}")
print(f"DEBUG: Engine ID Present? {bool(SEARCH_ENGINE_ID)}")

# --- MONGODB ---
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

def delete_user_message(chat_id, message_id):
    try: bot.delete_message(chat_id, message_id)
    except: pass

def get_smart_query(user_text):
    return f"{user_text} Hindi Dubbed Telegram Channel"

# --- DEBUG SEARCH FUNCTION ---
def google_search(query):
    # 1. Pehle check karo Keys hain ya nahi
    if not GOOGLE_API_KEY or not SEARCH_ENGINE_ID:
        return ["ERROR: API Key or Engine ID is Missing in Vercel Settings!"]

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY, 
        'cx': SEARCH_ENGINE_ID, 
        'q': query, 
        'num': 5
    }
    
    try:
        res = requests.get(url, params=params).json()
        
        # 2. Agar Google ne Error diya, toh wo return karo
        if 'error' in res:
            error_msg = res['error']['message']
            print(f"Google API Error: {error_msg}")
            return [f"GOOGLE ERROR: {error_msg}"]
            
        if 'items' not in res: 
            return [] # Sach me koi result nahi mila
            
        results = []
        for i in res['items']:
            title = i.get('title', 'Link').replace('Telegram:', '').strip()[:30] + "..."
            link = i.get('link', '').split('?')[0]
            results.append({'title': title, 'link': link})
        return results

    except Exception as e:
        return [f"CODE ERROR: {str(e)}"]

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
        try:
            json_str = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
            return 'OK', 200
        except: return 'Error', 500
    return 'Bot is Alive!', 200

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    delete_user_message(message.chat.id, message.message_id)
    add_user_to_db(message)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 Movies", callback_data="guide_movie"),
        types.InlineKeyboardButton("⛩ Anime", callback_data="guide_anime"),
        types.InlineKeyboardButton("➕ Add to Group", url="https://t.me/Animesarchingbot?startgroup=true")
    )
    caption = "<b>🤖 Bot Ready!</b>\nSearch something to test."
    try:
        bot.send_photo(message.chat.id, BANNER_URL, caption=caption, reply_markup=markup, parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    # Group Filtering
    is_spoiler = False
    if message.chat.type in ['group', 'supergroup']:
        delete_user_message(message.chat.id, message.message_id)
        is_spoiler = True
    
    add_user_to_db(message)
    bot.send_chat_action(message.chat.id, 'upload_photo')
    
    query = get_smart_query(message.text)
    results = google_search(query)
    image_url = get_google_image(message.text)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # --- ERROR CATCHING LOGIC ---
    if results and isinstance(results[0], str) and ("ERROR" in results[0]):
        # Agar error aaya hai (String return hua hai instead of Dict)
        caption = f"⚠️ <b>SYSTEM ERROR:</b>\n\n<code>{results[0]}</code>\n\n(Send this screenshot to Developer)"
        image_url = None # Error me photo mat dikhao
    elif results:
        # Success
        for item in results:
            markup.add(types.InlineKeyboardButton(f"📂 {item['title']}", url=item['link']))
        spoiler_tag = "<span class='tg-spoiler'>" if is_spoiler else "<blockquote>"
        end_tag = "</span>" if is_spoiler else "</blockquote>"
        caption = f"{spoiler_tag}🔎 <b>Result:</b> {message.text.title()}{end_tag}"
    else:
        # No Results (Sach me nahi mila)
        caption = "<blockquote>😕 <b>No results found.</b>\nTry checking spelling.</blockquote>"
    
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="delete_msg"))
    
    try:
        if image_url:
            bot.send_photo(message.chat.id, image_url, caption=caption, parse_mode="HTML", reply_markup=markup, has_spoiler=is_spoiler)
        else:
            bot.send_message(message.chat.id, caption, parse_mode="HTML", reply_markup=markup)
    except: pass

