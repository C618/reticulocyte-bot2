from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)

# -------------------- Tokens --------------------
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')  # ضع المفتاح هنا مباشرة إذا أحببت

# -------------------- Etats utilisateurs --------------------
user_states = {}
user_languages = {}
calculations_history = []

# -------------------- Claviers --------------------
def get_main_keyboard(lang='fr'):
    keyboards = {
        'fr': {
            'keyboard': [
                ['🔢 Réticulocytes', '🩸 Plaquettes'],
                ['🧪 Dilution', '⚙️ Paramètres'],
                ['ℹ️ Aide', '🔄 Langue']
            ],
            'resize_keyboard': True
        },
        'en': {
            'keyboard': [
                ['🔢 Reticulocytes', '🩸 Platelets'],
                ['🧪 Dilution', '⚙️ Settings'],
                ['ℹ️ Help', '🔄 Language']
            ],
            'resize_keyboard': True
        },
        'ar': {
            'keyboard': [
                ['🔢 الخلايا الشبكية', '🩸 الصفائح الدموية'],
                ['🧪 التخفيف', '⚙️ الإعدادات'],
                ['ℹ️ المساعدة', '🔄 اللغة']
            ],
            'resize_keyboard': True
        }
    }
    return keyboards.get(lang, keyboards['fr'])

# -------------------- ChatGPT API محسّنة --------------------
def ask_openai(prompt):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",  # أو gpt-3.5-turbo
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers, json=data, timeout=15
        )
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        elif "error" in result:
            return f"Erreur ChatGPT: {result['error'].get('message','Unknown error')}"
        else:
            return f"Erreur ChatGPT: réponse inattendue {result}"
    except Exception as e:
        return f"Erreur ChatGPT Exception: {str(e)}"

# -------------------- Envoi des messages --------------------
def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        requests.post(url, json=data, timeout=10)
    except requests.exceptions.RequestException:
        pass

# -------------------- Webhook --------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        lang = user_languages.get(chat_id, 'fr')

        handled = False

        # -------------------- Commandes existantes (exemple minimal) --------------------
        if text == '/start' or text in ['🔙 Retour','🔙 Back','🔙 رجوع']:
            send_message(chat_id, "👋 Bienvenue! Choisissez une option:", get_main_keyboard(lang))
            user_states[chat_id] = {'step': 0}
            handled = True
        elif text in ['/help','ℹ️ Aide','ℹ️ Help','ℹ️ المساعدة']:
            send_message(chat_id, "ℹ️ Commandes disponibles: ...", get_main_keyboard(lang))
            handled = True

        # -------------------- ChatGPT fallback --------------------
        if not handled:
            reply = ask_openai(text)
            send_message(chat_id, reply, get_main_keyboard(lang))

    return jsonify({'status': 'ok'})

@app.route('/')
def home():
    return "Le bot fonctionne correctement !"

# -------------------- Webhook setup --------------------
def set_webhook():
    webhook_url = os.environ.get('WEBHOOK_URL') + '/webhook'
    url = f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url)
        print(f"Webhook set: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error setting webhook: {e}")

if __name__ == '__main__':
    set_webhook()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
