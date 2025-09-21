from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)

# Token du bot Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# DeepSeek API
DEESEEKB_API_KEY = "sk-c092b5aecb284089adae770a030c0026"
DEESEEKB_API_URL = "https://api.deepseek.com/v1/query"

def query_deepseek(prompt: str):
    headers = {
        "Authorization": f"Bearer {DEESEEKB_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"prompt": prompt, "max_tokens": 500}
    try:
        response = requests.post(DEESEEKB_API_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "result" in data:
            return data["result"]
        elif "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("text", "")
        else:
            return "Aucun résultat retourné par DeepSeek."
    except requests.exceptions.RequestException as e:
        return f"Erreur API DeepSeek: {str(e)}"

user_states = {}

# -------------------- Claviers --------------------
def get_main_keyboard():
    return {
        'keyboard': [
            ['🔢 Réticulocytes', '🩸 Plaquettes'],
            ['🧪 Dilution', '⚙️ Paramètres'],
            ['🔍 DeepSeek', 'ℹ️ Aide'],
            ['🔄 Langue']
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

def get_dilution_keyboard():
    return {
        'keyboard': [
            ['1/2', '1/5', '1/10'],
            ['1/20', '1/50', '1/100'],
            ['1/200', '1/500', '1/1000'],
            ['Annuler']
        ],
        'resize_keyboard': True
    }

def get_cancel_keyboard():
    return {'keyboard': [['Annuler']], 'resize_keyboard': True}

def get_settings_keyboard():
    return {'keyboard': [['🔙 Retour'], ['🗑️ Effacer historique'], ['📊 Statistiques']], 'resize_keyboard': True}

# -------------------- Textes --------------------
TEXTS = {
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
🔄 *Langue* : Changer la langue
🔍 *DeepSeek* : Analyse avec DeepSeek
*Commandes rapides* :
/start - Démarrer le bot
/help - Afficher l'aide
/calc - Calcul réticulocytes
/plaquettes - Calcul plaquettes
/dilution - Préparation dilution""",
    'settings': "⚙️ *Paramètres* :\n- Langue: Français\n- Historique: Activé",
    'stats': "📊 *Statistiques* :\n- Calculs effectués: {}\n- Dernier calcul: {}"
}

calculations_history = []

# -------------------- Routes --------------------
@app.route('/')
def home():
    return "Le bot fonctionne correctement !"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')

        if text in ['/start', '🔙 Retour']:
            send_message(chat_id, TEXTS['welcome'], get_main_keyboard())
            user_states[chat_id] = {'step': 0}

        elif text in ['/help', 'ℹ️ Aide']:
            send_message(chat_id, TEXTS['help_text'], get_main_keyboard(), parse_mode='Markdown')

        elif text in ['/calc', '🔢 Réticulocytes']:
            send_message(chat_id, TEXTS['reti_fields'], get_numeric_keyboard())
            user_states[chat_id] = {'step': 50, 'type': 'reti', 'reti_counts': [], 'rbc_counts': [], 'nb_champs': None}

        elif text in ['/plaquettes', '🩸 Plaquettes']:
            send_message(chat_id, TEXTS['plaq_fields'], get_numeric_keyboard())
            user_states[chat_id] = {'step': 100, 'type': 'plaq', 'plaq_counts': [], 'rbc_counts': [], 'gr_auto': None, 'nb_champs': None}

        elif text in ['/dilution', '🧪 Dilution']:
            send_message(chat_id, TEXTS['dilution_prompt'], get_dilution_keyboard())
            user_states[chat_id] = {'step': 400, 'type': 'dilution'}

        elif text == '🔍 DeepSeek':
            prompt_text = "Analyse complète pour l'échantillon fourni"
            result = query_deepseek(prompt_text)
            send_message(chat_id, f"Résultat DeepSeek:\n{result}", get_main_keyboard())

        elif text.lower() in ['annuler', 'cancel', 'إلغاء']:
            send_message(chat_id, TEXTS['cancel'], get_main_keyboard())
            user_states[chat_id] = {'step': 0}

        elif chat_id in user_states:
            handle_input(chat_id, text)
    return jsonify({'status': 'ok'})

# -------------------- Gestion inputs --------------------
def handle_input(chat_id, text):
    state = user_states[chat_id]
    try:
        if state.get('type') != 'dilution':
            value = float(text) if '.' in text else int(text)
            if value < 0:
                send_message(chat_id, TEXTS['invalid_number'], get_numeric_keyboard())
                return
        else:
            value = text

        if state.get('type') == 'reti':
            handle_reti(chat_id, value)
        elif state.get('type') == 'plaq':
            handle_plaquettes(chat_id, value)
        elif state.get('type') == 'dilution':
            handle_dilution(chat_id, value)
    except ValueError:
        send_message(chat_id, TEXTS['invalid_number'], get_numeric_keyboard())

# -------------------- Fonctions Réticulocytes / Plaquettes / Dilution --------------------
# ... يمكن إضافة نفس الدوال handle_reti, handle_plaquettes, handle_dilution كما في الكود الأصلي
# بدون تغيير، مع إزالة كل النصوص غير الفرنسية

# -------------------- Envoi messages --------------------
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
