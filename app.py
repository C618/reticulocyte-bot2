from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# توكن البوت الخاص بك
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8402125692:AAHndM_lQg6xozZ4WWdu0udgM_BjBmvkV0U')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# حالة المستخدمين
user_states = {}

@app.route('/')
def home():
    return "بوت حساب نسبة الريتيكولوسيت يعمل بشكل صحيح!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        
        if text == '/start':
            send_message(chat_id, "مرحباً! أنا بوت حساب نسبة الريتيكولوسيت. اكتب /calc لبدء الحساب.")
            user_states[chat_id] = {'step': 0, 'reti_counts': [], 'rbc_counts': []}
        elif text == '/calc':
            send_message(chat_id, "لنبدأ عملية الحساب. أدخل عدد الريتيكولوسيت في كل champ (المجموع 10).")
            send_message(chat_id, "أدخل عدد الريتيكولوسيت في Champ 1:")
            user_states[chat_id] = {'step': 1, 'reti_counts': [], 'rbc_counts': []}
        elif chat_id in user_states:
            handle_user_input(chat_id, text)
    
    return jsonify({'status': 'ok'})

def handle_user_input(chat_id, text):
    state = user_states[chat_id]
    
    try:
        value = int(text)
        if value < 0:
            send_message(chat_id, "⚠️ الرجاء إدخال رقم موجب فقط.")
            return
    except ValueError:
        send_message(chat_id, "⚠️ الرجاء إدخال رقم صحيح.")
        return
    
    if state['step'] <= 10:
        # جمع قيم الريتيكولوسيت
        state['reti_counts'].append(value)
        
        if state['step'] < 10:
            send_message(chat_id, f"أدخل عدد الريتيكولوسيت في Champ {state['step'] + 1}:")
            state['step'] += 1
        else:
            send_message(chat_id, "تم جمع جميع قيم الريتيكولوسيت. الآن أدخل عدد الكريات الحمراء في ربع Champ 1:")
            state['step'] = 11
    elif state['step'] <= 13:
        # جمع قيم الكريات الحمراء
        state['rbc_counts'].append(value)
        
        if state['step'] < 13:
            send_message(chat_id, f"أدخل عدد الكريات الحمراء في ربع Champ {state['step'] - 10}:")
            state['step'] += 1
        else:
            # حساب النتيجة
            reti_total = sum(state['reti_counts'])
            
            rbc1 = state['rbc_counts'][0] * 4
            rbc2 = state['rbc_counts'][1] * 4
            rbc3 = state['rbc_counts'][2] * 4
            
            avg_rbc = (rbc1 + rbc2 + rbc3) / 3
            rbc_total = avg_rbc * 10
            
            result = (reti_total / rbc_total) * 100
            
            # إرسال النتيجة
            message = f"--- النتيجة ---\n"
            message += f"مجموع الريتيكولوسيت = {reti_total}\n"
            message += f"متوسط الكريات الحمراء (×10) = {rbc_total:.2f}\n"
            message += f"نسبة الريتيكولوسيت = {result:.2f} %"
            
            send_message(chat_id, message)
            
            # إعادة تعيين الحالة
            user_states[chat_id] = {'step': 0, 'reti_counts': [], 'rbc_counts': []}

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, json=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

