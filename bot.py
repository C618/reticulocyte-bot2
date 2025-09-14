import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
)

# -------------------------
# إعداد البوت
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # ضع التوكن في Environment Variables على Render
RETI, RBC = range(2)
user_data = {}

app = FastAPI()
application = ApplicationBuilder().token(BOT_TOKEN).build()

# -------------------------
# وظائف البوت
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_chat.id] = {"reti": [], "rbc": []}
    await update.message.reply_text(
        "👋 أهلاً! سنحسب نسبة الريتيكولوسيت.\n"
        "أدخل عدد الريتيكولوسيت في Champ 1:"
    )
    return RETI

async def get_reti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = user_data[chat_id]
    try:
        value = int(update.message.text)
        if value < 0:
            raise ValueError
        data["reti"].append(value)
    except ValueError:
        await update.message.reply_text("⚠️ الرجاء إدخال رقم صحيح موجب.")
        return RETI

    if len(data["reti"]) < 10:
        await update.message.reply_text(f"Champ {len(data['reti'])+1}:")
        return RETI
    else:
        await update.message.reply_text("✅ انتهينا من الريتيكولوسيت.\n"
                                        "الآن أدخل عدد الكريات الحمراء في ربع Champ 1:")
        return RBC

async def get_rbc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = user_data[chat_id]
    try:
        value = int(update.message.text)
        if value < 0:
            raise ValueError
        data["rbc"].append(value)
    except ValueError:
        await update.message.reply_text("⚠️ الرجاء إدخال رقم صحيح موجب.")
        return RBC

    if len(data["rbc"]) < 3:
        await update.message.reply_text(f"ربع Champ {len(data['rbc'])+1}:")
        return RBC
    else:
        # الحسابات
        reti_total = sum(data["reti"])
        rbc1, rbc2, rbc3 = [v*4 for v in data["rbc"]]
        avg_rbc = (rbc1 + rbc2 + rbc3)/3
        rbc_total = avg_rbc*10
        result = (reti_total / rbc_total)*100

        await update.message.reply_text(
            f"--- النتيجة ---\n"
            f"🔹 مجموع الريتيكولوسيت = {reti_total}\n"
            f"🔹 متوسط الكريات الحمراء (×10) = {rbc_total:.2f}\n"
            f"🔹 نسبة الريتيكولوسيت = {result:.2f} %"
        )
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 تم إلغاء العملية")
    return ConversationHandler.END

# -------------------------
# إعداد Conversation Handler
# -------------------------
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        RETI: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_reti)],
        RBC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rbc)],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)
application.add_handler(conv_handler)

# -------------------------
# Webhook endpoint
# -------------------------
@app.post(f"/{BOT_TOKEN}")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
    await application.update_queue.put(update)
    return {"ok": True}

@app.get("/")
async def index():
    return {"message": "🤖 البوت شغال على Render"}
