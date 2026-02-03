"""
Конфигурация бота
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Класс конфигурации бота"""
    
    # Discord настройки
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'YOUR_DISCORD_TOKEN_HERE')
    PREFIX = os.getenv('PREFIX', '!')
    
    # Прокси настройки (для обхода блокировок)
    PROXY_URL = os.getenv('PROXY_URL', '')  # Например: socks5://127.0.0.1:10808
    USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
    
    # LM Studio настройки
    LM_STUDIO_URL = os.getenv('LM_STUDIO_URL', 'http://localhost:1234/v1')
    LM_STUDIO_MODEL = os.getenv('LM_STUDIO_MODEL', 'local-model')
    
    # Параметры генерации
    MAX_TOKENS = int(os.getenv('MAX_TOKENS', '2000'))
    TEMPERATURE = float(os.getenv('TEMPERATURE', '0.7'))
    TOP_P = float(os.getenv('TOP_P', '0.9'))
    
    # Управление контекстом
    MAX_CONTEXT_MESSAGES = int(os.getenv('MAX_CONTEXT_MESSAGES', '10'))
    CONTEXT_TIMEOUT = int(os.getenv('CONTEXT_TIMEOUT', '3600'))  # 1 час в секундах
    
    # Системный промпт
    SYSTEM_PROMPT = os.getenv(
        'SYSTEM_PROMPT',
        "Ты умный и дружелюбный ИИ-ассистент в Discord. "
        "Отвечай полезно, точно и вежливо. "
        "Используй форматирование Discord когда это уместно. "
        "Если не знаешь точного ответа, честно скажи об этом. "
        "\n\n"
        "У тебя есть доступ к актуальной информации из интернета через веб-поиск. "
        "Когда ты получаешь информацию из веб-источников, используй её для ответа "
        "и упомяни источники в конце. Отвечай естественно, как будто ты просто знаешь эту информацию. "
        "\n\n"
        "Ты также можешь анализировать изображения. Когда тебе предоставляется информация об изображении, "
        "используй её для детального и точного описания того, что изображено."
    )
    
    # Роли и разрешения
    ADMIN_ROLE_IDS = [int(x) for x in os.getenv('ADMIN_ROLE_IDS', '').split(',') if x]
    MODERATOR_ROLE_IDS = [int(x) for x in os.getenv('MODERATOR_ROLE_IDS', '').split(',') if x]
    
    # Лимиты
    RATE_LIMIT_MESSAGES = int(os.getenv('RATE_LIMIT_MESSAGES', '5'))  # сообщений
    RATE_LIMIT_PERIOD = int(os.getenv('RATE_LIMIT_PERIOD', '60'))  # за период в секундах
    
    # Логирование
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'bot.log')
    
    # Эмбеддинги и цвета
    EMBED_COLOR = int(os.getenv('EMBED_COLOR', '0x00ff00'), 16)
    ERROR_COLOR = int(os.getenv('ERROR_COLOR', '0xff0000'), 16)
    WARNING_COLOR = int(os.getenv('WARNING_COLOR', '0xffaa00'), 16)
    
    @classmethod
    def validate(cls):
        """Проверка конфигурации"""
        if cls.DISCORD_TOKEN == 'YOUR_DISCORD_TOKEN_HERE':
            raise ValueError("DISCORD_TOKEN не настроен! Установите его в файле .env")
        
        if cls.MAX_CONTEXT_MESSAGES < 1:
            raise ValueError("MAX_CONTEXT_MESSAGES должен быть больше 0")
        
        if not (0 <= cls.TEMPERATURE <= 2):
            raise ValueError("TEMPERATURE должна быть между 0 и 2")
        
        return True
