from flask import Flask, request, jsonify
import requests
import os
import json
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}
user_languages = {}
active_alarms = {}

# Clavier principal en français
def get_main_keyboard():
    return {
        'keyboard': [
            ['🔢 Réticulocytes', '🩸 Plaquettes'],
            ['🧪 Dilution', '⚙️ Paramètres'],
            ['⏰ Minuteur', 'ℹ️ Aide']
        ],
        'resize_keyboard': True
    }

def get_numeric_keyboard():
    return {
        'keyboard': [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10'],
            ['15', '20', '25', '30', '50'],
            ['Annuler']
        ],
        'resize_keyboard': True
    }

def get_cancel_keyboard():
    return {'keyboard': [['Annuler']], 'resize_keyboard': True}

TEXTS = {
    'fr': {
        'welcome': "👋 Bonjour ! Je suis votre assistant de laboratoire.\nChoisissez une option :",
        'help_text': "ℹ️ *AIDE - Commandes disponibles*\n\n🔢 Réticulocytes\n🩸 Plaquettes\n🧪 Dilution\n⚙️ Paramètres\n⏰ Minuteur\n/start - Démarrer le bot\n/help - Aide",
        'cancel': "❌ Opération annulée.",
        'invalid_number': "⚠️ Veuillez entrer un nombre valide.",
        'alarm_prompt': "⏰ Entrez le temps du minuteur en secondes :",
        'alarm_set': "✅ Minuteur réglé pour {} secondes !"
    }
}

@app.route('/')
def home():
    return "Le bot fonctionne correctement !"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')

        # Commandes principales
        if text == '/start' or text == '🔙 Retour':
            send_message(chat_id, TEXTS['fr']['welcome'], get_main_keyboard())
            user_states[chat_id] = {'step': 0}

        elif text == '/help' or text == 'ℹ️ Aide':
            send_message(chat_id, TEXTS['fr']['help_text'], get_main_keyboard(), parse_mode='Markdown')

        elif text == '⏰ Minuteur':
            send_message(chat_id, TEXTS['fr']['alarm_prompt'], get_numeric_keyboard())
            user_states[chat_id] = {'step': 'alarm'}

        elif text.lower() == 'annuler':
            send_message(chat_id, TEXTS['fr']['cancel'], get_main_keyboard())
            user_states[chat_id] = {'step': 0}

        elif chat_id in user_states:
            state = user_states[chat_id]
            if state.get('step') == 'alarm':
                try:
                    seconds = int(text)
                    if seconds <= 0:
                        raise ValueError
                    start_alarm(chat_id, seconds)
                    send_message(chat_id, TEXTS['fr']['alarm_set'].format(seconds), get_main_keyboard())
                    user_states[chat_id] = {'step': 0}
                except ValueError:
                    send_message(chat_id, TEXTS['fr']['invalid_number'], get_numeric_keyboard())

    return jsonify({'status': 'ok'})

# -------------------- Minuteur --------------------
def start_alarm(chat_id, delay, duration=30):
    end_time = datetime.now() + timedelta(seconds=delay)

    def alarm_thread():
        while chat_id in active_alarms:
            now = datetime.now()
            if now >= end_time:
                start_alarm_time = time.time()
                while time.time() - start_alarm_time < duration:
                    send_message(chat_id, "⏰ ALARME ! Le temps est écoulé.")
                    time.sleep(5)
                active_alarms.pop(chat_id, None)
                break
            time.sleep(0.5)

    active_alarms[chat_id] = True
    threading.Thread(target=alarm_thread, daemon=True).start()

# -------------------- Envoi des messages --------------------
def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        requests.post(url, json=data, timeout=10)
    except requests.exceptions.RequestException:
        pass

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
