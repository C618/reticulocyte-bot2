from flask import Flask, request, jsonify
import requests
import os
import json
import threading
import time
from datetime import datetime

app = Flask(__name__)

# --- Token du bot ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}
user_languages = {}
active_alarms = {}

# -------------------- Claviers --------------------
def get_main_keyboard(lang='fr'):
    return {
        'keyboard': [
            ['🔢 Réticulocytes', '🩸 Plaquettes'],
            ['🧪 Dilution', '⚙️ Paramètres'],
            ['⏰ Alarme', 'ℹ️ Aide']
        ],
        'resize_keyboard': True
    }

def get_numeric_keyboard(lang='fr'):
    return {
        'keyboard': [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10'],
            ['15', '20', '25', '30', '50'],
            ['Annuler']
        ],
        'resize_keyboard': True
    }

def get_dilution_keyboard(lang='fr'):
    return {
        'keyboard': [
            ['1/2', '1/5', '1/10'],
            ['1/20', '1/50', '1/100'],
            ['1/200', '1/500', '1/1000'],
            ['Annuler']
        ],
        'resize_keyboard': True
    }

def get_cancel_keyboard(lang='fr'):
    return {
        'keyboard': [['Annuler']],
        'resize_keyboard': True
    }

def get_settings_keyboard(lang='fr'):
    return {
        'keyboard': [
            ['🔙 Retour'],
            ['🗑️ Effacer historique'],
            ['📊 Statistiques']
        ],
        'resize_keyboard': True
    }

# -------------------- Textes --------------------
TEXTS = {
    'fr': {
        'welcome': "👋 Bonjour ! Je suis votre assistant de laboratoire.\nChoisissez une option :",
        'reti_fields': "🔢 Combien de champs voulez-vous analyser pour les réticulocytes ?",
        'plaq_fields': "🩸 Combien de champs voulez-vous analyser pour les plaquettes ?",
        'dilution_prompt': "🧪 Entrez la dilution souhaitée (ex: 1/2, 1/10) :",
        'reti_count': "Entrez le nombre de réticulocytes dans le Champ {} :",
        'plaq_count': "Entrez le nombre de plaquettes dans le Champ {} :",
        'rbc_quarter': "Entrez le nombre de globules rouges dans le quart de Champ {} :",
        'gr_auto': "⚙️ Entrez le nombre de globules rouges auto (machine) :",
        'cancel': "❌ Opération annulée.",
        'invalid_number': "⚠️ Veuillez entrer un nombre valide.",
        'result_reti': "--- Résultat Réticulocytes ---\nTotal réticulocytes: {}\nMoyenne GR: {:.2f}\nTaux: {:.2f}%",
        'result_plaq': "--- Résultat Plaquettes ---\nMoyenne plaquettes: {:.2f}\nMoyenne GR: {:.2f}\nGR auto: {}\nRésultat: {:.2f}",
        'dilution_result': "🧪 Pour une dilution {}/{} :\n- Substance: {} partie(s)\n- Diluant: {} partie(s)",
        'quantity_prompt': "Entrez la quantité totale souhaitée :",
        'exact_volumes': "📊 Pour {} unité(s) :\n- Substance: {:.2f}\n- Diluant: {:.2f}",
        'help_text': """ℹ️ *AIDE - Commandes disponibles*

🔢 *Réticulocytes* : Calcul du taux de réticulocytes
🩸 *Plaquettes* : Calcul du nombre de plaquettes
🧪 *Dilution* : Préparation de dilutions
⚙️ *Paramètres* : Configuration du bot
⏰ *Alarme* : Définir un minuteur

*Commandes rapides* :
/start - Démarrer le bot
/help - Afficher l'aide
/calc - Calcul réticulocytes
/plaquettes - Calcul plaquettes
/dilution - Préparation dilution
/alarm - Définir alarme""",
        'settings': "⚙️ *Paramètres* :\n- Historique: Activé",
        'stats': "📊 *Statistiques* :\n- Calculs effectués: {}\n- Dernier calcul: {}",
        'alarm_prompt': "⏰ Entrez le temps en secondes pour l'alarme :"
    }
}

calculations_history = []

# -------------------- Webhook --------------------
@app.route('/')
def home():
    return "Bot actif !"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        lang = 'fr'

        # Commandes principales
        if text == '/start':
            send_message(chat_id, TEXTS[lang]['welcome'], get_main_keyboard(lang))
            user_states[chat_id] = {'step': 0}

        elif text == 'ℹ️ Aide':
            send_message(chat_id, TEXTS[lang]['help_text'], get_main_keyboard(lang), parse_mode='Markdown')

        elif text == '⏰ Alarme':
            send_message(chat_id, TEXTS[lang]['alarm_prompt'], get_numeric_keyboard(lang))
            user_states[chat_id] = {'step': 900}

        elif text.lower() in ['annuler']:
            if chat_id in active_alarms:
                active_alarms.pop(chat_id, None)
                send_message(chat_id, "❌ Alarme annulée.", get_main_keyboard(lang))
            else:
                send_message(chat_id, TEXTS[lang]['cancel'], get_main_keyboard(lang))
            user_states[chat_id] = {'step': 0}

        elif chat_id in user_states:
            state = user_states[chat_id]
            # Gestion alarme
            if state.get('step') == 900:
                try:
                    delay = int(text)
                    start_alarm(chat_id, delay)
                    send_message(chat_id, f"✅ Alarme réglée dans {delay} secondes (durée 30s).", get_main_keyboard(lang))
                    user_states[chat_id] = {'step': 0}
                except ValueError:
                    send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))

    return jsonify({'status': 'ok'})

# -------------------- Alarme --------------------
def start_alarm(chat_id, delay, duration=30):
    def alarm_thread():
        time.sleep(delay)
        start_time = time.time()
        while time.time() - start_time < duration and chat_id in active_alarms:
            send_message(chat_id, "⏰ ALARME ! Le temps est écoulé.")
            time.sleep(5)
        active_alarms.pop(chat_id, None)

    active_alarms[chat_id] = True
    threading.Thread(target=alarm_thread, daemon=True).start()

# -------------------- Send Message --------------------
def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

# -------------------- Webhook setup --------------------
def set_webhook():
    webhook_url = os.environ.get('WEBHOOK_URL') + '/webhook'
    url = f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url)
        print(f"Webhook set: {response.json()}")
    except Exception as e:
        print("Erreur webhook:", e)

if __name__ == '__main__':
    set_webhook()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
