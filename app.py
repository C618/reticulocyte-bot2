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
    return "Le bot de calcul du taux de réticulocytes fonctionne correctement !"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        
        if text == '/start':
            send_message(chat_id, "Bonjour ! Je suis un bot pour calculer le taux de réticulocytes. Tapez /calc pour commencer le calcul.")
            user_states[chat_id] = {'step': 0, 'reti_counts': [], 'rbc_counts': []}
        elif text == '/calc':
            send_message(chat_id, "Commençons le processus de calcul. Entrez le nombre de réticulocytes dans chaque champ (total 10).")
            send_message(chat_id, "Entrez le nombre de réticulocytes dans le Champ 1 :")
            user_states[chat_id] = {'step': 1, 'reti_counts': [], 'rbc_counts': []}
        elif chat_id in user_states:
            handle_user_input(chat_id, text)
    
    return jsonify({'status': 'ok'})

def handle_user_input(chat_id, text):
    state = user_states[chat_id]
    
    try:
        value = int(text)
        if value < 0:
            send_message(chat_id, "⚠️ Veuillez entrer un nombre positif uniquement.")
            return
    except ValueError:
        send_message(chat_id, "⚠️ Veuillez entrer un nombre entier.")
        return
    
    if state['step'] <= 10:
        # Collecter les valeurs des réticulocytes
        state['reti_counts'].append(value)
        
        if state['step'] < 10:
            send_message(chat_id, f"Entrez le nombre de réticulocytes dans le Champ {state['step'] + 1} :")
            state['step'] += 1
        else:
            send_message(chat_id, "Toutes les valeurs de réticulocytes ont été collectées. Maintenant, entrez le nombre de globules rouges dans le quart de Champ 1 :")
            state['step'] = 11
    elif state['step'] <= 13:
        # Collecter les valeurs des globules rouges
        state['rbc_counts'].append(value)
        
        if state['step'] < 13:
            send_message(chat_id, f"Entrez le nombre de globules rouges dans le quart de Champ {state['step'] - 10} :")
            state['step'] += 1
        else:
            # Calculer le résultat
            reti_total = sum(state['reti_counts'])
            
            rbc1 = state['rbc_counts'][0] * 4
            rbc2 = state['rbc_counts'][1] * 4
            rbc3 = state['rbc_counts'][2] * 4
            
            avg_rbc = (rbc1 + rbc2 + rbc3) / 3
            rbc_total = avg_rbc * 10
            
            result = (reti_total / rbc_total) * 100
            
            # Envoyer le résultat
            message = f"--- Résultat ---\n"
            message += f"Total des réticulocytes = {reti_total}\n"
            message += f"Moyenne des globules rouges (×10) = {rbc_total:.2f}\n"
            message += f"Taux de réticulocytes = {result:.2f} %"
            
            send_message(chat_id, message)
            
            # Réinitialiser l'état
            user_states[chat_id] = {'step': 0, 'reti_counts': [], 'rbc_counts': []}

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, json=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
