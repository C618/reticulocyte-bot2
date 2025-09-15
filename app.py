import os
import logging
import requests
import json
import re
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from flask import Flask, request, jsonify

# Initialize Flask app
app = Flask(__name__)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# IPTV configuration
M3U_URL = "https://raw.githubusercontent.com/hemzaberkane/ARAB-IPTV/main/ARABIPTV.m3u"
PAGE_SIZE = 6

# Bot token
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# State management for laboratory assistant
user_states = {}
user_languages = {}
calculations_history = []

# ------------------- IPTV Functions -------------------

def fetch_m3u(url: str) -> str:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text

def parse_m3u(m3u_text: str):
    lines = [ln.strip() for ln in m3u_text.splitlines() if ln.strip()]
    channels = []
    title = None
    for ln in lines:
        if ln.startswith("#EXTINF"):
            if "," in ln:
                title = ln.split(",", 1)[1].strip()
            else:
                title = ln
        elif not ln.startswith("#"):
            stream = ln
            if title is None:
                title = stream
            channels.append((title, stream))
            title = None
    return channels

def build_keyboard(channels, page):
    start = page * PAGE_SIZE
    subset = channels[start:start + PAGE_SIZE]
    buttons = []
    for idx, (title, _) in enumerate(subset, start=start):
        buttons.append([InlineKeyboardButton(text=title[:40], callback_data=f"play:{idx}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"page:{page-1}"))
    if start + PAGE_SIZE < len(channels):
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"page:{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)

# ------------------- Laboratory Assistant Functions -------------------

# Définition des claviers
def get_main_keyboard(lang='fr'):
    keyboards = {
        'fr': {
            'keyboard': [
                ['🔢 Réticulocytes', '🩸 Plaquettes'],
                ['🧪 Dilution', '⚙️ Paramètres'],
                ['ℹ️ Aide', '🔄 Langue', '📺 IPTV']
            ],
            'resize_keyboard': True
        },
        'en': {
            'keyboard': [
                ['🔢 Reticulocytes', '🩸 Platelets'],
                ['🧪 Dilution', '⚙️ Settings'],
                ['ℹ️ Help', '🔄 Language', '📺 IPTV']
            ],
            'resize_keyboard': True
        },
        'ar': {
            'keyboard': [
                ['🔢 الخلايا الشبكية', '🩸 الصفائح الدموية'],
                ['🧪 التخفيف', '⚙️ الإعدادات'],
                ['ℹ️ المساعدة', '🔄 اللغة', '📺 IPTV']
            ],
            'resize_keyboard': True
        }
    }
    return keyboards.get(lang, keyboards['fr'])

def get_numeric_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
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
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
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
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [[cancel_text[lang]]],
        'resize_keyboard': True
    }

def get_language_keyboard():
    return {
        'keyboard': [
            ['🇫🇷 Français', '🇬🇧 English'],
            ['🇸🇦 العربية', '🔙 Retour']
        ],
        'resize_keyboard': True
    }

def get_settings_keyboard(lang='fr'):
    texts = {
        'fr': ['🔙 Retour', '🗑️ Effacer historique', '📊 Statistiques'],
        'en': ['🔙 Back', '🗑️ Clear history', '📊 Statistics'],
        'ar': ['🔙 رجوع', '🗑️ مسح السجل', '📊 الإحصائيات']
    }
    return {
        'keyboard': [[texts[lang][0]], [texts[lang][1]], [texts[lang][2]]],
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
        'help_text': """ℹ️ *AIDE - Commandes disponibles*

🔢 *Réticulocytes* : Calcul du taux de réticulocytes
🩸 *Plaquettes* : Calcul du nombre de plaquettes
🧪 *Dilution* : Préparation de dilutions
⚙️ *Paramètres* : Configuration du bot
🔄 *Langue* : Changer la langue
📺 *IPTV* : Regarder des chaînes TV

*Commandes rapides* :
/start - Démarrer le bot
/help - Afficher l'aide
/calc - Calcul réticulocytes
/plaquettes - Calcul plaquettes
/dilution - Préparation dilution
/iptv - Liste des chaînes IPTV""",
        'settings': "⚙️ *Paramètres* :\n- Langue: Français\n- Historique: Activé",
        'stats': "📊 *Statistiques* :\n- Calculs effectués: {}\n- Dernier calcul: {}",
        'iptv_welcome': "📺 Bienvenue dans la section IPTV!\nUtilisez /list pour afficher les chaînes disponibles."
    },
    'en': {
        'welcome': "👋 Hello! I'm your laboratory assistant.\nChoose an option:",
        'reti_fields': "🔢 How many fields do you want to analyze for reticulocytes?",
        'plaq_fields': "🩸 How many fields do you want to analyze for platelets?",
        'dilution_prompt': "🧪 Enter the desired dilution (ex: 1/2, 1/10):",
        'reti_count': "Enter the number of reticulocytes in Field {}:",
        'plaq_count': "Enter the number of platelets in Field {}:",
        'rbc_quarter': "Enter the number of red blood cells in quarter Field {}:",
        'gr_auto': "⚙️ Enter the automatic red blood cell count (machine):",
        'cancel': "❌ Operation cancelled.",
        'invalid_number': "⚠️ Please enter a valid number.",
        'result_reti': "--- Reticulocytes Result ---\nTotal reticulocytes: {}\nAverage RBC: {:.2f}\nRate: {:.2f}%",
        'result_plaq': "--- Platelets Result ---\nAverage platelets: {:.2f}\nAverage RBC: {:.2f}\nAuto RBC: {}\nResult: {:.2f}",
        'dilution_result': "🧪 For a {}/{} dilution:\n- Substance: {} part(s)\n- Diluent: {} part(s)",
        'quantity_prompt': "Enter the desired total quantity:",
        'exact_volumes': "📊 For {} unit(s):\n- Substance: {:.2f}\n- Diluent: {:.2f}",
        'help_text': """ℹ️ *HELP - Available commands*

🔢 *Reticulocytes* : Reticulocyte count calculation
🩸 *Platelets* : Platelet count calculation
🧪 *Dilution* : Dilution preparation
⚙️ *Settings* : Bot configuration
🔄 *Language* : Change language
📺 *IPTV* : Watch TV channels

*Quick commands* :
/start - Start bot
/help - Show help
/calc - Calculate reticulocytes
/plaquettes - Calculate platelets
/dilution - Prepare dilution
/iptv - List IPTV channels""",
        'settings': "⚙️ *Settings* :\n- Language: English\n- History: Enabled",
        'stats': "📊 *Statistics* :\n- Calculations done: {}\n- Last calculation: {}",
        'iptv_welcome': "📺 Welcome to the IPTV section!\nUse /list to show available channels."
    },
    'ar': {
        'welcome': "👋 مرحبًا! أنا مساعدك في المختبر.\nاختر خيارًا:",
        'reti_fields': "🔢 كم حقلًا تريد تحليله للخلايا الشبكية؟",
        'plaq_fields': "🩸 كم حقلًا تريد تحليله للصفائح الدموية؟",
        'dilution_prompt': "🧪 أدخل التخفيف المطلوب (مثال: 1/2, 1/10):",
        'reti_count': "أدخل عدد الخلايا الشبكية في الحقل {}:",
        'plaq_count': "أدخل عدد الصفائح الدموية في الحقل {}:",
        'rbc_quarter': "أدخل عدد كريات الدم الحمراء في ربع الحقل {}:",
        'gr_auto': "⚙️ أدخل عدد كريات الدم الحمراء التلقائي (الآلة):",
        'cancel': "❌ تم إلغاء العملية.",
        'invalid_number': "⚠️ الرجاء إدخال رقم صحيح.",
        'result_reti': "--- نتيجة الخلايا الشبكية ---\nالمجموع: {}\nمتوسط كريات الدم الحمراء: {:.2f}\nالنسبة: {:.2f}%",
        'result_plaq': "--- نتيجة الصفائح الدموية ---\nمتوسط الصفائح: {:.2f}\nمتوسط كريات الدم الحمراء: {:.2f}\nالعدد التلقائي: {}\nالنتيجة: {:.2f}",
        'dilution_result': "🧪 للتخفيف {}/{} :\n- المادة: {} جزء\n- المخفف: {} جزء",
        'quantity_prompt': "أدخل الكمية الإجمالية المطلوبة:",
        'exact_volumes': "📊 لكل {} وحدة:\n- المادة: {:.2f}\n- المخفف: {:.2f}",
        'help_text': """ℹ️ *المساعدة - الأوامر المتاحة*

🔢 *الخلايا الشبكية* : حساب نسبة الخلايا الشبكية
🩸 *الصفائح الدموية* : حساب عدد الصفائح الدموية
🧪 *التخفيف* : تحضير المحاليل المخففة
⚙️ *الإعدادات* : تكوين البوت
🔄 *اللغة* : تغيير اللغة
📺 *IPTV* : مشاهدة القنوات التلفزيونية

*أوامر سريعة* :
/start - بدء البوت
/help - عرض المساعدة
/calc - حساب الخلايا الشبكية
/plaquettes - حساب الصفائح الدموية
/dilution - تحضير التخفيف
/iptv - قائمة قنوات IPTV""",
        'settings': "⚙️ *الإعدادات* :\n- اللغة: العربية\n- السجل: مفعل",
        'stats': "📊 *الإحصائيات* :\n- عدد العمليات الحسابية: {}\n- آخر عملية: {}",
        'iptv_welcome': "📺 مرحبًا بك في قسم IPTV!\nاستخدم /list لعرض القنوات المتاحة."
    }
}

# ------------------- Telegram Handlers -------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = user_languages.get(chat_id, 'fr')
    await update.message.reply_text(TEXTS[lang]['welcome'], reply_markup=get_main_keyboard(lang))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = user_languages.get(chat_id, 'fr')
    await update.message.reply_text(TEXTS[lang]['help_text'], parse_mode='Markdown')

async def iptv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = user_languages.get(chat_id, 'fr')
    await update.message.reply_text(TEXTS[lang]['iptv_welcome'])

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = fetch_m3u(M3U_URL)
        context.user_data["channels"] = parse_m3u(text)
        if not context.user_data["channels"]:
            await update.message.reply_text("❌ لم يتم العثور على قنوات.")
            return
        keyboard = build_keyboard(context.user_data["channels"], page=0)
        await update.message.reply_text("اختر قناة:", reply_markup=keyboard)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في تحميل القنوات: {str(e)}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    channels = context.user_data.get("channels", [])
    if not channels:
        return

    if data.startswith("page:"):
        page = int(data.split(":")[1])
        kb = build_keyboard(channels, page)
        await query.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("play:"):
        idx = int(data.split(":")[1])
        title, url = channels[idx]

        try:
            # إرسال الفيديو مباشرة داخل تيليغرام
            await query.message.reply_video(
                video=url,
                caption=f"🎬 {title}",
                supports_streaming=True
            )
        except Exception as e:
            await query.message.reply_text(f"❌ لم أستطع تشغيل القناة داخل تيليغرام.\n🔗 الرابط: {url}")

# ------------------- Flask Routes -------------------

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

        # Gestion des commandes textuelles et boutons
        if text == '/start' or text == '🔙 Retour' or text == '🔙 Back' or text == '🔙 رجوع':
            send_welcome_start(chat_id, lang)
            user_states[chat_id] = {'step': 0}
        
        elif text == '/help' or text == 'ℹ️ Aide' or text == 'ℹ️ Help' or text == 'ℹ️ المساعدة':
            send_message(chat_id, TEXTS[lang]['help_text'], get_main_keyboard(lang), parse_mode='Markdown')
        
        elif text == '/calc' or text == '🔢 Réticulocytes' or text == '🔢 Reticulocytes' or text == '🔢 الخلايا الشبكية':
            send_message(chat_id, TEXTS[lang]['reti_fields'], get_numeric_keyboard(lang))
            user_states[chat_id] = {'step': 50, 'type': 'reti', 'reti_counts': [], 'rbc_counts': [], 'nb_champs': None}
        
        elif text == '/plaquettes' or text == '🩸 Plaquettes' or text == '🩸 Platelets' or text == '🩸 الصفائح الدموية':
            send_message(chat_id, TEXTS[lang]['plaq_fields'], get_numeric_keyboard(lang))
            user_states[chat_id] = {'step': 100, 'type': 'plaq', 'plaq_counts': [], 'rbc_counts': [], 'gr_auto': None, 'nb_champs': None}
        
        elif text == '/dilution' or text == '🧪 Dilution' or text == '🧪 التخفيف':
            send_message(chat_id, TEXTS[lang]['dilution_prompt'], get_dilution_keyboard(lang))
            user_states[chat_id] = {'step': 400, 'type': 'dilution'}
        
        elif text == '/iptv' or text == '📺 IPTV':
            send_message(chat_id, TEXTS[lang]['iptv_welcome'], get_main_keyboard(lang))
        
        elif text == '⚙️ Paramètres' or text == '⚙️ Settings' or text == '⚙️ الإعدادات':
            send_message(chat_id, TEXTS[lang]['settings'], get_settings_keyboard(lang), parse_mode='Markdown')
        
        elif text == '🔄 Langue' or text == '🔄 Language' or text == '🔄 اللغة':
            send_message(chat_id, "🌍 Choose your language / اختر لغتك:", get_language_keyboard())
        
        elif text == '🇫🇷 Français':
            user_languages[chat_id] = 'fr'
            send_message(chat_id, "✅ Langue changée en Français", get_main_keyboard('fr'))
        
        elif text == '🇬🇧 English':
            user_languages[chat_id] = 'en'
            send_message(chat_id, "✅ Language changed to English", get_main_keyboard('en'))
        
        elif text == '🇸🇦 العربية':
            user_languages[chat_id] = 'ar'
            send_message(chat_id, "✅ تم تغيير اللغة إلى العربية", get_main_keyboard('ar'))
        
        elif text == '📊 Statistiques' or text == '📊 Statistics' or text == '📊 الإحصائيات':
            stats_text = TEXTS[lang]['stats'].format(len(calculations_history), 
                                                   calculations_history[-1]['type'] if calculations_history else 'None')
            send_message(chat_id, stats_text, get_main_keyboard(lang), parse_mode='Markdown')
        
        elif text.lower() in ['annuler', 'cancel', 'إلغاء']:
            send_message(chat_id, TEXTS[lang]['cancel'], get_main_keyboard(lang))
            user_states[chat_id] = {'step': 0}
        
        elif chat_id in user_states:
            handle_input(chat_id, text, lang)
    
    return jsonify({'status': 'ok'})

# -------------------- Gestion des inputs --------------------

def handle_input(chat_id, text, lang):
    state = user_states[chat_id]

    try:
        if state.get('type') != 'dilution':
            value = float(text) if '.' in text else int(text)
            if value < 0:
                send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))
                return
        else:
            value = text

        if state.get('type') == 'reti':
            handle_reti(chat_id, value, lang)
        elif state.get('type') == 'plaq':
            handle_plaquettes(chat_id, value, lang)
        elif state.get('type') == 'dilution':
            handle_dilution(chat_id, value, lang)
    
    except ValueError:
        send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))

# -------------------- Réticulocytes --------------------

def handle_reti(chat_id, value, lang):
    state = user_states[chat_id]

    if state['step'] == 50:
        state['nb_champs'] = value
        send_message(chat_id, TEXTS[lang]['reti_count'].format(1), get_numeric_keyboard(lang))
        state['step'] = 51
        return

    if 51 <= state['step'] < 51 + state['nb_champs']:
        state['reti_counts'].append(value)
        champ_actuel = len(state['reti_counts'])
        if len(state['reti_counts']) < state['nb_champs']:
            send_message(chat_id, TEXTS[lang]['reti_count'].format(champ_actuel + 1), get_numeric_keyboard(lang))
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(1), get_numeric_keyboard(lang))
            state['step'] = 200
        return

    if 200 <= state['step'] <= 202:
        state['rbc_counts'].append(value)
        if state['step'] < 202:
            champ = state['step'] - 199
            send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(champ + 1), get_numeric_keyboard(lang))
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
            
            message = TEXTS[lang]['result_reti'].format(reti_total, rbc_total, taux)
            send_message(chat_id, message, get_main_keyboard(lang))
            send_welcome_end(chat_id, lang)
            user_states[chat_id] = {'step': 0}

# -------------------- Plaquettes --------------------

def handle_plaquettes(chat_id, value, lang):
    state = user_states[chat_id]

    if state['step'] == 100:
        state['nb_champs'] = value
        send_message(chat_id, TEXTS[lang]['plaq_count'].format(1), get_numeric_keyboard(lang))
        state['step'] = 101
        return

    if 101 <= state['step'] < 101 + state['nb_champs']:
        state['plaq_counts'].append(value)
        champ_actuel = len(state['plaq_counts'])
        if len(state['plaq_counts']) < state['nb_champs']:
            send_message(chat_id, TEXTS[lang]['plaq_count'].format(champ_actuel + 1), get_numeric_keyboard(lang))
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(1), get_numeric_keyboard(lang))
            state['step'] = 300
        return

    if 300 <= state['step'] <= 302:
        state['rbc_counts'].append(value)
        if state['step'] < 302:
            champ = state['step'] - 299
            send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(champ + 1), get_numeric_keyboard(lang))
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS[lang]['gr_auto'], get_numeric_keyboard(lang))
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
        
        message = TEXTS[lang]['result_plaq'].format(plaq_moy, avg_rbc, state['gr_auto'], result)
        send_message(chat_id, message, get_main_keyboard(lang))
        send_welcome_end(chat_id, lang)
        user_states[chat_id] = {'step': 0}

# -------------------- Dilution --------------------

def handle_dilution(chat_id, text, lang):
    state = user_states[chat_id]

    try:
        if state['step'] == 400:
            if '/' in text:
                numer, denom = map(int, text.split('/'))
                if numer <= 0 or denom <= 0 or numer > denom:
                    raise ValueError
                
                message = TEXTS[lang]['dilution_result'].format(numer, denom, numer, denom - numer)
                send_message(chat_id, message, get_main_keyboard(lang))
                
                # Demander pour les volumes exacts
                send_message(chat_id, TEXTS[lang]['quantity_prompt'], get_cancel_keyboard(lang))
                state['step'] = 401
                state['last_dilution'] = text
            else:
                send_message(chat_id, TEXTS[lang]['invalid_number'], get_dilution_keyboard(lang))
        
        elif state['step'] == 401:
            if text.lower() in ['annuler', 'cancel', 'إلغاء']:
                send_welcome_end(chat_id, lang)
                user_states[chat_id] = {'step': 0}
            else:
                quantite = float(text)
                numer, denom = map(int, state.get('last_dilution', '1/2').split('/'))
                part_substance = (numer/denom) * quantite
                part_diluant = quantite - part_substance
                
                message = TEXTS[lang]['exact_volumes'].format(quantite, part_substance, part_diluant)
                send_message(chat_id, message, get_main_keyboard(lang))
                
                # Enregistrer dans l'historique
                calculations_history.append({
                    'type': 'dilution',
                    'result': f"{numer}/{denom}",
                    'timestamp': datetime.now().isoformat()
                })
                
                send_welcome_end(chat_id, lang)
                user_states[chat_id] = {'step': 0}
    
    except (ValueError, AttributeError):
        send_message(chat_id, TEXTS[lang]['invalid_number'], get_dilution_keyboard(lang))

# -------------------- Messages --------------------

def send_welcome_start(chat_id, lang='fr'):
    send_message(chat_id, TEXTS[lang]['welcome'], get_main_keyboard(lang))

def send_welcome_end(chat_id, lang='fr'):
    message = {
        'fr': "✅ Calcul terminé !\nChoisissez une autre option :",
        'en': "✅ Calculation completed!\nChoose another option:",
        'ar': "✅ اكتمل الحساب!\nاختر خيارًا آخر:"
    }
    send_message(chat_id, message.get(lang, "✅ Done!"), get_main_keyboard(lang))

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

# ------------------- MAIN -------------------
def main():
    # Create Telegram application
    app_bot = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("help", help_command))
    app_bot.add_handler(CommandHandler("iptv", iptv_start))
    app_bot.add_handler(CommandHandler("list", list_channels))
    app_bot.add_handler(CallbackQueryHandler(button_handler))

    # Set webhook
    set_webhook()
    
    # Start the bot in webhook mode
    webhook_url = os.environ.get('WEBHOOK_URL') + '/webhook'
    app_bot.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get('PORT', 5000)),
        url_path=TELEGRAM_TOKEN,
        webhook_url=webhook_url
    )

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
