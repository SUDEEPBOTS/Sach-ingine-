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

# --- 3. LINK SEARCH (Returns Data for Buttons) ---
def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
    try:
        res = requests.get(url, params=params, timeout=5).json()
        if 'items' not in res: return []
        
        results = []
        for i in res['items']:
            title = i.get('title', 'Channel Link')
            # Title safai (Button me jyada lamba text allowed nahi hota)
            clean_title = title.replace('Telegram:', '').replace('Channel', '').strip()[:30] + "..." 
            
            raw_link = i.get('link', '')
            # Link safai
            clean_link = raw_link.replace('/s/', '/').split('?')[0]
            
            # List me Dictionary bana ke store karenge
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

# Start Menu
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_img = "https://cdn-icons-png.flaticon.com/512/2111/2111646.png"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 Movies", callback_data="guide_movie"),
        types.InlineKeyboardButton("⛩ Anime", callback_data="guide_anime")
    )
    bot.send_photo(message.chat.id, welcome_img, caption="👋 **Search Bot Ready!**\nNaam likho, main dhoond dunga.", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('guide_'))
def guide_buttons(call):
    bot.answer_callback_query(call.id, "Naam likh kar bhejo!")

@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

# --- MAIN SEARCH HANDLER (Buttons Wala) ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    chat_id = message.chat.id
    user_text = message.text
    
    bot.send_chat_action(chat_id, 'upload_photo')
    
    # 1. Search Data
    query = get_smart_query(user_text)
    results_list = google_search(query) # Ab ye list wapas karega
    image_url = get_google_image(user_text)
    
    # 2. Buttons Banao
    markup = types.InlineKeyboardMarkup(row_width=1) # Ek line me ek button
    
    if results_list:
        for item in results_list:
            # Har result ke liye ek Button add karo
            btn = types.InlineKeyboardButton(text=f"📂 {item['title']}", url=item['link'])
            markup.add(btn)
        
        caption = f"🔎 **Search Result:** {user_text.title()}"
    else:
        caption = "😕 Koi dhang ka channel nahi mila."
    
    # 3. Close Button Add Karo
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="delete_msg"))
    
    # 4. Send
    try:
        if image_url:
            bot.send_photo(chat_id, image_url, caption=caption, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        bot.send_message(chat_id, "Error aagaya par koshish jari hai...", reply_markup=markup)
        
