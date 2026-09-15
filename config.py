"""
Конфигурация бота
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_ADMIN_ID = int(os.getenv("BOT_ADMIN_ID", "0"))  # Ваш Telegram ID

# Bridge API (LLM)
BRIDGE_API_URL = os.getenv("BRIDGE_API_URL", "https://api.bridge-ai.com/v1/chat/completions")
BRIDGE_API_KEY = os.getenv("BRIDGE_API_KEY", "")
BRIDGE_MODEL = os.getenv("BRIDGE_MODEL", "gpt-4o")

# База данных
DB_PATH = os.getenv("DB_PATH", "expenses.db")

# Настройки сводок
SUMMARY_TIMEZONE = "Europe/Moscow"
