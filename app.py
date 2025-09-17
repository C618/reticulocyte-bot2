from flask import Flask, request, jsonify
import requests
import os
import json
import threading
import time
from datetime import datetime

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}
calculations_history = {}

# -------------------- Alarmes --------------------
active_alarms = {}

def start_alarm(chat_id, delay, duration=30):
    """Lancer une alarme qui envoie des notifications pendant 'duration' secondes"""
    def alarm_thread():
        time.sleep(delay)
        start_time = time.time()
        while time.time() - start_time < duration and chat_id in active_alarms:
            send_message(chat_id, "⏰ ALARME ! Réveillez-vous !")
            time.sleep(5)  # répéter toutes les 5 secondes
        active_alarms.pop(chat_id, None)
    active_alarms[chat_id] = True
    threading.Thread(target=alarm_thread, daemon=True).start()

# -------------------- Claviers --------------------
def get_main_keyboard():
    return {
        'keyboard': [
            ['🔢 Réticulocytes', '🩸 Plaquettes'],
            ['🧪 Dilution', '⏰ Alarme'],
            ['⚙️ Paramètres', 'ℹ️ Aide']
        ],
        'resize_keyboard': True
    }

def get_cancel_keyboard():
    return {'keyboard': [['Annuler']], 'resize_keyboard': True}

# -------------------- Textes --------------------
TEXTS = {
    'fr': {
        'welcome': "👋 Bonjour ! Je suis votre assistant de laboratoire.\nChoisissez une option :",
        'alarm_prompt': "⏰ Entrez le délai de l’alarme en secondes (ex: 10) :",
        'alarm_set': "✅ Alarme réglée dans {} secondes. Elle sonnera pendant 30 secondes.",
        'alarm_cancel': "❌ Alarme annulée."
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

        # Commandes
        if text == '/start':
            send_message(chat_id, TEXTS['fr']['welcome'], get_main_keyboard())
            user_states[chat_id] = {'step': 0}

        elif text == '⏰ Alarme':
            send_message(chat_id, TEXTS['fr']['alarm_prompt'], get_cancel_keyboard())
            user_states[chat_id] = {'step': 900, 'type': 'alarm'}

        elif text.lower() == 'annuler':
            if chat_id in active_alarms:
                active_alarms.pop(chat_id, None)
                send_message(chat_id, TEXTS['fr']['alarm_cancel'], get_main_keyboard())
            else:
                send_message(chat_id, "❌ Rien à annuler.", get_main_keyboard())
            user_states[chat_id] = {'step': 0}

        elif chat_id in user_states:
            handle_input(chat_id, text)

    return jsonify({'status': 'ok'})

# -------------------- Gestion des inputs --------------------
def handle_input(chat_id, text):
    state = user_states[chat_id]
    try:
        if state.get('type') == 'alarm' and state['step'] == 900:
            delay = int(text)
            start_alarm(chat_id, delay)
            send_message(chat_id, TEXTS['fr']['alarm_set'].format(delay), get_main_keyboard())
            user_states[chat_id] = {'step': 0}
    except ValueError:
        send_message(chat_id, "⚠️ Veuillez entrer un nombre valide.", get_cancel_keyboard())

# -------------------- Envoi des messages --------------------
def send_message(chat_id, text, reply_markup=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
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
