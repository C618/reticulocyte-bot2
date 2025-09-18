from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}

# -------------------- Claviers --------------------

def get_main_keyboard():
    return {
        'keyboard': [
            ['🔢 Réticulocytes', '🩸 Plaquettes'],
            ['🧪 Dilution', '⚙️ Paramètres'],
            ['ℹ️ Aide']
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
    return {
        'keyboard': [['Annuler']],
        'resize_keyboard': True
    }

def get_settings_keyboard():
    return {
        'keyboard': [['🔙 Retour'], ['🗑️ Effacer historique'], ['📊 Statistiques']],
        'resize_keyboard': True
    }

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

*Commandes rapides* :  
/start - Démarrer le bot  
/help - Afficher l'aide  
/calc - Calcul réticulocytes  
/plaquettes - Calcul plaquettes  
/dilution - Préparation dilution""",
    'settings': "⚙️ *Paramètres* :\n- Langue: Français\n- Historique: Activé",
    'stats': "📊 *Statistiques* :\n- Calculs effectués: {}\n- Dernier calcul: {}"
}

# Statistiques
calculations_history = []

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
            send_welcome_start(chat_id)
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

        elif text in ['⚙️ Paramètres']:
            send_message(chat_id, TEXTS['settings'], get_settings_keyboard(), parse_mode='Markdown')

        elif text in ['📊 Statistiques']:
            stats_text = TEXTS['stats'].format(len(calculations_history), 
                                               calculations_history[-1]['type'] if calculations_history else 'None')
            send_message(chat_id, stats_text, get_main_keyboard(), parse_mode='Markdown')

        elif text.lower() in ['annuler']:
            send_message(chat_id, TEXTS['cancel'], get_main_keyboard())
            user_states[chat_id] = {'step': 0}

        elif chat_id in user_states:
            handle_input(chat_id, text)

    return jsonify({'status': 'ok'})

# -------------------- Gestion des inputs --------------------

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

# -------------------- Réticulocytes --------------------

def handle_reti(chat_id, value):
    state = user_states[chat_id]

    if state['step'] == 50:
        state['nb_champs'] = value
        send_message(chat_id, TEXTS['reti_count'].format(1), get_numeric_keyboard())
        state['step'] = 51
        return

    if 51 <= state['step'] < 51 + state['nb_champs']:
        state['reti_counts'].append(value)
        champ_actuel = len(state['reti_counts'])
        if len(state['reti_counts']) < state['nb_champs']:
            send_message(chat_id, TEXTS['reti_count'].format(champ_actuel + 1), get_numeric_keyboard())
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS['rbc_quarter'].format(1), get_numeric_keyboard())
            state['step'] = 200
        return

    if 200 <= state['step'] <= 202:
        state['rbc_counts'].append(value)
        if state['step'] < 202:
            champ = state['step'] - 199
            send_message(chat_id, TEXTS['rbc_quarter'].format(champ + 1), get_numeric_keyboard())
            state['step'] += 1
        else:
            reti_total = sum(state['reti_counts'])
            rbc_total = sum([x*4 for x in state['rbc_counts']]) / 3 * state['nb_champs']
            taux = (reti_total / rbc_total) * 100

            calculations_history.append({
                'type': 'reticulocytes',
                'result': taux,
                'timestamp': datetime.now().isoformat()
            })

            message = TEXTS['result_reti'].format(reti_total, rbc_total, taux)
            send_message(chat_id, message, get_main_keyboard())
            send_welcome_end(chat_id)
            user_states[chat_id] = {'step': 0}

# -------------------- Plaquettes --------------------

def handle_plaquettes(chat_id, value):
    state = user_states[chat_id]

    if state['step'] == 100:
        state['nb_champs'] = value
        send_message(chat_id, TEXTS['plaq_count'].format(1), get_numeric_keyboard())
        state['step'] = 101
        return

    if 101 <= state['step'] < 101 + state['nb_champs']:
        state['plaq_counts'].append(value)
        champ_actuel = len(state['plaq_counts'])
        if len(state['plaq_counts']) < state['nb_champs']:
            send_message(chat_id, TEXTS['plaq_count'].format(champ_actuel + 1), get_numeric_keyboard())
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS['rbc_quarter'].format(1), get_numeric_keyboard())
            state['step'] = 300
        return

    if 300 <= state['step'] <= 302:
        state['rbc_counts'].append(value)
        if state['step'] < 302:
            champ = state['step'] - 299
            send_message(chat_id, TEXTS['rbc_quarter'].format(champ + 1), get_numeric_keyboard())
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS['gr_auto'], get_numeric_keyboard())
            state['step'] = 303
        return

    if state['step'] == 303:
        state['gr_auto'] = value
        plaq_moy = sum(state['plaq_counts']) / state['nb_champs']
        avg_rbc = sum([x*4 for x in state['rbc_counts']]) / 3

        # ✅ Correction appliquée
        result = (plaq_moy * state['gr_auto']) / avg_rbc

        calculations_history.append({
            'type': 'platelets',
            'result': result,
            'timestamp': datetime.now().isoformat()
        })

        message = TEXTS['result_plaq'].format(plaq_moy, avg_rbc, state['gr_auto'], result)
        send_message(chat_id, message, get_main_keyboard())
        send_welcome_end(chat_id)
        user_states[chat_id] = {'step': 0}

# -------------------- Dilution --------------------

def handle_dilution(chat_id, text):
    state = user_states[chat_id]

    try:
        if state['step'] == 400:
            if '/' in text:
                numer, denom = map(int, text.split('/'))
                if numer <= 0 or denom <= 0 or numer > denom:
                    raise ValueError

                message = TEXTS['dilution_result'].format(numer, denom, numer, denom - numer)
                send_message(chat_id, message, get_main_keyboard())

                send_message(chat_id, TEXTS['quantity_prompt'], get_cancel_keyboard())
                state['step'] = 401
                state['last_dilution'] = text
            else:
                send_message(chat_id, TEXTS['invalid_number'], get_dilution_keyboard())

        elif state['step'] == 401:
            if text.lower() in ['annuler']:
                send_welcome_end(chat_id)
                user_states[chat_id] = {'step': 0}
            else:
                quantite = float(text)
                numer, denom = map(int, state.get('last_dilution', '1/2').split('/'))
                part_substance = (numer/denom) * quantite
                part_diluant = quantite - part_substance

                message = TEXTS['exact_volumes'].format(quantite, part_substance, part_diluant)
                send_message(chat_id, message, get_main_keyboard())

                calculations_history.append({
                    'type': 'dilution',
                    'result': f"{numer}/{denom}",
                    'timestamp': datetime.now().isoformat()
                })

                send_welcome_end(chat_id)
                user_states[chat_id] = {'step': 0}

    except (ValueError, AttributeError):
        send_message(chat_id, TEXTS['invalid_number'], get_dilution_keyboard())

# -------------------- Messages --------------------

def send_welcome_start(chat_id):
    send_message(chat_id, TEXTS['welcome'], get_main_keyboard())

def send_welcome_end(chat_id):
    send_message(chat_id, "✅ Calcul terminé !\nChoisissez une autre option :", get_main_keyboard())

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
