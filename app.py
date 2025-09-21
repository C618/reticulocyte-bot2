from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)

# Token du bot Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# DeepSeek API - استخدام متغير بيئة بدلاً من المفتاح المضمن
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-c092b5aecb284089adae770a030c0026')
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"  # URL مصحح

def query_deepseek(prompt: str):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    # بنية payload مصححة لـ DeepSeek API
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
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
            user_states[chat_id] = {'step': 1, 'type': 'reti', 'reti_counts': [], 'rbc_counts': [], 'nb_champs': None}

        elif text in ['/plaquettes', '🩸 Plaquettes']:
            send_message(chat_id, TEXTS['plaq_fields'], get_numeric_keyboard())
            user_states[chat_id] = {'step': 1, 'type': 'plaq', 'plaq_counts': [], 'rbc_counts': [], 'gr_auto': None, 'nb_champs': None}

        elif text in ['/dilution', '🧪 Dilution']:
            send_message(chat_id, TEXTS['dilution_prompt'], get_dilution_keyboard())
            user_states[chat_id] = {'step': 1, 'type': 'dilution'}

        elif text == '🔍 DeepSeek':
            send_message(chat_id, "Veuillez entrer votre question pour DeepSeek:", get_cancel_keyboard())
            user_states[chat_id] = {'step': 1, 'type': 'deepseek'}

        elif text.lower() in ['annuler', 'cancel', 'إلغاء']:
            send_message(chat_id, TEXTS['cancel'], get_main_keyboard())
            if chat_id in user_states:
                user_states[chat_id] = {'step': 0}

        elif chat_id in user_states:
            handle_input(chat_id, text)
        else:
            send_message(chat_id, TEXTS['welcome'], get_main_keyboard())
            user_states[chat_id] = {'step': 0}
            
    return jsonify({'status': 'ok'})

# -------------------- Gestion inputs --------------------
def handle_input(chat_id, text):
    state = user_states.get(chat_id, {'step': 0})
    
    if state.get('type') == 'deepseek':
        result = query_deepseek(text)
        send_message(chat_id, f"Résultat DeepSeek:\n{result}", get_main_keyboard())
        user_states[chat_id] = {'step': 0}
        return
        
    try:
        if state.get('type') != 'dilution' and text not in ['1/2', '1/5', '1/10', '1/20', '1/50', '1/100', '1/200', '1/500', '1/1000']:
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

# -------------------- Fonctions manquantes --------------------
def handle_reti(chat_id, value):
    state = user_states[chat_id]
    
    if state['step'] == 1:  # عدد الحقول
        state['nb_champs'] = value
        state['step'] = 2
        state['current_champ'] = 1
        send_message(chat_id, TEXTS['reti_count'].format(state['current_champ']), get_cancel_keyboard())
    
    elif state['step'] == 2:  # عدد الخلايا الشبكية
        state['reti_counts'].append(value)
        state['step'] = 3
        send_message(chat_id, TEXTS['rbc_quarter'].format(state['current_champ']), get_cancel_keyboard())
    
    elif state['step'] == 3:  # عدد كريات الدم الحمراء
        state['rbc_counts'].append(value * 4)  # تحويل الربع إلى كامل
        state['current_champ'] += 1
        
        if state['current_champ'] > state['nb_champs']:
            # حساب النتائج
            total_reti = sum(state['reti_counts'])
            avg_rbc = sum(state['rbc_counts']) / state['nb_champs']
            rate = (total_reti / (avg_rbc * state['nb_champs'])) * 100
            
            result = TEXTS['result_reti'].format(total_reti, avg_rbc, rate)
            send_message(chat_id, result, get_main_keyboard())
            
            # حفظ في السجل
            calculations_history.append({
                'type': 'reti',
                'timestamp': datetime.now(),
                'result': result
            })
            
            user_states[chat_id] = {'step': 0}
        else:
            state['step'] = 2
            send_message(chat_id, TEXTS['reti_count'].format(state['current_champ']), get_cancel_keyboard())

def handle_plaquettes(chat_id, value):
    state = user_states[chat_id]
    
    if state['step'] == 1:  # عدد الحقول
        state['nb_champs'] = value
        state['step'] = 2
        state['current_champ'] = 1
        send_message(chat_id, TEXTS['plaq_count'].format(state['current_champ']), get_cancel_keyboard())
    
    elif state['step'] == 2:  # عدد الصفائح الدموية
        state['plaq_counts'].append(value)
        state['step'] = 3
        send_message(chat_id, TEXTS['rbc_quarter'].format(state['current_champ']), get_cancel_keyboard())
    
    elif state['step'] == 3:  # عدد كريات الدم الحمراء
        state['rbc_counts'].append(value * 4)  # تحويل الربع إلى كامل
        state['current_champ'] += 1
        
        if state['current_champ'] > state['nb_champs']:
            state['step'] = 4
            send_message(chat_id, TEXTS['gr_auto'], get_cancel_keyboard())
        else:
            state['step'] = 2
            send_message(chat_id, TEXTS['plaq_count'].format(state['current_champ']), get_cancel_keyboard())
    
    elif state['step'] == 4:  # عدد كريات الدم الحمراء التلقائي
        state['gr_auto'] = value
        
        # حساب النتائج
        avg_plaq = sum(state['plaq_counts']) / state['nb_champs']
        avg_rbc = sum(state['rbc_counts']) / state['nb_champs']
        result_value = (avg_plaq * state['gr_auto']) / avg_rbc
        
        result = TEXTS['result_plaq'].format(avg_plaq, avg_rbc, state['gr_auto'], result_value)
        send_message(chat_id, result, get_main_keyboard())
        
        # حفظ في السجل
        calculations_history.append({
            'type': 'plaq',
            'timestamp': datetime.now(),
            'result': result
        })
        
        user_states[chat_id] = {'step': 0}

def handle_dilution(chat_id, value):
    state = user_states[chat_id]
    
    if state['step'] == 1:  # نسبة التخفيف
        if value in ['1/2', '1/5', '1/10', '1/20', '1/50', '1/100', '1/200', '1/500', '1/1000']:
            parts = value.split('/')
            state['dilution_num'] = int(parts[0])
            state['dilution_den'] = int(parts[1])
            state['step'] = 2
            send_message(chat_id, TEXTS['quantity_prompt'], get_cancel_keyboard())
        else:
            send_message(chat_id, "Format de dilution invalide. Utilisez le format 1/10, 1/100, etc.", get_dilution_keyboard())
    
    elif state['step'] == 2:  # الكمية الإجمالية
        total_quantity = float(value)
        substance = total_quantity / state['dilution_den']
        diluant = total_quantity - substance
        
        result1 = TEXTS['dilution_result'].format(state['dilution_num'], state['dilution_den'], state['dilution_num'], state['dilution_den'] - state['dilution_num'])
        result2 = TEXTS['exact_volumes'].format(total_quantity, substance, diluant)
        
        send_message(chat_id, f"{result1}\n\n{result2}", get_main_keyboard())
        
        # حفظ في السجل
        calculations_history.append({
            'type': 'dilution',
            'timestamp': datetime.now(),
            'result': f"{result1} | {result2}"
        })
        
        user_states[chat_id] = {'step': 0}

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
