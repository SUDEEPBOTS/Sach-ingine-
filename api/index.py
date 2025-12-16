from flask import Flask, request
import telebot
from telebot import types 
import google.generativeai as genai
import requests
import os

# --- CONFIG ---
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
SEARCH_ENGINE_ID = os.environ.get('SEARCH_ENGINE_ID')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

bot = telebot.TeleBot(TOKEN, threaded=False)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
app = Flask(__name__)

# --- 1. GEMINI LOGIC ---
def get_smart_query(user_text):
    try:
        prompt = f"""Convert to Google Search Query.
        Input: "{user_text}"
        Rules: 
        1. Default to "in Hindi Dubbed" if language missing.
        2. ALWAYS Add "Telegram Channel link " in the query.
        3. Default site is "site:t.me".
        Output: ONLY the query string."""
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"{user_text} Hindi Dubbed Telegram Channel site:t.me"

# --- 2. IMAGE SEARCH ---
def get_google_image(user_text):
    img_query = user_text + " movie anime poster wallpaper hd"
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'q': img_query,
        'searchType': 'image',
        'num': 1,
        'imgSize': 'large',
        'safe': 'active'
    }
    try:
        res = requests.get(url, params=params, timeout=5).json()
        if 'items' in res: return res['items'][0]['link']
    except: pass
    return None

# --- 3. LINK SEARCH ---
def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
    try:
        res = requests.get(url, params=params, timeout=5).json()
        if 'items' not in res: return []
        
        results = []
        for i in res['items']:
            title = i.get('title', 'Channel Link')
            clean_title = title.replace('Telegram:', '').replace('Channel', '').strip()[:30] + "..." 
            raw_link = i.get('link', '')
            clean_link = raw_link.replace('/s/', '/').split('?')[0]
            results.append({'title': clean_title, 'link': clean_link})
        return results
    except Exception as e: return []

# --- HANDLERS ---

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return ''
    return 'Bot is Alive!', 200

# --- START MENU (BLUR PHOTO + OWNER ID) ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Yahan apni pasand ki photo ka link daal dena
    welcome_img = "https://ibb.co/4ZHGbkDL"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Search Buttons
    markup.add(
        types.InlineKeyboardButton("🎬 Movies", callback_data="guide_movie"),
        types.InlineKeyboardButton("⛩ Anime", callback_data="guide_anime")
    )
    
    # Owner & Support Buttons (Tumhari ID set kar di hai)
    markup.add(
        types.InlineKeyboardButton("👤 Owner", url="tg://user?id=6356015122"), 
        types.InlineKeyboardButton("💬 Support", url="https://t.me/Sudeep_support_bot") # Yahan Support link daal dena
    )
    
    # Blockquote Design
    caption = (
        "<blockquote><b>👋 Search Bot Ready!</b>\n"
        "lats start searching anime.</blockquote>"
    )
    
    # has_spoiler=True se photo Blur aayegi
    bot.send_photo(message.chat.id, welcome_img, caption=caption, reply_markup=markup, parse_mode="HTML", has_spoiler=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('guide_'))
def guide_buttons(call):
    bot.answer_callback_query(call.id, "Naam likh kar bhejo!")

@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

# --- MAIN SEARCH HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    chat_id = message.chat.id
    user_text = message.text
    
    bot.send_chat_action(chat_id, 'upload_photo')
    
    query = get_smart_query(user_text)
    results_list = google_search(query)
    image_url = get_google_image(user_text)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if results_list:
        for item in results_list:
            btn = types.InlineKeyboardButton(text=f"📂 {item['title']}", url=item['link'])
            markup.add(btn)
        caption = f"<blockquote>🔎 <b>Search Result:</b> {user_text.title()}</blockquote>"
    else:
        caption = "<blockquote>😕 <b>Koi dhang ka channel nahi mila.</b></blockquote>"
    
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="delete_msg"))
    
    try:
        if image_url:
            # Result wali photo blur nahi rakhi hai, sirf Start wali rakhi hai
            bot.send_photo(chat_id, image_url, caption=caption, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        bot.send_message(chat_id, "Error aagaya par koshish jari hai...", reply_markup=markup)
        
