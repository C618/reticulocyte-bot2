from flask import Flask, request, jsonify
import requests
import os
import json
import re
from datetime import datetime
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}
user_languages = {}
alarms = {}  # قاموس لتخزين المنبهات

# تفعيل التسجيل للأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# إنشاء مجدول الخلفية للمنبهات
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Paris'))
scheduler.start()

# Définition des claviers
def get_main_keyboard():
    return {
        'keyboard': [
            ['🔢 Réticulocytes', '🩸 Plaquettes'],
            ['🧪 Dilution', '⏰ Alarme'],
            ['ℹ️ Aide', '⚙️ Paramètres']
        ],
        'resize_keyboard': True
    }

def get_alarm_keyboard():
    return {
        'keyboard': [
            ['⏰ Régler une alarme', '📋 Mes alarmes'],
            ['❌ Annuler alarme', '🔙 Retour']
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
        'keyboard': [
            ['🔙 Retour', '🗑️ Effacer historique'],
            ['📊 Statistiques']
        ],
        'resize_keyboard': True
    }

# Textes en français uniquement
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
⏰ *Alarme* : Gestion des alarmes
⚙️ *Paramètres* : Configuration du bot

*Commandes rapides* :
/start - Démarrer le bot
/help - Afficher l'aide
/calc - Calcul réticulocytes
/plaquettes - Calcul plaquettes
/dilution - Préparation dilution
/alarme - Gestion des alarmes""",
    'settings': "⚙️ *Paramètres* :\n- Historique: Activé",
    'stats': "📊 *Statistiques* :\n- Calculs effectués: {}\n- Dernier calcul: {}",
    'alarm_prompt': "⏰ Entrez l'heure pour l'alarme (format HH:MM) :",
    'alarm_set': "✅ Alarme réglée pour {}",
    'alarm_list': "📋 Vos alarmes :\n{}",
    'no_alarms': "📋 Vous n'avez aucune alarme configurée.",
    'alarm_cancel_prompt': "Entrez l'heure de l'alarme à annuler :",
    'alarm_cancelled': "✅ Alarme pour {} a été annulée.",
    'alarm_not_found': "❌ Aucune alarme trouvée pour {}."
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

        # Gestion des commandes textuelles et boutons
        if text == '/start' or text == '🔙 Retour':
            send_welcome_start(chat_id)
            user_states[chat_id] = {'step': 0}
        
        elif text == '/help' or text == 'ℹ️ Aide':
            send_message(chat_id, TEXTS['help_text'], get_main_keyboard(), parse_mode='Markdown')
        
        elif text == '/calc' or text == '🔢 Réticulocytes':
            send_message(chat_id, TEXTS['reti_fields'], get_numeric_keyboard())
            user_states[chat_id] = {'step': 50, 'type': 'reti', 'reti_counts': [], 'rbc_counts': [], 'nb_champs': None}
        
        elif text == '/plaquettes' or text == '🩸 Plaquettes':
            send_message(chat_id, TEXTS['plaq_fields'], get_numeric_keyboard())
            user_states[chat_id] = {'step': 100, 'type': 'plaq', 'plaq_counts': [], 'rbc_counts': [], 'gr_auto': None, 'nb_champs': None}
        
        elif text == '/dilution' or text == '🧪 Dilution':
            send_message(chat_id, TEXTS['dilution_prompt'], get_dilution_keyboard())
            user_states[chat_id] = {'step': 400, 'type': 'dilution'}
        
        elif text == '/alarme' or text == '⏰ Alarme':
            send_message(chat_id, "Gestion des alarmes:", get_alarm_keyboard())
        
        elif text == '⏰ Régler une alarme':
            send_message(chat_id, TEXTS['alarm_prompt'], get_cancel_keyboard())
            user_states[chat_id] = {'step': 500, 'type': 'alarm_set'}
        
        elif text == '📋 Mes alarmes':
            if chat_id in alarms and alarms[chat_id]:
                alarm_list = "\n".join(alarms[chat_id])
                send_message(chat_id, TEXTS['alarm_list'].format(alarm_list), get_alarm_keyboard())
            else:
                send_message(chat_id, TEXTS['no_alarms'], get_alarm_keyboard())
        
        elif text == '❌ Annuler alarme':
            if chat_id in alarms and alarms[chat_id]:
                alarm_list = "\n".join([f"{i+1}. {t}" for i, t in enumerate(alarms[chat_id])])
                send_message(chat_id, f"Choisissez l'alarme à annuler:\n{alarm_list}", get_cancel_keyboard())
                user_states[chat_id] = {'step': 600, 'type': 'alarm_cancel'}
            else:
                send_message(chat_id, TEXTS['no_alarms'], get_alarm_keyboard())
        
        elif text == '⚙️ Paramètres':
            send_message(chat_id, TEXTS['settings'], get_settings_keyboard(), parse_mode='Markdown')
        
        elif text == '📊 Statistiques':
            stats_text = TEXTS['stats'].format(len(calculations_history), 
                                               calculations_history[-1]['type'] if calculations_history else 'Aucun')
            send_message(chat_id, stats_text, get_main_keyboard(), parse_mode='Markdown')
        
        elif text.lower() == 'annuler':
            send_message(chat_id, TEXTS['cancel'], get_main_keyboard())
            user_states[chat_id] = {'step': 0}
        
        elif chat_id in user_states:
            handle_input(chat_id, text)
    
    return jsonify({'status': 'ok'})

# -------------------- Gestion des inputs --------------------

def handle_input(chat_id, text):
    state = user_states[chat_id]

    try:
        if state.get('type') == 'alarm_set':
            handle_alarm_set(chat_id, text)
        elif state.get('type') == 'alarm_cancel':
            handle_alarm_cancel(chat_id, text)
        elif state.get('type') != 'dilution':
            value = float(text) if '.' in text else int(text)
            if value < 0:
                send_message(chat_id, TEXTS['invalid_number'], get_numeric_keyboard())
                return
            
            if state.get('type') == 'reti':
                handle_reti(chat_id, value)
            elif state.get('type') == 'plaq':
                handle_plaquettes(chat_id, value)
        elif state.get('type') == 'dilution':
            handle_dilution(chat_id, text)
    
    except ValueError:
        send_message(chat_id, TEXTS['invalid_number'], get_numeric_keyboard())

# -------------------- Gestion des alarmes --------------------

def handle_alarm_set(chat_id, time_str):
    # Validation du format de l'heure
    try:
        alarm_time = datetime.strptime(time_str, "%H:%M").time()
        
        # Sauvegarde de l'alarme
        if chat_id not in alarms:
            alarms[chat_id] = []
        
        alarms[chat_id].append(time_str)
        
        # Programmation de l'alarme
        scheduler.add_job(
            send_alarm_notification,
            trigger=CronTrigger(hour=alarm_time.hour, minute=alarm_time.minute),
            args=[chat_id, time_str],
            id=f"alarm_{chat_id}_{time_str}",
            replace_existing=True
        )
        
        send_message(chat_id, TEXTS['alarm_set'].format(time_str), get_alarm_keyboard())
        user_states[chat_id] = {'step': 0}
    
    except ValueError:
        send_message(chat_id, "Format d'heure invalide. Utilisez HH:MM", get_cancel_keyboard())

def handle_alarm_cancel(chat_id, text):
    try:
        index = int(text) - 1
        if chat_id in alarms and 0 <= index < len(alarms[chat_id]):
            time_str = alarms[chat_id][index]
            
            # Suppression de l'alarme
            del alarms[chat_id][index]
            if not alarms[chat_id]:
                del alarms[chat_id]
            
            # Annulation de la tâche planifiée
            job_id = f"alarm_{chat_id}_{time_str}"
            scheduler.remove_job(job_id)
            
            send_message(chat_id, TEXTS['alarm_cancelled'].format(time_str), get_alarm_keyboard())
        else:
            send_message(chat_id, TEXTS['alarm_not_found'].format(text), get_alarm_keyboard())
        
        user_states[chat_id] = {'step': 0}
    
    except ValueError:
        send_message(chat_id, "Veuillez entrer un numéro valide.", get_alarm_keyboard())

def send_alarm_notification(chat_id, time_str):
    send_message(chat_id, f"⏰ Réveil! Il est {time_str}", get_main_keyboard())
    
    # Suppression de l'alarme après déclenchement
    if chat_id in alarms and time_str in alarms[chat_id]:
        alarms[chat_id].remove(time_str)
        if not alarms[chat_id]:
            del alarms[chat_id]

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
            
            # Enregistrer dans l'historique
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
        result = (state['gr_auto'] * plaq_moy) / avg_rbc
        
        # Enregistrer dans l'historique
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
                
                # Demander pour les volumes exacts
                send_message(chat_id, TEXTS['quantity_prompt'], get_cancel_keyboard())
                state['step'] = 401
                state['last_dilution'] = text
            else:
                send_message(chat_id, TEXTS['invalid_number'], get_dilution_keyboard())
        
        elif state['step'] == 401:
            if text.lower() == 'annuler':
                send_welcome_end(chat_id)
                user_states[chat_id] = {'step': 0}
            else:
                quantite = float(text)
                numer, denom = map(int, state.get('last_dilution', '1/2').split('/'))
                part_substance = (numer/denom) * quantite
                part_diluant = quantite - part_substance
                
                message = TEXTS['exact_volumes'].format(quantite, part_substance, part_diluant)
                send_message(chat_id, message, get_main_keyboard())
                
                # Enregistrer dans l'historique
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
    data = {
        "chat_id": chat_id, 
        "text": text
    }
    
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    
    if parse_mode:
        data["parse_mode"] = parse_mode
    
    try:
        requests.post(url, json=data, timeout=10)
    except requests.exceptions.RequestException:
        pass 

def set_webhook():
    """تعيين الويب هوك للبوت"""
    webhook_url = os.environ.get('WEBHOOK_URL') + '/webhook'
    url = f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url)
        print(f"Webhook set: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error setting webhook: {e}")

if __name__ == '__main__':
    # تعيين الويب هوك عند التشغيل
    set_webhook()
    
    # تشغيل التطبيق
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
