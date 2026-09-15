"""
Точка входа — запуск Telegram бота для учёта расходов
"""
import logging
from telegram import Update
from bot import create_application, post_init

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Запуск бота"""
    logger.info("🚀 Запуск бота для учёта расходов...")
    
    # Создание приложения
    application = create_application()
    application.post_init = post_init
    
    # Запуск
    logger.info("✅ Бот готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main() 