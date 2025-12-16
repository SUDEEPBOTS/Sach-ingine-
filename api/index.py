from flask import Flask, request
import telebot
from telebot import types 
import requests
import os
import pymongo
import google.generativeai as genai

# --- 1. CONFIGURATION ---
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
# Nayi wali ID (jo tumne bheji thi)
SEARCH_ENGINE_ID = "4322c10a72e6944a7" 
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
MONGO_URI = os.environ.get('MONGO_URI')

BANNER_URL = "https://i.ibb.co/FbFMQpf1/thumb-400-anime-boy-5725.webp"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- 2. GEMINI AI SETUP (Ye raha tumhara Model) ---
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    print("✅ Gemini AI Connected")
else:
    model = None
    print("⚠️ Gemini Key Missing")

# --- 3. MONGODB SETUP ---
try:
    if MONGO_URI:
        client = pymongo.MongoClient(MONGO_URI)
        db = client['MySearchBotDB']
        users_collection = db['users']
except: pass

def add_user_to_db(message):
    try:
        if users_collection is not None:
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

# --- 4. SMART AI INTENT CHECK (Gemini Logic) ---
def is_search_query(text):
    # Basic words ko ignore karo (Quota bachane ke liye)
    ignore_words = ['hi', 'hello', 'hey', 'start', 'help', 'admin', 'kaise ho', 'gm', 'gn']
    if text.lower() in ignore_words: return False
    
    # Gemini AI se pucho: "Kya ye Anime/Movie ka naam hai?"
    if model:
        try:
            prompt = f"Analyze text: '{text}'. Is this a Movie, Anime, Series, or Book name? Reply ONLY 'YES' or 'NO'."
            response = model.generate_content(prompt)
            # Agar AI 'YES' bole, to Search karo
            return "YES" in response.text.upper()
        except Exception as e:
            print(f"AI Error: {e}")
            return True # Agar AI fail ho to safe side Search kar lo
    return True

# Query Builder
def get_smart_query(user_text):
    return f"{user_text} Hindi Dubbed Telegram Channel"

# --- 5. GOOGLE SEARCH ---
def google_search(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
        res = requests.get(url, params=params).json()
        
        if 'items' not in res: return []
        
        results = []
        for i in res['items']:
            title = i.get('title', 'Link').replace('Telegram:', '').strip()[:30] + "..."
            link = i.get('link', '').split('?')[0]
            results.append({'title': title, 'link': link})
        return results
    except: return []

def get_google_image(user_text):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': user_text + " wallpaper", 'searchType': 'image', 'num': 1}
        res = requests.get(url, params=params).json()
        if 'items' in res: return res['items'][0]['link']
    except: pass
    return None

# --- 6. HANDLERS ---
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
        bot.send_photo(message.chat.id, BANNER_URL, caption=caption, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("guide_"))
def guide_callback(call):
    if call.data == "guide_movie":
        bot.answer_callback_query(call.id, "Just type Movie Name (e.g. Stree 2)!", show_alert=True)
    elif call.data == "guide_anime":
        bot.answer_callback_query(call.id, "Just type Anime Name (e.g. Naruto)!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    # --- GROUP AI LOGIC ---
    is_spoiler = False
    if message.chat.type in ['group', 'supergroup']:
        # Agar message bahut lamba hai to search mat maano
        if len(message.text) > 50: return 
        
        # Yahan Gemini AI check karega ki ye Movie hai ya nahi
        if not is_search_query(message.text): 
            return # Agar chat hai to ignore karo
            
        delete_user_message(message.chat.id, message.message_id)
        is_spoiler = True
    
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
        caption = "<blockquote>😕 <b>No results found.</b>\n(Check Spelling)</blockquote>"
        
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="delete_msg"))
    
    try:
        if image_url:
            bot.send_photo(message.chat.id, image_url, caption=caption, parse_mode="HTML", reply_markup=markup, has_spoiler=is_spoiler)
        else:
            bot.send_message(message.chat.id, caption, parse_mode="HTML", reply_markup=markup)
    except: pass

