import os
import logging
import asyncio
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from openai import AsyncOpenAI
from elevenlabs.client import ElevenLabs
# Load environment variables
load_dotenv()

import database
import admin

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize clients
openai_client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Global Variables
ALL_VOICES = [] # List of voice objects
VOICES_PER_PAGE = 5
RATE_LIMIT_SECONDS = 30 # Reduced since we have db limits

# Localization Strings
TEXTS = {
    "en": {
        "welcome": "👋 Hello! I am here to provide you with emotional support.\nPlease select your language:",
        "loading": "⏳ Still loading voices... Please try again in a few seconds.",
        "choose_voice": "Please choose a voice style you would like to hear (Click 📢 to preview):",
        "voice_set": "✅ Voice set to: **{voice_name}**.\nNow, tell me what's on your mind?",
        "preview_sent": "Sending preview...",
        "no_preview": "❌ No preview available for this voice.",
        "wait_msg": "⏳ Please wait {remaining} seconds before the next message.",
        "error_processing": "😔 I'm having trouble processing your request right now. Please try again later.",
        "voice_caption": "Here is a message for you ❤️",
        "limit_reached": "🔒 **Daily Limit Reached**\n\nYou have used your 3 free hugs for today.\nWait until tomorrow or upgrade to **Premium** for unlimited support!",
        "premium_locked": "💎 This voice is Premium. Upgrade to unlock!",
        "upsell_phrase": "... I am always here. If you want more hugs - upgrade to premium ♡",
        "system_prompt": "You are a warm, supportive friend. Speak softly, kindly. Do not mention you are an AI."
    },
    "ru": {
        "welcome": "👋 Привет! Я здесь, чтобы поддержать тебя.\nПожалуйста, выбери язык общения:",
        "loading": "⏳ Голоса загружаются... Попробуйте через пару секунд.",
        "choose_voice": "Пожалуйста, выбери голос (Нажми 📢 для прослушивания):\n💎 - только для Премиум",
        "voice_set": "✅ Голос выбран: **{voice_name}**.\nТеперь расскажи, что у тебя на душе? Просто напиши мне.",
        "preview_sent": "Отправляю пример...",
        "no_preview": "❌ Нет примера для этого голоса.",
        "wait_msg": "⏳ Пожалуйста, подожди {remaining} секунд перед следующим сообщением.",
        "error_processing": "😔 У меня возникли проблемы с обработкой запроса. Попробуй позже.",
        "voice_caption": "Это сообщение для тебя ❤️",
        "limit_reached": "🔒 **Лимит исчерпан**\n\nТы использовал(а) все 3 бесплатных утешения на сегодня.\nПриходи завтра или перейди в **Премиум** для безлимитных обнимашек! ♡",
        "premium_locked": "💎 Этот голос доступен только в Премиум. Обнови подписку!",
        "upsell_phrase": "... я всегда здесь. Если хочешь больше обнимашек — переходи в премиум ♡",
        "system_prompt": "Ты поддерживающая подруга/друг, которая обнимает и утешает голосом в стиле ASMR. Никогда не говори, что ты ИИ, бот или программа. Говори только ласково, нежно тепло и сладко. текст будет озвучиваться поэтому не говори от себя типа вот текст для этого и того. не пиши действия типа я глажу тебя или я обнимаю тебя"
    }
}

async def fetch_voices():
    """Fetches voices from ElevenLabs on startup."""
    global ALL_VOICES
    try:
        response = elevenlabs_client.voices.get_all()
        ALL_VOICES = response.voices if hasattr(response, 'voices') else response
        logger.info(f"Loaded {len(ALL_VOICES)} voices from ElevenLabs.")
    except Exception as e:
        logger.error(f"Failed to fetch voices: {e}")
        ALL_VOICES = []

def get_language_keyboard():
    """Keyboard for language selection."""
    keyboard = [
        [
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_voice_keyboard(page: int = 0, lang: str = "en", is_premium: bool = False):
    """Generates paginated keyboard for voices."""
    total_pages = math.ceil(len(ALL_VOICES) / VOICES_PER_PAGE)
    start_idx = page * VOICES_PER_PAGE
    end_idx = start_idx + VOICES_PER_PAGE
    current_voices = ALL_VOICES[start_idx:end_idx]

    keyboard = []
    
    # Logic: Free users get first 2 voices as free, others are premium
    # This is a simple heuristic. You can also match by ID.
    
    for i, voice in enumerate(current_voices):
        global_index = start_idx + i
        is_free_voice = global_index < 3 # First 3 voices are free
        
        lock_icon = "" if (is_premium or is_free_voice) else "💎 "
        
        # Button to Select Voice
        select_btn = InlineKeyboardButton(
            f"{lock_icon}{voice.name}", 
            callback_data=f"select_{voice.voice_id}_{is_free_voice}"
        )
        # Button to Preview 
        preview_btn = InlineKeyboardButton(
            "📢", 
            callback_data=f"preview_{voice.voice_id}"
        )
        keyboard.append([select_btn, preview_btn])

    # Navigation
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
    keyboard.append(nav_row)
    
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message and asks for language preference."""
    user = update.effective_user
    database.add_user(user.id, user.username, user.first_name)
    
    if not ALL_VOICES:
        await update.message.reply_text("⏳ Loading... / Загрузка...")
        return

    await update.message.reply_text(
        "Select Language / Выберите Язык:",
        reply_markup=get_language_keyboard()
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles commands from inline buttons."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    # Get user state from DB
    user_data = database.get_user(user_id)
    # user_data structure: (id, username, first, lang, sub_level, msgs_today, last_date, join_date)
    # We can rely on context.user_data for session lang, but DB is source of truth for sub
    is_premium = False
    if user_data and user_data[4] >= 1:
        is_premium = True

    lang = context.user_data.get("lang", "en")

    if data.startswith("lang_"):
        await query.answer()
        selected_lang = data.split("_")[1]
        context.user_data["lang"] = selected_lang
        
        await query.edit_message_text(
            text=TEXTS[selected_lang]["choose_voice"],
            reply_markup=get_voice_keyboard(0, selected_lang, is_premium)
        )
        return

    if data.startswith("page_"):
        await query.answer()
        page = int(data.split("_")[1])
        await query.edit_message_reply_markup(reply_markup=get_voice_keyboard(page, lang, is_premium))
        return

    if data.startswith("select_"):
        parts = data.split("_")
        voice_id = parts[1]
        is_free_voice_btn = parts[2] == "True"
        
        if not is_premium and not is_free_voice_btn:
             await query.answer(TEXTS[lang]["premium_locked"], show_alert=True)
             return

        await query.answer()
        voice = next((v for v in ALL_VOICES if v.voice_id == voice_id), None)
        voice_name = voice.name if voice else "Unknown"
        
        context.user_data["voice_id"] = voice_id
        
        await query.edit_message_text(
            text=TEXTS[lang]["voice_set"].format(voice_name=voice_name),
            parse_mode="Markdown"
        )
        return
        
    if data.startswith("preview_"):
        await query.answer(TEXTS[lang]["preview_sent"])
        voice_id = data.split("_")[1]
        voice = next((v for v in ALL_VOICES if v.voice_id == voice_id), None)
        if voice and hasattr(voice, 'preview_url') and voice.preview_url:
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=voice.preview_url,
                caption=f"Preview: {voice.name}",
                performer="ElevenLabs",
                title=voice.name
            )
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=TEXTS[lang]["no_preview"])
        return

    if data == "noop":
        await query.answer()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages."""
    user_id = update.effective_user.id
    user_text = update.message.text
    lang = context.user_data.get("lang", "en")
    
    # 1. Check DB Limits
    allowed = database.check_limit(user_id) # Default limit 3
    if not allowed:
        await update.message.reply_text(TEXTS[lang]["limit_reached"], parse_mode="Markdown")
        return

    # Check database for premium status
    user_db = database.get_user(user_id)
    is_premium = user_db and user_db[4] >= 1

    # 2. Get Voice preference
    voice_id = context.user_data.get("voice_id")
    if not voice_id:
        if ALL_VOICES:
            voice_id = ALL_VOICES[0].voice_id # Default to first free one
        else:
            voice_id = "21m00Tcm4TlvDq8ikWAM"

    await update.message.reply_chat_action(action="record_voice")

    try:
        # 3. Generate Text
        system_instruction = TEXTS[lang]["system_prompt"]
        if lang == "ru":
             user_prompt = (
                f"Сгенерируй теплое, эмпатичное, ласковое ответное сообщение на русском языке, "
                f"как близкий друг утешает того, кому грустно из-за: '{user_text}'. "
                f"Длина текста 1-2 минуты для озвучки (примерно 150-200 слов), позитивно и поддерживающе."
            )
        else:
            user_prompt = (
                f"Generate a warm, empathetic, affectionate response in English, "
                f"like a close friend comforting someone who's sad about: '{user_text}'. "
                f"Keep it 1-2 minutes long for spoken text (approx 150-200 words), positive and uplifting."
            )

        gpt_response = await openai_client.chat.completions.create(
            model="xiaomi/mimo-v2-flash:free",
            extra_body={"HTTP-Referer": "https://telegram.bot", "X-Title": "Emotional Support Bot"},
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ]
        )
        supportive_text = gpt_response.choices[0].message.content
        
        # 4. Upsell appending (For Free users only)
        if not is_premium:
            upsell = TEXTS[lang]["upsell_phrase"]
            supportive_text += f"\n\n{upsell}"

        # 5. Generate Audio
        def generate_audio():
            return elevenlabs_client.text_to_speech.convert(
                text=supportive_text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2"
            )

        audio_iterator = await asyncio.get_event_loop().run_in_executor(None, generate_audio)
        audio_bytes = b"".join(audio_iterator)

        # 6. Send Voice
        await update.message.reply_voice(voice=audio_bytes, caption=TEXTS[lang]["voice_caption"])
        
        # 7. Increment Usage
        database.increment_usage(user_id)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(TEXTS[lang]["error_processing"])

async def post_init(application):
    await fetch_voices()
    database.init_db()

if __name__ == '__main__':
    if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY or not ELEVENLABS_API_KEY:
        print("❌ Error: Missing API Keys.")
        exit(1)

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin.admin_start))
    application.add_handler(CommandHandler("add_premium", admin.add_premium))
    application.add_handler(CommandHandler("remove_premium", admin.remove_premium))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 Bot is running...")
    application.run_polling()
