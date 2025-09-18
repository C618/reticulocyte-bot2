from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Token Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}
calculations_history = []

@app.route('/')
def home():
    return "Le bot fonctionne correctement !"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if chat_id not in user_states:
            user_states[chat_id] = {"step": 0}

        state = user_states[chat_id]

        if text == "/start":
            state["step"] = 1
            bot_send(chat_id, "👋 Bienvenue ! Suivez les étapes pour calculer les plaquettes.\n\n1️⃣ Entrez le nombre de globules rouges auto (GR) :")

        elif state["step"] == 1:
            try:
                state["gr_auto"] = float(text)
                state["step"] = 2
                bot_send(chat_id, "2️⃣ Entrez le nombre total de plaquettes comptées (au microscope) :")
            except:
                bot_send(chat_id, "⚠️ Veuillez entrer un nombre valide.")

        elif state["step"] == 2:
            try:
                state["plaq_count"] = float(text)
                state["step"] = 3
                state["rbc_counts"] = []
                state["current_rbc"] = 1
                bot_send(chat_id, f"3️⃣ Entrez le nombre de GR dans le carré {state['current_rbc']} :")
            except:
                bot_send(chat_id, "⚠️ Veuillez entrer un nombre valide.")

        elif state["step"] == 3:
            try:
                rbc = int(text)
                state["rbc_counts"].append(rbc)

                if state["current_rbc"] < 3:
                    state["current_rbc"] += 1
                    bot_send(chat_id, f"Entrez le nombre de GR dans le carré {state['current_rbc']} :")
                else:
                    handle_plaquettes(chat_id, state)
                    state["step"] = 0
            except:
                bot_send(chat_id, "⚠️ Veuillez entrer un nombre valide.")

    return jsonify({"status": "ok"})

def bot_send(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

def handle_plaquettes(chat_id, state):
    # Moyenne des GR (×4 pour volume)
    avg_rbc = sum([x * 4 for x in state['rbc_counts']]) / 3

    # Valeurs saisies
    plaq_count = state['plaq_count']
    gr_auto = state['gr_auto']

    # Calcul final
    result = (plaq_count * gr_auto) / avg_rbc

    # Conversion en notation scientifique (a × 10^x)
    mantisse, exposant = "{:.2e}".format(result).split("e")
    mantisse = float(mantisse)
    exposant = int(exposant)
    result_fmt = f"{mantisse} × 10^{exposant} /µL"

    # Message final avec équation
    equation = f"({plaq_count} × {gr_auto}) ÷ {avg_rbc:.2f}"
    bot_send(
        chat_id,
        f"📊 Équation utilisée : {equation}\n✅ Résultat final : {result_fmt}"
    )

    # Enregistrer dans l'historique
    calculations_history.append({
        "type": "plaquettes",
        "plaq_count": plaq_count,
        "gr_auto": gr_auto,
        "avg_rbc": avg_rbc,
        "result": result_fmt,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
