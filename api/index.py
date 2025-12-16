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

# Photo file ka naam jo tumne root me upload ki hai
LOCAL_IMAGE_NAME = "banner.png" 

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

# --- 1. SMART INTENT CHECK (Group ke liye) ---
def is_search_query(text):
    ignore_words = ['hi', 'hello', 'hey', 'gm', 'gn', 'ok', 'thanks', 'admin', 'bot', 'help', 'start']
    if text.lower() in ignore_words:
        return False
    try:
        prompt = f"""Analyze this text: "{text}"
        Is this a name of a Movie, Anime, TV Series, or Book? 
        Or is it a casual chat message?
        Reply ONLY 'YES' if it is media/search content.
        Reply 'NO' if it is chat/greeting/nonsense.
        """
        response = model.generate_content(prompt)
        return "YES" in response.text.upper()
    except:
        return True

# --- 2. QUERY MAKER ---
def get_smart_query(user_text):
    try:
        response = model.generate_content(f"""Convert to Search Query.
        Input: "{user_text}"
        Rules: Default to "in Hindi Dubbed", Add "Telegram Channel link".
        Output: ONLY query.""")
        return response.text.strip()
    except:
        return f"{user_text} in Hindi Dubbed Telegram Channel site:t.me"

# --- 3. SEARCH FUNCTIONS ---
def get_google_image(user_text):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 
            'q': user_text + " poster wallpaper hd", 
            'searchType': 'image', 'num': 1, 'imgSize': 'large', 'safe': 'active'
        }
        res = requests.get(url, params=params, timeout=5).json()
        if 'items' in res: return res['items'][0]['link']
    except: pass
    return None

def google_search(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
        res = requests.get(url, params=params, timeout=5).json()
        if 'items' not in res: return []
        results = []
        for i in res['items']:
            title = i.get('title', 'Link').replace('Telegram:', '').replace('Channel', '').strip()[:30] + "..."
            link = i.get('link', '').replace('/s/', '/').split('?')[0]
            results.append({'title': title, 'link': link})
        return results
    except: return []

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
    add_user_to_db(message)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 Movies", callback_data="guide_movie"),
        types.InlineKeyboardButton("⛩ Anime", callback_data="guide_anime"),
        types.InlineKeyboardButton("👤 Owner", url="tg://user?id=6356015122")
    )
    caption = "<blockquote><b>👋 Bot Ready!</b>\nNaam likho, main dhoond dunga.</blockquote>"
    
    # YAHAN CHANGE HAI: Local file ko open karke bhej rahe hain
    try:
        # 'rb' ka matlab hai read binary mode me file kholo
        with open(LOCAL_IMAGE_NAME, 'rb') as photo_file:
            bot.send_photo(message.chat.id, photo_file, caption=caption, reply_markup=markup, parse_mode="HTML", has_spoiler=True)
    except Exception as e:
        # Agar file nahi mili ya koi error aaya to sirf text bhej do
        print(f"Photo Error: {e}")
        bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    # --- SMART GROUP LOGIC ---
    if message.chat.type in ['group', 'supergroup']:
        if not is_search_query(message.text):
            return 
            
    # --- PROCESSING ---
    add_user_to_db(message)
    bot.send_chat_action(message.chat.id, 'upload_photo')
    
    query = get_smart_query(message.text)
    results = google_search(query)
    image_url = get_google_image(message.text)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    if results:
        for item in results:
            markup.add(types.InlineKeyboardButton(f"📂 {item['title']}", url=item['link']))
        caption = f"<blockquote>🔎 <b>Result:</b> {message.text.title()}</blockquote>"
    else:
        caption = "<blockquote>😕 <b>Nahi mila.</b> Spelling check karo.</blockquote>"
        
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="delete_msg"))
    
    try:
        if image_url:
            bot.send_photo(message.chat.id, image_url, caption=caption, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, caption, parse_mode="HTML", reply_markup=markup)
    except: pass

