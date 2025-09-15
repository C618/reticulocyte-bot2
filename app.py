from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

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
            send_welcome_start(chat_id)
            user_states[chat_id] = {'step': 0}
        elif text == '/calc':
            send_message(chat_id, "🔢 Combien de champs voulez-vous analyser pour les réticulocytes ?")
            user_states[chat_id] = {'step': 50, 'type': 'reti', 'reti_counts': [], 'rbc_counts': [], 'nb_champs': None}
        elif text == '/plaquettes':
            send_message(chat_id, "🩸 Combien de champs voulez-vous analyser pour les plaquettes ?")
            user_states[chat_id] = {'step': 100, 'type': 'plaq', 'plaq_counts': [], 'rbc_counts': [], 'gr_auto': None, 'nb_champs': None}
        elif text == '/dilution':
            send_message(chat_id, "🔹 Entrez la dilution souhaitée (ex: 1/2, 1/10) :")
            user_states[chat_id] = {'step': 400, 'type': 'dilution'}
        elif chat_id in user_states:
            handle_input(chat_id, text)
    return jsonify({'status': 'ok'})

# -------------------- Gestion des inputs --------------------

def handle_input(chat_id, text):
    state = user_states[chat_id]

    # Vérifier si c'est un entier sauf pour dilution
    if state.get('type') != 'dilution':
        try:
            value = int(text)
            if value < 0:
                send_message(chat_id, "⚠️ Veuillez entrer un nombre positif uniquement.")
                return
        except ValueError:
            send_message(chat_id, "⚠️ Veuillez entrer un nombre entier.")
            return
    else:
        value = text  # pour dilution

    if state.get('type') == 'reti':
        handle_reti(chat_id, value)
    elif state.get('type') == 'plaq':
        handle_plaquettes(chat_id, value)
    elif state.get('type') == 'dilution':
        handle_dilution(chat_id, value)

# -------------------- Réticulocytes --------------------

def handle_reti(chat_id, value):
    state = user_states[chat_id]

    if state['step'] == 50:
        state['nb_champs'] = value
        send_message(chat_id, f"🔢 Entrez le nombre de réticulocytes dans le Champ 1 :")
        state['step'] = 51
        return

    if 51 <= state['step'] < 51 + state['nb_champs']:
        state['reti_counts'].append(value)
        champ_actuel = len(state['reti_counts']) + 1
        if len(state['reti_counts']) < state['nb_champs']:
            send_message(chat_id, f"Entrez le nombre de réticulocytes dans le Champ {champ_actuel} :")
            state['step'] += 1
        else:
            send_message(chat_id, "👉 Maintenant, entrez le nombre de globules rouges dans le quart de Champ 1 :")
            state['step'] = 200
        return

    if 200 <= state['step'] <= 202:
        state['rbc_counts'].append(value)
        if state['step'] < 202:
            champ = state['step'] - 199
            send_message(chat_id, f"Entrez le nombre de globules rouges dans le quart de Champ {champ + 1} :")
            state['step'] += 1
        else:
            reti_total = sum(state['reti_counts'])
            rbc_total = sum([x*4 for x in state['rbc_counts']]) / 3 * state['nb_champs']
            taux = (reti_total / rbc_total) * 100
            message = f"--- Résultat Réticulocytes ---\n"
            message += f"Total des réticulocytes = {reti_total}\n"
            message += f"Moyenne des globules rouges (×{state['nb_champs']}) = {rbc_total:.2f}\n"
            message += f"Taux de réticulocytes = {taux:.2f} %"
            send_message(chat_id, message)
            send_welcome_end(chat_id)
            user_states[chat_id] = {'step': 0}

# -------------------- Plaquettes --------------------

def handle_plaquettes(chat_id, value):
    state = user_states[chat_id]

    if state['step'] == 100:
        state['nb_champs'] = value
        send_message(chat_id, f"👉 Entrez le nombre de plaquettes dans le Champ 1 :")
        state['step'] = 101
        return

    if 101 <= state['step'] < 101 + state['nb_champs']:
        state['plaq_counts'].append(value)
        champ_actuel = len(state['plaq_counts']) + 1
        if len(state['plaq_counts']) < state['nb_champs']:
            send_message(chat_id, f"Entrez le nombre de plaquettes dans le Champ {champ_actuel} :")
            state['step'] += 1
        else:
            send_message(chat_id, "👉 Maintenant, entrez le nombre de globules rouges dans le quart de Champ 1 :")
            state['step'] = 300
        return

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

    if state['step'] == 303:
        state['gr_auto'] = value
        plaq_moy = sum(state['plaq_counts']) / state['nb_champs']
        avg_rbc = sum([x*4 for x in state['rbc_counts']]) / 3
        result = (state['gr_auto'] * plaq_moy) / avg_rbc
        message = f"--- Résultat Plaquettes ---\n"
        message += f"Moyenne des plaquettes ({state['nb_champs']} champs) = {plaq_moy:.2f}\n"
        message += f"Moyenne des GR = {avg_rbc:.2f}\n"
        message += f"GR auto = {state['gr_auto']}\n"
        message += f"👉 Résultat final = {result:.2f}"
        send_message(chat_id, message)
        send_welcome_end(chat_id)
        user_states[chat_id] = {'step': 0}

# -------------------- Dilution --------------------

def handle_dilution(chat_id, text):
    try:
        if '/' in text:
            numer, denom = map(int, text.split('/'))
            if numer <= 0 or denom <= 0 or numer > denom:
                raise ValueError
            message = f"Pour préparer une dilution {numer}/{denom} :\n"
            message += f"- Prenez {numer} partie(s) de la substance\n"
            message += f"- Ajoutez {denom - numer} partie(s) de diluant"
            send_message(chat_id, message)
            # Option pour entrer quantité
            send_message(chat_id, "Si vous voulez, entrez la quantité totale pour calculer les volumes exacts, ou tapez /skip pour ignorer :")
            user_states[chat_id]['step'] = 401
        elif text == '/skip' and user_states[chat_id]['step'] == 401:
            send_welcome_end(chat_id)
            user_states[chat_id] = {'step': 0}
        elif user_states[chat_id]['step'] == 401:
            quantite = float(text)
            numer, denom = map(int, user_states[chat_id].get('last_dilution', '1/2').split('/'))
            part_substance = (numer/denom) * quantite
            part_diluant = quantite - part_substance
            message = f"Pour {quantite} unité(s) totale(s) :\n- Substance : {part_substance}\n- Diluant : {part_diluant}"
            send_message(chat_id, message)
            send_welcome_end(chat_id)
            user_states[chat_id] = {'step': 0}
        else:
            send_message(chat_id, "⚠️ Format incorrect. Utilisez le format 1/2, 1/10, etc.")
    except:
        send_message(chat_id, "⚠️ Format incorrect. Utilisez le format 1/2, 1/10, etc.")
    finally:
        if 'last_dilution' not in user_states[chat_id]:
            user_states[chat_id]['last_dilution'] = text

# -------------------- Messages --------------------

def send_welcome_start(chat_id):
    send_message(chat_id,
                 "👋 Bonjour ! Je suis votre bot pour le calcul des réticulocytes, plaquettes et dilutions.\n"
                 "🔹 Tapez /calc pour calculer le taux de réticulocytes\n"
                 "🔹 Tapez /plaquettes pour calculer les plaquettes\n"
                 "🔹 Tapez /dilution pour préparer une dilution")

def send_welcome_end(chat_id):
    send_message(chat_id,
                 "✅ Calcul terminé !\n"
                 "👋 Vous voulez essayer un autre calcul ?\n"
                 "🔹 /calc → Taux de réticulocytes\n"
                 "🔹 /plaquettes → Plaquettes\n"
                 "🔹 /dilution → Dilution")

# -------------------- Envoi des messages --------------------

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, json=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
