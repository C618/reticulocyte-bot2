from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# États des utilisateurs
user_states = {}

@app.route('/')
def home():
    return "Le bot fonctionne correctement !"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        
        if text == '/start':
            send_welcome(chat_id)
            user_states[chat_id] = {'step': 0}
        
        elif text == '/calc':
            send_message(chat_id, "🔢 Combien de champs voulez-vous analyser pour les réticulocytes ?")
            user_states[chat_id] = {'step': 50, 'type': 'reti', 'reti_counts': [], 'rbc_counts': [], 'nb_champs': None}
        
        elif text == '/plaquettes':
            send_message(chat_id, "🩸 Combien de champs voulez-vous analyser pour les plaquettes ?")
            user_states[chat_id] = {'step': 100, 'type': 'plaq', 'plaq_counts': [], 'rbc_counts': [], 'gr_auto': None, 'nb_champs': None}
        
        elif chat_id in user_states:
            handle_user_input(chat_id, text)
    
    return jsonify({'status': 'ok'})

# -------------------- Fonctions Utiles --------------------

def handle_user_input(chat_id, text):
    state = user_states[chat_id]

    # Vérifier si c'est un entier
    try:
        value = int(text)
        if value < 0:
            send_message(chat_id, "⚠️ Veuillez entrer un nombre positif uniquement.")
            return
    except ValueError:
        send_message(chat_id, "⚠️ Veuillez entrer un nombre entier.")
        return

    # ---------- Partie réticulocytes ----------
    if state.get('type') == 'reti':
        handle_reti(chat_id, value)

    # ---------- Partie plaquettes ----------
    if state.get('type') == 'plaq':
        handle_plaquettes(chat_id, value)

def handle_reti(chat_id, value):
    state = user_states[chat_id]

    # Choix du nombre de champs
    if state['step'] == 50:
        state['nb_champs'] = value
        send_message(chat_id, f"🔢 Entrez le nombre de réticulocytes dans le Champ 1 :")
        state['step'] = 51
        return

    # Collecte des réticulocytes
    if 51 <= state['step'] < 51 + state['nb_champs']:
        state['reti_counts'].append(value)
        champ_actuel = len(state['reti_counts']) + 1
        if len(state['reti_counts']) < state['nb_champs']:
            send_message(chat_id, f"Entrez le nombre de réticulocytes dans le Champ {champ_actuel} :")
            state['step'] += 1
        else:
            send_message(chat_id, "👉 Maintenant, entrez le nombre de globules rouges dans le quart de Champ 1 :")
            state['step'] = 200  # étape GR
        return

    # Collecte des GR (3 champs en quarts)
    if 200 <= state['step'] <= 202:
        state['rbc_counts'].append(value)
        if state['step'] < 202:
            champ = state['step'] - 199
            send_message(chat_id, f"Entrez le nombre de globules rouges dans le quart de Champ {champ + 1} :")
            state['step'] += 1
        else:
            # Calcul final
            reti_total = sum(state['reti_counts'])
            rbc1 = state['rbc_counts'][0] * 4
            rbc2 = state['rbc_counts'][1] * 4
            rbc3 = state['rbc_counts'][2] * 4
            avg_rbc = (rbc1 + rbc2 + rbc3) / 3
            rbc_total = avg_rbc * state['nb_champs']  # multiplie par le nb de champs
            result = (reti_total / rbc_total) * 100
            message = f"--- Résultat Réticulocytes ---\n"
            message += f"Total des réticulocytes = {reti_total}\n"
            message += f"Moyenne des globules rouges (×{state['nb_champs']}) = {rbc_total:.2f}\n"
            message += f"Taux de réticulocytes = {result:.2f} %"
            send_message(chat_id, message)
            send_welcome(chat_id)
            user_states[chat_id] = {'step': 0}

def handle_plaquettes(chat_id, value):
    state = user_states[chat_id]

    # Étape choix du nombre de champs
    if state['step'] == 100:
        state['nb_champs'] = value
        send_message(chat_id, f"👉 Entrez le nombre de plaquettes dans le Champ 1 :")
        state['step'] = 101
        return
    
    # Collecte des plaquettes
    if 101 <= state['step'] < 101 + state['nb_champs']:
        state['plaq_counts'].append(value)
        champ_actuel = len(state['plaq_counts']) + 1
        if len(state['plaq_counts']) < state['nb_champs']:
            send_message(chat_id, f"Entrez le nombre de plaquettes dans le Champ {champ_actuel} :")
            state['step'] += 1
        else:
            send_message(chat_id, "👉 Maintenant, entrez le nombre de globules rouges dans le quart de Champ 1 :")
            state['step'] = 300  # étape GR
        return
    
    # Collecte des GR (3 champs en quarts)
    if 300 <= state['step'] <= 302:
        state['rbc_counts'].append(value)
        if state['step'] < 302:
            champ = state['step'] - 299
            send_message(chat_id, f"Entrez le nombre de globules rouges dans le quart de Champ {champ + 1} :")
            state['step'] += 1
        else:
            send_message(chat_id, "⚙️ Enfin, entrez le nombre de globules rouges auto (machine) :")
            state['step'] = 303
        return
    
    # GR auto
    if state['step'] == 303:
        state['gr_auto'] = value
        plaq_moy = sum(state['plaq_counts']) / len(state['plaq_counts'])
        rbc1 = state['rbc_counts'][0] * 4
        rbc2 = state['rbc_counts'][1] * 4
        rbc3 = state['rbc_counts'][2] * 4
        avg_rbc = (rbc1 + rbc2 + rbc3) / 3
        result = (state['gr_auto'] * plaq_moy) / avg_rbc
        
        message = f"--- Résultat Plaquettes ---\n"
        message += f"Moyenne des plaquettes ({state['nb_champs']} champs) = {plaq_moy:.2f}\n"
        message += f"Moyenne des GR = {avg_rbc:.2f}\n"
        message += f"GR auto = {state['gr_auto']}\n"
        message += f"👉 Résultat final = {result:.2f}"
        send_message(chat_id, message)
        send_welcome(chat_id)
        user_states[chat_id] = {'step': 0}

# Message de bienvenue
def send_welcome(chat_id):
    send_message(chat_id, "👋 !\nTapez /calc pour calculer le taux de réticulocytes.\nTapez /plaquettes pour calculer les plaquettes.")

# Envoi des messages
def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, json=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

