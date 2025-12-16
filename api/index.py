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

# --- SAFE IMAGE URL (100% Working) ---
# Hum Local File use nahi karenge kyunki wo Vercel par path error de raha hai
BANNER_URL = "https://i.ibb.co/FbFMQpf1/thumb-400-anime-boy-5725.webp"

bot = telebot.TeleBot(TOKEN, threaded=False)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
app = Flask(__name__)

# --- MONGODB CONNECTION (Safe Mode) ---
db_connected = False
users_collection = None
try:
    if MONGO_URI:
        client = pymongo.MongoClient(MONGO_URI)
        db = client['MySearchBotDB']
        users_collection = db['users']
        db_connected = True
        print("✅ MongoDB Connected")
except Exception as e:
    print(f"⚠️ MongoDB Error: {e}")

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

# --- HELPER: DELETE MESSAGE ---
def delete_user_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except: pass

# --- SMART AI INTENT ---
def is_search_query(text):
    ignore_words = ['hi', 'hello', 'hey', 'start', 'help', 'admin']
    if text.lower() in ignore_words: return False
    try:
        prompt = f"Is '{text}' a movie/anime name? Reply YES or NO."
        response = model.generate_content(prompt)
        return "YES" in response.text.upper()
    except: return True 

def get_smart_query(user_text):
    try:
        response = model.generate_content(f"Convert '{user_text}' to search query with 'Telegram Channel'.")
        return response.text.strip()
    except: return f"{user_text} Telegram Channel site:t.me"

def google_search(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
        res = requests.get(url, params=params).json()
        results = []
        if 'items' in res:
            for i in res['items']:
                title = i.get('title', 'Link').replace('Telegram:', '').strip()[:30] + "..."
                link = i.get('link', '').split('?')[0]
                results.append({'title': title, 'link': link})
        return results
    except: return []

def get_google_image(user_text):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': user_text + " poster", 'searchType': 'image', 'num': 1}
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
    markup.add(
        types.InlineKeyboardButton("🎬 Movies", callback_data="guide_movie"),
        types.InlineKeyboardButton("⛩ Anime", callback_data="guide_anime")
    )
    markup.add(types.InlineKeyboardButton("➕ Add to Group", url="https://t.me/Animesarchingbot?startgroup=true"))
    
    caption = (
        "<blockquote><b>🤖 Most Powerful Full Anime Search Bot</b>\n\n"
        "• Search any Anime\n"
        "• Search any Movie\n"
        "• Add to Group for more!</blockquote>"
    )
    
    # --- ANTI-CRASH PHOTO SENDER ---
    try:
        # Pehle Blur ke sath try karo
        bot.send_photo(message.chat.id, BANNER_URL, caption=caption, reply_markup=markup, parse_mode="HTML", has_spoiler=True)
    except Exception as e:
        print(f"Spoiler Error: {e}")
        # Agar error aaye (library old ho), toh normal photo bhejo
        bot.send_photo(message.chat.id, BANNER_URL, caption=caption, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    # Group Filter
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
        caption = "<blockquote>😕 No results found.</blockquote>"
        
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="delete_msg"))
    
    try:
        # Safe Sending Logic
        if image_url:
            try:
                bot.send_photo(message.chat.id, image_url, caption=caption, parse_mode="HTML", reply_markup=markup, has_spoiler=is_spoiler)
            except:
                # Agar spoiler fail ho jaye
                bot.send_photo(message.chat.id, image_url, caption=caption, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, caption, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")
        
