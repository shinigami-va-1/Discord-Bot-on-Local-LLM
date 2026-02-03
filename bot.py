"""
Продвинутый Discord бот с интеграцией LM Studio
Основной файл запуска бота
ИСПРАВЛЕННАЯ ВЕРСИЯ с поддержкой прокси для всех компонентов
"""

import discord
from discord.ext import commands
import asyncio
import logging
from datetime import datetime
import aiohttp
from aiohttp_socks import ProxyConnector
from config import Config
from lm_studio_client import LMStudioClient
from conversation_manager import ConversationManager
from utils import setup_logging, error_handler
from web_search import WebSearchTool, SearchEnhancedLLM
from image_processing import ImageProcessor

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


class AdvancedDiscordBot(commands.Bot):
    """Основной класс бота с расширенным функционалом"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=Config.PREFIX,
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{Config.PREFIX}help | Local LLM"
            )
        )
        
        # Настройка прокси если включено
        proxy_url = None
        
        if Config.USE_PROXY and Config.PROXY_URL:
            logger.info(f"🔒 Использование прокси: {Config.PROXY_URL}")
            proxy_url = Config.PROXY_URL
            try:
                # Создаём HTTP сессию с прокси для Discord
                connector = ProxyConnector.from_url(Config.PROXY_URL)
                self.http.connector = connector
                logger.info("✅ Прокси коннектор для Discord установлен")
            except Exception as e:
                logger.error(f"❌ Ошибка создания прокси коннектора: {e}")
                logger.warning("⚠️ Продолжение без прокси")
        
        # Инициализация компонентов
        self.lm_client = LMStudioClient(Config.LM_STUDIO_URL)
        self.conversation_manager = ConversationManager(
            max_history=Config.MAX_CONTEXT_MESSAGES
        )
        
        # Инициализация веб-поиска С ПРОКСИ
        logger.info("🔧 Инициализация веб-поиска...")
        self.web_search = WebSearchTool(proxy_url=proxy_url)
        self.search_enhanced_llm = SearchEnhancedLLM(self.lm_client, self.web_search)
        logger.info("✅ Веб-поиск инициализирован")
        
        # Инициализация обработки изображений С ПРОКСИ
        logger.info("🔧 Инициализация обработки изображений...")
        self.image_processor = ImageProcessor(
            lm_client=self.lm_client,
            proxy_url=proxy_url
        )
        logger.info("✅ Обработка изображений инициализирована")
        
        self.start_time = datetime.now()
        
    async def setup_hook(self):
        """Инициализация при запуске бота"""
        logger.info("🚀 Инициализация бота...")
        
        # Загрузка расширений (cogs)
        await self.load_extension('cogs.chat_commands')
        await self.load_extension('cogs.admin_commands')
        await self.load_extension('cogs.utility_commands')
        await self.load_extension('cogs.web_image_commands')
        
        logger.info("✅ Все расширения загружены")
    
    async def on_ready(self):
        """Событие при успешном подключении бота"""
        logger.info("=" * 50)
        logger.info(f"🤖 Бот {self.user.name} успешно запущен!")
        logger.info(f"📊 ID: {self.user.id}")
        logger.info(f"🌐 Серверов: {len(self.guilds)}")
        
        # Проверка подключения к LM Studio
        if await self.lm_client.check_connection():
            logger.info("✅ Подключение к LM Studio установлено")
        else:
            logger.warning("⚠️ Не удалось подключиться к LM Studio")
        
        # Проверка прокси
        if Config.USE_PROXY:
            logger.info(f"🔒 Прокси активен: {Config.PROXY_URL}")
        
        logger.info("=" * 50)
    
    async def on_message(self, message: discord.Message):
        """Обработка сообщений"""
        # Игнорируем сообщения от ботов
        if message.author.bot:
            return
        
        # Обработка упоминаний бота
        if self.user in message.mentions and not message.mention_everyone:
            await self.handle_mention(message)
            return
        
        # Обработка команд
        await self.process_commands(message)
    
    async def handle_mention(self, message: discord.Message):
        """
        Обработка упоминаний бота для естественного диалога 
        с автоматическим поиском и анализом изображений
        """
        async with message.channel.typing():
            try:
                # Удаляем упоминание из текста
                content = message.content.replace(f'<@{self.user.id}>', '').strip()
                
                if not content:
                    await message.reply("Да, я здесь! Чем могу помочь?")
                    return
                
                # Проверяем наличие изображений
                image_url = None
                image_data = None
                
                # Проверяем вложения в сообщении
                if message.attachments:
                    for attachment in message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            image_url = attachment.url
                            logger.info(f"🖼️ Обнаружено изображение: {image_url}")
                            image_data = await self.image_processor.download_image(image_url)
                            if image_data:
                                logger.info(f"✅ Изображение загружено ({len(image_data)} байт)")
                            else:
                                logger.error("❌ Не удалось загрузить изображение")
                            break
                
                # Если изображение не найдено, проверяем ссылку на сообщение
                if not image_url and message.reference:
                    try:
                        referenced_msg = await message.channel.fetch_message(message.reference.message_id)
                        if referenced_msg.attachments:
                            for attachment in referenced_msg.attachments:
                                if attachment.content_type and attachment.content_type.startswith('image/'):
                                    image_url = attachment.url
                                    logger.info(f"🖼️ Обнаружено изображение в ответе: {image_url}")
                                    image_data = await self.image_processor.download_image(image_url)
                                    break
                    except:
                        pass
                
                # Получаем историю разговора
                conversation_history = await self.conversation_manager.get_history(
                    message.channel.id,
                    message.author.id
                )
                
                # Если есть изображение - анализируем его
                if image_data:
                    logger.info(f"🔍 Запускаю анализ изображения для пользователя {message.author}")
                    
                    # Анализируем изображение
                    image_analysis = await self.image_processor.analyze_image_with_llm(
                        image_data,
                        prompt=f"Пользователь спрашивает: {content}\nОпиши изображение и ответь на вопрос пользователя.",
                        resize=True
                    )
                    
                    logger.info(f"✅ Анализ изображения выполнен")
                    
                    # Формируем расширенный контекст
                    enhanced_content = (
                        f"{content}\n\n"
                        f"[Информация об изображении: {image_analysis}]"
                    )
                    
                    response = await self.lm_client.generate_response(
                        user_message=enhanced_content,
                        conversation_history=conversation_history,
                        system_prompt=Config.SYSTEM_PROMPT
                    )
                
                # Если изображения нет - используем веб-поиск при необходимости
                else:
                    logger.info(f"💬 Обработка текстового запроса с автоматическим веб-поиском")
                    
                    # Используем SearchEnhancedLLM для автоматического поиска
                    response = await self.search_enhanced_llm.generate_with_search(
                        user_message=content,
                        conversation_history=conversation_history,
                        system_prompt=Config.SYSTEM_PROMPT,
                        auto_search=True  # Автоматически определяем необходимость поиска
                    )
                
                # Сохраняем в историю
                await self.conversation_manager.add_message(
                    channel_id=message.channel.id,
                    user_id=message.author.id,
                    user_message=content,
                    bot_response=response
                )
                
                # Отправляем ответ (разбиваем на части если слишком длинный)
                await self.send_long_message(message.channel, response, reference=message)
                
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке упоминания: {e}", exc_info=True)
                await message.reply(
                    "Произошла ошибка при обработке вашего сообщения. "
                    "Пожалуйста, попробуйте позже."
                )
    
    async def send_long_message(
        self,
        channel: discord.TextChannel,
        content: str,
        reference: discord.Message = None
    ):
        """Отправка длинных сообщений с разбивкой"""
        max_length = 2000
        
        if len(content) <= max_length:
            if reference:
                await reference.reply(content)
            else:
                await channel.send(content)
            return
        
        # Разбиваем на части
        parts = []
        while content:
            if len(content) <= max_length:
                parts.append(content)
                break
            
            # Ищем последний перенос строки или пробел
            split_pos = content.rfind('\n', 0, max_length)
            if split_pos == -1:
                split_pos = content.rfind(' ', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            
            parts.append(content[:split_pos])
            content = content[split_pos:].lstrip()
        
        # Отправляем части
        for i, part in enumerate(parts):
            if i == 0 and reference:
                await reference.reply(part)
            else:
                await channel.send(part)
            await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями
    
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Глобальная обработка ошибок команд"""
        await error_handler(ctx, error)
    
    async def close(self):
        """Закрытие ресурсов при остановке бота"""
        logger.info("🔄 Закрытие соединений...")
        
        # Закрываем сессии
        if hasattr(self, 'web_search'):
            await self.web_search.close()
        
        if hasattr(self, 'image_processor'):
            await self.image_processor.close()
        
        await super().close()
        logger.info("✅ Все соединения закрыты")


async def main():
    """Главная функция запуска бота"""
    bot = AdvancedDiscordBot()
    
    try:
        async with bot:
            await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал остановки...")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("👋 Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
