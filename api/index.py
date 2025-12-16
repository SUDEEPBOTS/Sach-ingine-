from flask import Flask, request
import telebot
from telebot import types # Button ke liye
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

# --- SEARCH LOGIC ---
def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
    try:
        res = requests.get(url, params=params).json()
        if 'items' not in res: return []
        
        results = []
        for i in res['items']:
            title = i.get('title', 'Link')
            raw_link = i.get('link', '')
            clean_link = raw_link.replace('/s/', '/') # Link Fix
            results.append(f"🎬 **{title}**\n🔗 {clean_link}")
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

# 1. Start Command
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 **Bol Bhai!** Movie ya Anime ka naam likh, main link dhoondta hu.")

# 2. Callback Handler (Delete Button Logic)
@bot.callback_query_handler(func=lambda call: call.data == "delete_msg")
def delete_message_handler(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass # Agar message pehle hi delete ho gaya ho

# 3. Main Search Handler
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text.startswith('/'): return 
    
    # Typing action
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Pehle "Searching" message bhejo
    msg = bot.send_message(message.chat.id, "🔍 *Dhoond raha hu...*", parse_mode="Markdown")
    
    query = get_smart_query(message.text)
    links = google_search(query)
    
    # Close Button Banao
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("❌ Close / Delete", callback_data="delete_msg")
    markup.add(btn)
    
    if links:
        response = f"🎯 **Result:** `{query}`\n\n" + "\n\n".join(links)
    else:
        response = f"😕 **Kuch nahi mila.**\nTry: `{query}`"

    # Message ko EDIT karo (Naya nahi bhejega) + Button lagao
    try:
        bot.edit_message_text(
            response, 
            chat_id=message.chat.id, 
            message_id=msg.message_id, 
            parse_mode="Markdown",
            reply_markup=markup,  # Button add kiya
            disable_web_page_preview=True # Chat clean rakhne ke liye preview off
        )
    except:
        bot.send_message(message.chat.id, response, reply_markup=markup)
        
