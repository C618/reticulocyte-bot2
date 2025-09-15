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
            send_message(chat_id, "👋 Bonjour !\nTapez /calc pour calculer le taux de réticulocytes.\nTapez /plaquettes pour calculer les plaquettes.")
            user_states[chat_id] = {'step': 0}
        
        elif text == '/calc':
            send_message(chat_id, "🔢 Entrez le nombre de réticulocytes dans le Champ 1 :")
            user_states[chat_id] = {'step': 1, 'reti_counts': [], 'rbc_counts': []}
        
        elif text == '/plaquettes':
            send_message(chat_id, "🩸 Combien de champs voulez-vous analyser pour les plaquettes ?")
            user_states[chat_id] = {'step': 100, 'plaq_counts': [], 'rbc_counts': [], 'gr_auto': None, 'nb_champs': None}
        
        elif chat_id in user_states:
            handle_user_input(chat_id, text)
    
    return jsonify({'status': 'ok'})

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
    
    # ---------- Partie Réticulocytes ----------
    if 'reti_counts' in state:
        if state['step'] <= 10:
            state['reti_counts'].append(value)
            if state['step'] < 10:
                send_message(chat_id, f"Entrez le nombre de réticulocytes dans le Champ {state['step'] + 1} :")
                state['step'] += 1
            else:
                send_message(chat_id, "👉 Maintenant, entrez le nombre de globules rouges dans le quart de Champ 1 :")
                state['step'] = 11
        elif state['step'] <= 13:
            state['rbc_counts'].append(value)
            if state['step'] < 13:
                send_message(chat_id, f"Entrez le nombre de globules rouges dans le quart de Champ {state['step'] - 10} :")
                state['step'] += 1
            else:
                reti_total = sum(state['reti_counts'])
                rbc1 = state['rbc_counts'][0] * 4
                rbc2 = state['rbc_counts'][1] * 4
                rbc3 = state['rbc_counts'][2] * 4
                avg_rbc = (rbc1 + rbc2 + rbc3) / 3
                rbc_total = avg_rbc * 10
                result = (reti_total / rbc_total) * 100
                message = f"--- Résultat Réticulocytes ---\n"
                message += f"Total des réticulocytes = {reti_total}\n"
                message += f"Moyenne des globules rouges (×10) = {rbc_total:.2f}\n"
                message += f"Taux de réticulocytes = {result:.2f} %"
                send_message(chat_id, message)
                user_states[chat_id] = {'step': 0}
    
    # ---------- Partie Plaquettes (Flexible Champs) ----------
    if 'plaq_counts' in state:
        # Étape choix du nombre de champs
        if state['step'] == 100:
            state['nb_champs'] = value
            send_message(chat_id, f"👉 Entrez le nombre de plaquettes dans le Champ 1 :")
            state['step'] = 101
        
        # Collecte des plaquettes
        elif 101 <= state['step'] < 101 + state['nb_champs']:
            state['plaq_counts'].append(value)
            champ_actuel = len(state['plaq_counts']) + 1
            if len(state['plaq_counts']) < state['nb_champs']:
                send_message(chat_id, f"Entrez le nombre de plaquettes dans le Champ {champ_actuel} :")
                state['step'] += 1
            else:
                send_message(chat_id, "👉 Maintenant, entrez le nombre de globules rouges dans le quart de Champ 1 :")
                state['step'] = 200
        
        # Collecte des GR (3 champs en quarts)
        elif 200 <= state['step'] <= 202:
            state['rbc_counts'].append(value)
            if state['step'] < 202:
                champ = state['step'] - 199
                send_message(chat_id, f"Entrez le nombre de globules rouges dans le quart de Champ {champ + 1} :")
                state['step'] += 1
            else:
                send_message(chat_id, "⚙️ Enfin, entrez le nombre de globules rouges auto (machine) :")
                state['step'] = 203
        
        # GR auto
        elif state['step'] == 203:
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
            user_states[chat_id] = {'step': 0}

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, json=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
