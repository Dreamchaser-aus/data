import logging
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Your Telegram Bot Token (replace or use env var)
BOT_TOKEN = "7751711985:AAFNUH0Sur1abtPM2RYaXznG-aMrjAjdmUo"

# Create Flask app to keep Render Web Service alive
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Telegram bot is running (via Render Web Service)."

# Define a simple /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! Your Telegram bot is running.")

# Main bot loop
async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    print("🤖 Bot started polling...")
    await application.run_polling()

# Start the bot in a separate thread
def run_bot():
    asyncio.run(main())

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
