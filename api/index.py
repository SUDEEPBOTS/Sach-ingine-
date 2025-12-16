from flask import Flask, request
import telebot
import google.generativeai as genai
import requests
import os

# Environment Variables se keys lenge
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
SEARCH_ENGINE_ID = os.environ.get('SEARCH_ENGINE_ID')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

bot = telebot.TeleBot(TOKEN, threaded=False)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
app = Flask(__name__)

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

def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {'key': GOOGLE_API_KEY, 'cx': SEARCH_ENGINE_ID, 'q': query, 'num': 5}
    try:
        res = requests.get(url, params=params).json()
        if 'items' not in res: return ["Kuch nahi mila bhai."]
        return [f"🎬 {i['title']}\n🔗 {i['link']}" for i in res['items']]
    except Exception as e: return [f"Error: {e}"]

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return ''
    return 'Bot Running!', 200

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    bot.send_message(message.chat.id, "🔍 *Dhoond raha hu...*", parse_mode="Markdown")
    query = get_smart_query(message.text)
    links = google_search(query)
    bot.send_message(message.chat.id, f"**Search:** `{query}`\n\n" + "\n\n".join(links), parse_mode="Markdown")
      
