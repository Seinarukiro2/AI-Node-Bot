import os
import sqlite3
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from dotenv import load_dotenv
from clicktime_ai_bot import ClicktimeAIBot

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Define states for conversation handler
WAITING_FOR_URL = range(1)

# Initialize database
conn = sqlite3.connect('bot_data.db')
cursor = conn.cursor()

# Create tables for state storage and user bots
cursor.execute('''
    CREATE TABLE IF NOT EXISTS states (
        chat_id INTEGER PRIMARY KEY,
        state TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_bots (
        chat_id INTEGER PRIMARY KEY,
        bot BLOB
    )
''')
conn.commit()

# Function to save state
def save_state(chat_id, state):
    cursor.execute('REPLACE INTO states (chat_id, state) VALUES (?, ?)', (chat_id, state))
    conn.commit()

# Function to load state
def load_state(chat_id):
    cursor.execute('SELECT state FROM states WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    return result[0] if result else None

# Function to save user bot
def save_user_bot(chat_id, bot):
    cursor.execute('REPLACE INTO user_bots (chat_id, bot) VALUES (?, ?)', (chat_id, pickle.dumps(bot)))
    conn.commit()

# Function to load user bot
def load_user_bot(chat_id):
    cursor.execute('SELECT bot FROM user_bots WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    return pickle.loads(result[0]) if result else None

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.message.chat_id
    
    # Initialize user bot instance if not already done
    bot_instance = load_user_bot(chat_id)
    if not bot_instance:
        bot_instance = ClicktimeAIBot()
        save_user_bot(chat_id, bot_instance)
    
    keyboard = [
        [InlineKeyboardButton("Обучить меня", callback_data='train')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        rf"Привет {user.mention_html()}! Я готов помочь тебе с установкой и настройкой нод",
        reply_markup=reply_markup,
    )

# Train command handler
async def train(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Create cancel button
    keyboard = [
        [InlineKeyboardButton("Отменить", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Пожалуйста, укажи URL веб-сайта, на котором ты хочешь обучить меня",
        reply_markup=reply_markup
    )
    return WAITING_FOR_URL

# Handle URL input for training
async def url_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text
    chat_id = update.message.chat_id

    # Save the URL in the state storage
    save_state(chat_id, {'url': url})

    await update.message.reply_text("Я учусь, подожди немного...")
    bot_instance = load_user_bot(chat_id)
    data = bot_instance.load_data_from_url(url)
    bot_instance.train_model_from_data(data)
    save_user_bot(chat_id, bot_instance)
    await update.message.reply_text("Класс! Я теперь стал умнее чем ты 👀")

    # Clear state
    cursor.execute('DELETE FROM states WHERE chat_id = ?', (chat_id,))
    conn.commit()
    return ConversationHandler.END

# Handle incoming messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    text = update.message.text

    state = load_state(chat_id)
    if state:
        if 'url' in state:
            await url_received(update, context)
    elif text.startswith('!'):
        bot_instance = load_user_bot(chat_id)
        response = bot_instance.ask_question(f"Отвечай на русском, и форматируй код или команды в ``` - {text[1:].strip()}")
        formatted_response = format_response(response)
        await update.message.reply_text(formatted_response, parse_mode='Markdown')
    else:
        await update.message.reply_text("Пожалуйста, начни свой вопрос с '!' чтобы я мог ответить.")

# Format response
def format_response(response: str) -> str:
    reserved_chars = r'_*[]()~`>#+-=|{}.!'
    
    # Check if response is a dictionary
    if isinstance(response, dict):
        # Assuming you want to fetch the value associated with the key "result"
        if "result" in response:
            response_str = response["result"]
        else:
            response_str = ""
    else:
        # If response is not a dictionary, assume it's already a string
        response_str = response
    
    # Replace reserved characters in the response string
    for char in reserved_chars:
        response_str = response_str.replace(char, f'\\{char}')
    
    # Return the formatted response with newline characters
    return f"{response_str}"

# Cancel conversation handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Отмена обучения. Возвращаюсь в главное меню."
    )
    await start(update, context)
    return ConversationHandler.END

def main() -> None:
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TOKEN).build()

    # Conversation handler for training
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(train, pattern='train')],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, url_received)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern='cancel')],
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
