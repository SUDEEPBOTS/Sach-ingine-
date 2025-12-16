from flask import Flask, request
import telebot
from telebot import types 
import google.generativeai as genai
import requests
import os
import pymongo

# --- 1. CONFIGURATION (Saari Keys Yahan Hain) ---
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONGO_URI = os.environ.get('MONGO_URI')

# Search ke liye
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') 
SEARCH_ENGINE_ID = os.environ.get('SEARCH_ENGINE_ID')

# AI (Gemini) ke liye
GEMINI_KEY = os.environ.get('GEMINI_API_KEY') 

# Image URL
BANNER_URL = "https://i.ibb.co/FbFMQpf1/thumb-400-anime-boy-5725.webp"

# --- 2. SETUP (Jo tune bola missing tha) ---
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Gemini AI Configure kar rahe hain
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    print("⚠️ GEMINI_API_KEY missing in Vercel!")

# --- 3. MONGODB CONNECTION ---
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

# --- 4. HELPER FUNCTIONS ---
def delete_user_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except: pass

# AI check karega ki ye Movie name hai ya Chat
def is_search_query(text):
    ignore_words = ['hi', 'hello', 'hey', 'start', 'help', 'admin', 'bot', 'kaise ho']
    if text.lower() in ignore_words: return False
    
    # Agar Gemini key hai to AI se pucho, nahi to basic check karo
    if GEMINI_KEY:
        try:
            prompt = f"Is '{text}' a movie, anime, or series name? Reply YES or NO."
            response = model.generate_content(prompt)
            return "YES" in response.text.upper()
        except: return True
    return True

# Query ko Smart banata hai (Hindi Dubbed add karke)
def get_smart_query(user_text):
    return f"{user_text} Hindi Dubbed Telegram Channel"

# --- 5. GOOGLE SEARCH LOGIC (API Key Yahan Use Hoti Hai) ---
def google_search(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        # Dekh bhai, yahan 'key' me GOOGLE_API_KEY ja raha hai
        params = {
            'key': GOOGLE_API_KEY, 
            'cx': SEARCH_ENGINE_ID, 
            'q': query, 
            'num': 5
        }
        res = requests.get(url, params=params).json()
        
        if 'items' not in res: return []
        
        results = []
        for i in res['items']:
            title = i.get('title', 'Link').replace('Telegram:', '').strip()[:30] + "..."
            link = i.get('link', '').split('?')[0]
            results.append({'title': title, 'link': link})
        return results
    except Exception as e:
        print(f"Search Error: {e}")
        return []

def get_google_image(user_text):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': GOOGLE_API_KEY, 
            'cx': SEARCH_ENGINE_ID, 
            'q': user_text + " wallpaper", 
            'searchType': 'image', 
            'num': 1
        }
        res = requests.get(url, params=params).json()
        if 'items' in res: return res['items'][0]['link']
    except: pass
    return None

# --- 6. HANDLERS (Bot Logic) ---
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

# Welcome Message
@app.message_handler(commands=['start', 'help'])
def send_welcome(message):
    delete_user_message(message.chat.id, message.message_id)
    add_user_to_db(message)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 Movies", callback_data="guide_movie"),
        types.InlineKeyboardButton("⛩ Anime", callback_data="guide_anime")
    )
    markup.add(types.InlineKeyboardButton("➕ Add to Group", url="https://t.me/Animesarchingbot?startgroup=true"))
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
        bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="HTML")

# Close Button
@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

# Main Message Handler
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    # Group Filtering
    if message.chat.type in ['group', 'supergroup']:
        if not is_search_query(message.text): return
        delete_user_message(message.chat.id, message.message_id)
        is_spoiler = True
    else:
        is_spoiler = False
    
    add_user_to_db(message)
    bot.send_chat_action(message.chat.id, 'upload_photo')
    
    # Search Logic
    query = get_smart_query(message.text)
    results = google_search(query)
    image_url = get_google_image(message.text)
    
    # Buttons Logic
    markup = types.InlineKeyboardMarkup(row_width=1)
    if results:
        for item in results:
            markup.add(types.InlineKeyboardButton(f"📂 {item['title']}", url=item['link']))
        
        spoiler_tag = "<span class='tg-spoiler'>" if is_spoiler else "<blockquote>"
        end_tag = "</span>" if is_spoiler else "</blockquote>"
        caption = f"{spoiler_tag}🔎 <b>Result:</b> {message.text.title()}{end_tag}"
    else:
        caption = "<blockquote>😕 <b>No results found.</b>\n(Check Keys or Spelling)</blockquote>"
        is_spoiler = False
        
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="delete_msg"))
    
    # Sending Logic (Safe)
    try:
        if image_url:
            bot.send_photo(message.chat.id, image_url, caption=caption, parse_mode="HTML", reply_markup=markup, has_spoiler=is_spoiler)
        else:
            bot.send_message(message.chat.id, caption, parse_mode="HTML", reply_markup=markup)
    except: pass

