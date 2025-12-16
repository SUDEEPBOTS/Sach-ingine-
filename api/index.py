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
model = genai.GenerativeModel('gemini-1.5-flash')
app = Flask(__name__)

# --- GEMINI LOGIC ---
def get_smart_query(user_text):
    try:
        prompt = f"""Convert to Google Search Query.
        Input: "{user_text}"
        Rules: Default to "Hindi Dubbed" if language missing. Default to "site:t.me" if platform missing.
        Output: ONLY the query string."""
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"{user_text} Hindi Dubbed site:t.me"

# --- 1. IMAGE SEARCH FUNCTION (New) ---
def get_google_image(user_text):
    # Hum query me "poster wallpaper" jod denge achi photo ke liye
    img_query = user_text + " movie anime poster wallpaper hd"
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'q': img_query,
        'searchType': 'image',  # Image maang rahe hain
        'num': 1,               # Sirf 1 photo chahiye
        'imgSize': 'large',     # Badi photo
        'safe': 'active'
    }
    try:
        res = requests.get(url, params=params, timeout=5).json()
        if 'items' in res:
            return res['items'][0]['link'] # Pehli image ka URL
    except:
        pass
    return None # Agar photo nahi mili

# --- 2. LINK SEARCH FUNCTION (Clean) ---
def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
    try:
        res = requests.get(url, params=params, timeout=5).json()
        if 'items' not in res: return []
        
        results = []
        for i in res['items']:
            title = i.get('title', 'Link')
            raw_link = i.get('link', '')
            # Clean Link Logic
            clean_link = raw_link.replace('/s/', '/').split('?')[0]
            results.append(f"🔹 **{title}**\n🔗 {clean_link}")
            
        return results
    except Exception as e: return [f"Error: {e}"]

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
    bot.reply_to(message, "👋 **Bol Bhai!** Movie ya Anime ka naam likh, main Banner ke saath link lata hu.")

# Close Button Logic
@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

# --- MAIN HANDLER (Photo Wala) ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    chat_id = message.chat.id
    user_text = message.text
    
    # Action change: Ab "uploading photo" dikhayega
    bot.send_chat_action(chat_id, 'upload_photo')
    
    # 1. Cheezein dhoondo
    query = get_smart_query(user_text)
    links = google_search(query)
    image_url = get_google_image(user_text)
    
    # 2. Caption banao (Text jo photo ke niche aayega)
    caption = f"🎬 **Search Result:** {user_text.title()}\n\n"
    if links:
        caption += "\n\n".join(links)
    else:
        caption += "😕 Links nahi mile, par poster mil gaya!"
    
    # 3. Close Button Banao
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("❌ Close Results", callback_data="delete_msg")
    markup.add(btn)
    
    # 4. Bhejo (Photo ya Text Fallback)
    try:
        if image_url:
            # Agar photo mili toh Photo bhejo
            bot.send_photo(chat_id, image_url, caption=caption, parse_mode="Markdown", reply_markup=markup)
        else:
            # Agar photo nahi mili toh normal text bhejo
            bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        # Agar photo bhejne me error aaye (kabhi kabhi URL block hota hai)
        bot.send_message(chat_id, f"Photo error, par links ye rahe:\n{caption}", parse_mode="Markdown", reply_markup=markup)

        
