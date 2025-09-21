from flask import Flask, request, jsonify
import requests
import os
import json
import re
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

def get_numeric_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10'],
            ['15', '20', '25', '30', '50'],
            [cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_dilution_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [
            ['1/2', '1/5', '1/10'],
            ['1/20', '1/50', '1/100'],
            ['1/200', '1/500', '1/1000'],
            [cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_cancel_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [[cancel_text[lang]]],
        'resize_keyboard': True
    }

def get_language_keyboard():
    return {
        'keyboard': [
            ['🇫🇷 Français', '🇬🇧 English'],
            ['🇸🇦 العربية', '🔙 Retour']
        ],
        'resize_keyboard': True
    }

def get_settings_keyboard(lang='fr'):
    texts = {
        'fr': ['🔙 Retour', '🗑️ Effacer historique', '📊 Statistiques'],
        'en': ['🔙 Back', '🗑️ Clear history', '📊 Statistics'],
        'ar': ['🔙 رجوع', '🗑️ مسح السجل', '📊 الإحصائيات']
    }
    return {
        'keyboard': [[texts[lang][0]], [texts[lang][1]], [texts[lang][2]]],
        'resize_keyboard': True
    }

# -------------------- Textes --------------------
TEXTS = {
    # ... (نسخ TEXTS من كودك السابق كما هو) ...
}

# -------------------- ChatGPT API --------------------
def ask_openai(prompt):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers, json=data, timeout=15
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erreur ChatGPT: {str(e)}"

# -------------------- Messages --------------------
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

def send_welcome_start(chat_id, lang='fr'):
    send_message(chat_id, TEXTS[lang]['welcome'], get_main_keyboard(lang))

def send_welcome_end(chat_id, lang='fr'):
    message = {
        'fr': "✅ Calcul terminé !\nChoisissez une autre option :",
        'en': "✅ Calculation completed!\nChoose another option:",
        'ar': "✅ اكتمل الحساب!\nاختر خيارًا آخر:"
    }
    send_message(chat_id, message.get(lang, "✅ Done!"), get_main_keyboard(lang))

# -------------------- Gestion du webhook --------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        lang = user_languages.get(chat_id, 'fr')

        handled = False

        # -------------------- Commandes existantes --------------------
        if text == '/start' or text in ['🔙 Retour','🔙 Back','🔙 رجوع']:
            send_welcome_start(chat_id, lang)
            user_states[chat_id] = {'step': 0}
            handled = True
        elif text in ['/help','ℹ️ Aide','ℹ️ Help','ℹ️ المساعدة']:
            send_message(chat_id, TEXTS[lang]['help_text'], get_main_keyboard(lang), parse_mode='Markdown')
            handled = True
        # ... هنا يجب نسخ كل باقي أوامر البوت الأصلية من كودك السابق ...
        
        # -------------------- ChatGPT fallback --------------------
        if not handled:
            reply = ask_openai(text)
            send_message(chat_id, reply, get_main_keyboard(lang))

    return jsonify({'status': 'ok'})

@app.route('/')
def home():
    return "Le bot fonctionne correctement !"

# -------------------- Webhook --------------------
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


