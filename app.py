from flask import Flask,request, jsonify
import requests
import os
import json
import re
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Dictionnaires pour stocker l'état des utilisateurs et les alarmes
user_states = {}
user_languages = {}
user_alarms = {}

# Initialisation du planificateur pour les alarmes
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Paris')) # Ajustez la timezone si nécessaire
scheduler.start()

# Définition des claviers

def get_main_keyboard(lang='fr'):
    keyboards = {
        'fr': {
            'keyboard': [
                ['🔢 Réticulocytes', '🩸 Plaquettes'],
                ['🧪 Dilution', '⏰ Horloge & Alarme'],
                ['⚙️ Paramètres', 'ℹ️ Aide']
            ],
            'resize_keyboard': True
        }
    }
    return keyboards.get(lang, keyboards['fr'])

def get_numeric_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler'}
    return {
        'keyboard': [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10'],
            ['15', '20', '25', '30', '50'],
            [cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_dilution_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler'}
    return {
        'keyboard': [
            ['1/2', '1/5', '1/10'],
            ['1/20', '1/50', '1/100'],
            ['1/200', '1/500', '1/1000'],
            [cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_cancel_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler'}
    return {
        'keyboard': [[cancel_text[lang]]],
        'resize_keyboard': True
    }

def get_language_keyboard():
    return {
        'keyboard': [
            ['🇫🇷 Français', '🔙 Retour']
        ],
        'resize_keyboard': True
    }

def get_settings_keyboard(lang='fr'):
    texts = {
        'fr': ['🔙 Retour', '🗑️ Effacer historique', '📊 Statistiques']
    }
    return {
        'keyboard': [[texts[lang][0]], [texts[lang][1]], [texts[lang][2]]],
        'resize_keyboard': True
    }

def get_clock_keyboard(lang='fr'):
    texts = {
        'fr': ['➕ Ajouter une alarme', '🗑️ Supprimer une alarme', '📜 Mes alarmes', '🔙 Retour']
    }
    return {
        'keyboard': [
            [texts[lang][0]],
            [texts[lang][1]],
            [texts[lang][2]],
            [texts[lang][3]]
        ],
        'resize_keyboard': True
    }

# Textes multilingues

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
        'help_text': """ℹ️ AIDE - Commandes disponibles
🔢 Réticulocytes : Calcul du taux de réticulocytes
🩸Plaquettes : Calcul du nombre de plaquettes
🧪Dilution : Préparation de dilutions
⏰ Horloge & Alarme: Gérer vos alarmes
⚙️Paramètres : Configuration du bot
🔄Langue : Changer la langue
Commandes rapides : /start- Démarrer le bot /help- Afficher l'aide /calc- Calcul réticulocytes /plaquettes- Calcul plaquettes /dilution- Préparation dilution""",
        'settings': "⚙️ Paramètres :\n- Langue: Français\n- Historique: Activé",
        'stats': "📊 Statistiques :\n- Calculs effectués: {}\n- Dernier calcul: {}",
        'clock_menu': "⏰ Bienvenue dans le menu Horloge et Alarme.\nChoisissez une option :",
        'add_alarm_prompt': "➕ Entrez l'heure de l'alarme (ex: 14:30) et un nom (ex: 'réunion'):\n14:30 réunion",
        'alarm_added': "✅ Alarme '{name}' ajoutée pour {time}.",
        'alarm_list': "📜 Vos alarmes actuelles:\n{alarms}",
        'no_alarms': "📜 Vous n'avez pas d'alarmes actives pour le moment.",
        'alarm_trigger': "🔔 **ALARM:** {name}",
        'alarm_deleted': "🗑️ L'alarme '{name}' a été supprimée.",
        'alarm_not_found': "⚠️ Aucune alarme trouvée avec ce nom.",
        'delete_alarm_prompt': "🗑️ Entrez le nom de l'alarme à supprimer:",
        'invalid_alarm_format': "⚠️ Format d'alarme invalide. Veuillez utiliser 'HH:MM nom_alarme'."
    }
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
        lang = user_languages.get(chat_id, 'fr')
        handle_input(chat_id, text, lang)
    return jsonify({"status": "ok"})

# Fonctions d'alarme

def add_alarm(chat_id, time_str, name):
    try:
        # Vérifier le format de l'heure
        if not re.match(r'^\d{2}:\d{2}$', time_str):
            raise ValueError
        
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        
        # Déterminer la prochaine heure de déclenchement
        now = datetime.now()
        run_date = now.replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)
        
        if run_date < now:
            run_date = run_date + pytz.utc.localize(datetime.timedelta(days=1))
        
        # Planifier la tâche d'alarme
        job_id = f"alarm_{chat_id}_{name}"
        scheduler.add_job(
            send_message,
            'date',
            run_date=run_date,
            id=job_id,
            args=[chat_id, TEXTS['fr']['alarm_trigger'].format(name=name), None, 'Markdown']
        )
        
        # Stocker les détails de l'alarme
        if chat_id not in user_alarms:
            user_alarms[chat_id] = {}
        user_alarms[chat_id][name] = {
            'time': time_str,
            'job_id': job_id
        }
        return True
    except (ValueError, KeyError) as e:
        return False

def delete_alarm(chat_id, name):
    if chat_id in user_alarms and name in user_alarms[chat_id]:
        job_id = user_alarms[chat_id][name]['job_id']
        try:
            scheduler.remove_job(job_id)
            del user_alarms[chat_id][name]
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression de la tâche : {e}")
            return False
    return False

# Gestion des inputs

def handle_input(chat_id, text, lang):
    state = user_states.get(chat_id)
    
    if text == '⏰ Horloge & Alarme':
        user_states[chat_id] = 'CLOCK_MENU'
        send_message(chat_id, TEXTS[lang]['clock_menu'], get_clock_keyboard(lang))
        return
    
    if text == '➕ Ajouter une alarme' and state == 'CLOCK_MENU':
        user_states[chat_id] = 'ADD_ALARM_PROMPT'
        send_message(chat_id, TEXTS[lang]['add_alarm_prompt'], get_cancel_keyboard(lang))
        return
    
    if text == '🗑️ Supprimer une alarme' and state == 'CLOCK_MENU':
        user_states[chat_id] = 'DELETE_ALARM_PROMPT'
        send_message(chat_id, TEXTS[lang]['delete_alarm_prompt'], get_cancel_keyboard(lang))
        return
    
    if text == '📜 Mes alarmes' and state == 'CLOCK_MENU':
        alarm_list = user_alarms.get(chat_id, {})
        if alarm_list:
            alarms_text = '\n'.join([f"- **{name}**: {details['time']}" for name, details in alarm_list.items()])
            send_message(chat_id, TEXTS[lang]['alarm_list'].format(alarms=alarms_text), get_clock_keyboard(lang), 'Markdown')
        else:
            send_message(chat_id, TEXTS[lang]['no_alarms'], get_clock_keyboard(lang))
        return

    if state == 'ADD_ALARM_PROMPT':
        match = re.match(r'(\d{2}:\d{2})\s(.+)', text)
        if match:
            time_str, name = match.groups()
            if add_alarm(chat_id, time_str, name):
                send_message(chat_id, TEXTS[lang]['alarm_added'].format(name=name, time=time_str), get_clock_keyboard(lang))
                user_states[chat_id] = 'CLOCK_MENU'
            else:
                send_message(chat_id, TEXTS[lang]['invalid_alarm_format'], get_cancel_keyboard(lang))
        else:
            send_message(chat_id, TEXTS[lang]['invalid_alarm_format'], get_cancel_keyboard(lang))
        return
    
    if state == 'DELETE_ALARM_PROMPT':
        name = text.strip()
        if delete_alarm(chat_id, name):
            send_message(chat_id, TEXTS[lang]['alarm_deleted'].format(name=name), get_clock_keyboard(lang))
        else:
            send_message(chat_id, TEXTS[lang]['alarm_not_found'], get_cancel_keyboard(lang))
        user_states[chat_id] = 'CLOCK_MENU'
        return

    # Gestion des messages de calcul
    if text == '🔢 Réticulocytes' or text == '/calc':
        user_states[chat_id] = 'RETI_FIELDS_PROMPT'
        send_message(chat_id, TEXTS[lang]['reti_fields'], get_numeric_keyboard(lang))
        return
    
    if text == '🩸 Plaquettes' or text == '/plaquettes':
        user_states[chat_id] = 'PLAQ_FIELDS_PROMPT'
        send_message(chat_id, TEXTS[lang]['plaq_fields'], get_numeric_keyboard(lang))
        return
    
    if text == '🧪 Dilution' or text == '/dilution':
        user_states[chat_id] = 'DILUTION_PROMPT'
        send_message(chat_id, TEXTS[lang]['dilution_prompt'], get_dilution_keyboard(lang))
        return

    if text == '⚙️ Paramètres':
        user_states[chat_id] = 'SETTINGS_MENU'
        send_message(chat_id, TEXTS[lang]['settings'], get_settings_keyboard(lang))
        return

    if text == 'ℹ️ Aide' or text == '/help':
        send_message(chat_id, TEXTS[lang]['help_text'], get_main_keyboard(lang))
        return

    if text == '🔄 Langue':
        user_states[chat_id] = 'SELECT_LANGUAGE'
        send_message(chat_id, "Choisissez une langue:", get_language_keyboard())
        return

    if text == '🔙 Retour':
        user_states[chat_id] = 'IDLE'
        send_message(chat_id, TEXTS[lang]['welcome'], get_main_keyboard(lang))
        return

    if text == '🇫🇷 Français':
        user_languages[chat_id] = 'fr'
        user_states[chat_id] = 'IDLE'
        send_message(chat_id, TEXTS['fr']['welcome'], get_main_keyboard('fr'))
        return

    if text == '🗑️ Effacer historique' and state == 'SETTINGS_MENU':
        calculations_history.clear()
        send_message(chat_id, "L'historique des calculs a été effacé.", get_settings_keyboard(lang))
        return

    if text == '📊 Statistiques' and state == 'SETTINGS_MENU':
        stats_text = TEXTS[lang]['stats'].format(len(calculations_history), calculations_history[-1] if calculations_history else 'Aucun')
        send_message(chat_id, stats_text, get_settings_keyboard(lang))
        return

    # Gérer les autres états (calculs)
    if state == 'RETI_FIELDS_PROMPT':
        try:
            num_fields = int(text)
            if num_fields > 0:
                user_states[chat_id] = 'RETI_INPUT_LOOP'
                user_states[chat_id + '_fields'] = num_fields
                user_states[chat_id + '_reti_counts'] = []
                user_states[chat_id + '_rbc_counts'] = []
                user_states[chat_id + '_current_field'] = 1
                send_message(chat_id, TEXTS[lang]['reti_count'].format(1), get_cancel_keyboard(lang))
            else:
                send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))
        except ValueError:
            send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))
        return

    if state == 'RETI_INPUT_LOOP':
        try:
            value = float(text)
            current_field = user_states[chat_id + '_current_field']
            if current_field <= user_states[chat_id + '_fields']:
                user_states[chat_id + '_reti_counts'].append(value)
                send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(current_field), get_cancel_keyboard(lang))
                user_states[chat_id + '_current_field'] += 1
            else:
                user_states[chat_id + '_rbc_counts'].append(value)
                total_reti = sum(user_states[chat_id + '_reti_counts'])
                avg_rbc = (sum(user_states[chat_id + '_rbc_counts']) * 4) / user_states[chat_id + '_fields']
                rate = (total_reti / (1000 * avg_rbc)) * 100
                result_text = TEXTS[lang]['result_reti'].format(total_reti, avg_rbc, rate)
                send_message(chat_id, result_text, get_main_keyboard(lang))
                calculations_history.append({'type': 'reti', 'result': rate, 'timestamp': str(datetime.now())})
                user_states[chat_id] = 'IDLE'
        except ValueError:
            send_message(chat_id, TEXTS[lang]['invalid_number'], get_cancel_keyboard(lang))
        return

    if state == 'PLAQ_FIELDS_PROMPT':
        try:
            num_fields = int(text)
            if num_fields > 0:
                user_states[chat_id] = 'PLAQ_INPUT_LOOP'
                user_states[chat_id + '_fields'] = num_fields
                user_states[chat_id + '_plaq_counts'] = []
                user_states[chat_id + '_gr_auto'] = None
                user_states[chat_id + '_current_field'] = 1
                send_message(chat_id, TEXTS[lang]['plaq_count'].format(1), get_cancel_keyboard(lang))
            else:
                send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))
        except ValueError:
            send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))
        return

    if state == 'PLAQ_INPUT_LOOP':
        try:
            value = float(text)
            if user_states[chat_id + '_gr_auto'] is None:
                user_states[chat_id + '_plaq_counts'].append(value)
                current_field = user_states[chat_id + '_current_field']
                if current_field < user_states[chat_id + '_fields']:
                    user_states[chat_id + '_current_field'] += 1
                    send_message(chat_id, TEXTS[lang]['plaq_count'].format(current_field), get_cancel_keyboard(lang))
                else:
                    user_states[chat_id + '_gr_auto'] = True # Passer à l'étape suivante
                    send_message(chat_id, TEXTS[lang]['gr_auto'], get_cancel_keyboard(lang))
            else:
                gr_auto = float(text)
                avg_plaq = sum(user_states[chat_id + '_plaq_counts']) / user_states[chat_id + '_fields']
                avg_gr = 200 * gr_auto / 1000000
                result = (avg_plaq / avg_gr) * 1000
                result_text = TEXTS[lang]['result_plaq'].format(avg_plaq, avg_gr, gr_auto, result)
                send_message(chat_id, result_text, get_main_keyboard(lang))
                calculations_history.append({'type': 'plaq', 'result': result, 'timestamp': str(datetime.now())})
                user_states[chat_id] = 'IDLE'
        except ValueError:
            send_message(chat_id, TEXTS[lang]['invalid_number'], get_cancel_keyboard(lang))
        return

    if state == 'DILUTION_PROMPT':
        try:
            match = re.match(r'(\d+)/(\d+)', text)
            if match:
                numerator, denominator = int(match.group(1)), int(match.group(2))
                parts_substance = numerator
                parts_diluent = denominator - numerator
                result_text = TEXTS[lang]['dilution_result'].format(numerator, denominator, parts_substance, parts_diluent)
                send_message(chat_id, result_text, get_main_keyboard(lang))
                user_states[chat_id] = 'IDLE'
            else:
                send_message(chat_id, TEXTS[lang]['invalid_number'], get_dilution_keyboard(lang))
        except ValueError:
            send_message(chat_id, TEXTS[lang]['invalid_number'], get_dilution_keyboard(lang))
        return

    # Gérer les autres commandes comme /start, /help, etc.
    if text == '/start':
        send_welcome_start(chat_id, lang)
        user_states[chat_id] = 'IDLE'
    elif text == '/help':
        send_message(chat_id, TEXTS[lang]['help_text'], get_main_keyboard(lang))
    elif text == '/calc':
        user_states[chat_id] = 'RETI_FIELDS_PROMPT'
        send_message(chat_id, TEXTS[lang]['reti_fields'], get_numeric_keyboard(lang))
    elif text == '/plaquettes':
        user_states[chat_id] = 'PLAQ_FIELDS_PROMPT'
        send_message(chat_id, TEXTS[lang]['plaq_fields'], get_numeric_keyboard(lang))
    elif text == '/dilution':
        user_states[chat_id] = 'DILUTION_PROMPT'
        send_message(chat_id, TEXTS[lang]['dilution_prompt'], get_dilution_keyboard(lang))
    else:
        # Gérer les entrées inconnues
        pass

# Envoi des messages

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, data=data)
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'envoi du message: {e}")

def send_welcome_start(chat_id, lang='fr'):
    send_message(chat_id, TEXTS[lang]['welcome'], get_main_keyboard(lang))

def send_welcome_end(chat_id, lang='fr'):
    message = {'fr': "✅ Calcul terminé !\nChoisissez une autre option :"}
    send_message(chat_id, message.get(lang, "✅ Terminé !"), get_main_keyboard(lang))

def set_webhook():
    """Définir le webhook pour le bot"""
    webhook_url = os.environ.get('WEBHOOK_URL') + '/webhook'
    url = f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url)
        print(f"Webhook défini: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la définition du webhook: {e}")

if __name__ == '__main__':
    # Définir le webhook au démarrage
    set_webhook()
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
