"""
Cog с командами для веб-поиска и обработки изображений
"""

import discord
from discord.ext import commands
import logging
from typing import Optional
from utils import create_embed, create_error_embed, create_success_embed
from config import Config
import io

logger = logging.getLogger(__name__)


class WebAndImageCommands(commands.Cog):
    """Команды для веб-поиска и работы с изображениями"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(
        name="search",
        aliases=["поиск", "найди"],
        help="Поиск информации в интернете"
    )
    async def web_search(self, ctx: commands.Context, *, query: str):
        """
        Поиск информации в интернете через веб-поиск
        
        Использование: !search <запрос>
        Пример: !search последние новости ИИ
        """
        async with ctx.typing():
            try:
                if not hasattr(self.bot, 'web_search'):
                    await ctx.send(
                        embed=create_error_embed(
                            "Функция недоступна",
                            "Веб-поиск не настроен. Обратитесь к администратору."
                        )
                    )
                    return
                
                # Выполняем поиск
                results = await self.bot.web_search.search(query, max_results=5)
                
                if not results:
                    await ctx.send(
                        embed=create_error_embed(
                            "Ничего не найдено",
                            f"По запросу '{query}' не найдено результатов."
                        )
                    )
                    return
                
                # Создаем embed с результатами
                embed = create_embed(
                    f"🔍 Результаты поиска: {query}",
                    f"Найдено {len(results)} результатов"
                )
                
                for i, result in enumerate(results, 1):
                    title = result.get('title', 'Без названия')[:256]
                    snippet = result.get('snippet', 'Нет описания')[:1024]
                    url = result.get('url', '')
                    source = result.get('source', 'Неизвестно')
                    
                    field_value = f"{snippet}\n"
                    if url:
                        field_value += f"[Перейти к источнику]({url})\n"
                    field_value += f"*Источник: {source}*"
                    
                    embed.add_field(
                        name=f"{i}. {title}",
                        value=field_value[:1024],
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Ошибка веб-поиска: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось выполнить поиск. Попробуйте позже."
                    )
                )
    
    @commands.command(
        name="searchai",
        aliases=["поискai", "aisearch"],
        help="Поиск с AI анализом результатов"
    )
    async def search_with_ai(self, ctx: commands.Context, *, query: str):
        """
        Поиск информации с последующим анализом через AI
        
        Использование: !searchai <запрос>
        Пример: !searchai что такое квантовые компьютеры
        """
        async with ctx.typing():
            try:
                if not hasattr(self.bot, 'search_enhanced_llm'):
                    await ctx.send(
                        embed=create_error_embed(
                            "Функция недоступна",
                            "AI поиск не настроен."
                        )
                    )
                    return
                
                # Поиск и суммаризация
                summary = await self.bot.search_enhanced_llm.search_and_summarize(query)
                
                # Отправляем результат
                embed = create_embed(
                    f"🤖 AI Поиск: {query}",
                    summary
                )
                embed.set_footer(text="Информация получена из веб-источников и обработана AI")
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Ошибка AI поиска: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось выполнить AI поиск."
                    )
                )
    
    @commands.command(
        name="askweb",
        aliases=["вопросweb"],
        help="Задать вопрос AI с доступом к интернету"
    )
    async def ask_with_web(self, ctx: commands.Context, *, question: str):
        """
        Задать вопрос AI с автоматическим веб-поиском
        
        Использование: !askweb <вопрос>
        Пример: !askweb кто выиграл последний чемпионат мира по футболу
        """
        async with ctx.typing():
            try:
                if not hasattr(self.bot, 'search_enhanced_llm'):
                    # Fallback к обычному ask
                    await ctx.invoke(self.bot.get_command('ask'), question=question)
                    return
                
                # Получаем историю
                history = await self.bot.conversation_manager.get_history(
                    ctx.channel.id,
                    ctx.author.id
                )
                
                # Генерируем ответ с веб-поиском
                response = await self.bot.search_enhanced_llm.generate_with_search(
                    user_message=question,
                    conversation_history=history,
                    system_prompt=Config.SYSTEM_PROMPT,
                    auto_search=True
                )
                
                # Сохраняем в историю
                await self.bot.conversation_manager.add_message(
                    channel_id=ctx.channel.id,
                    user_id=ctx.author.id,
                    user_message=question,
                    bot_response=response
                )
                
                # Отправляем ответ
                await self.bot.send_long_message(ctx.channel, response, reference=ctx.message)
                
            except Exception as e:
                logger.error(f"Ошибка askweb: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось обработать вопрос с веб-поиском."
                    )
                )
    
    @commands.command(
        name="imageinfo",
        aliases=["imginfo", "инфоизобр"],
        help="Получить информацию об изображении"
    )
    async def image_info(self, ctx: commands.Context):
        """
        Получение информации о прикрепленном изображении
        
        Использование: !imageinfo (прикрепите изображение)
        """
        async with ctx.typing():
            try:
                if not hasattr(self.bot, 'image_processor'):
                    await ctx.send(
                        embed=create_error_embed(
                            "Функция недоступна",
                            "Обработка изображений не настроена."
                        )
                    )
                    return
                
                # Проверяем наличие изображения
                image_url = None
                
                # Проверяем вложения
                if ctx.message.attachments:
                    for attachment in ctx.message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            image_url = attachment.url
                            break
                
                if not image_url:
                    await ctx.send(
                        embed=create_error_embed(
                            "Изображение не найдено",
                            "Пожалуйста, прикрепите изображение к команде."
                        )
                    )
                    return
                
                # Скачиваем изображение
                image_data = await self.bot.image_processor.download_image(image_url)
                
                if not image_data:
                    await ctx.send(
                        embed=create_error_embed(
                            "Ошибка",
                            "Не удалось скачать изображение."
                        )
                    )
                    return
                
                # Получаем информацию
                info = self.bot.image_processor.get_image_info(image_data)
                
                # Создаем embed
                embed = create_embed(
                    "📸 Информация об изображении",
                    "Детали прикрепленного изображения"
                )
                
                embed.add_field(name="Формат", value=info.get('format', 'Н/Д'), inline=True)
                embed.add_field(name="Размер", value=f"{info.get('width', 0)}x{info.get('height', 0)}", inline=True)
                embed.add_field(
                    name="Размер файла",
                    value=f"{info.get('file_size', 0) / 1024:.2f} KB",
                    inline=True
                )
                embed.add_field(name="Цветовой режим", value=info.get('mode', 'Н/Д'), inline=True)
                embed.add_field(
                    name="Прозрачность",
                    value="Да" if info.get('has_transparency') else "Нет",
                    inline=True
                )
                
                # Определяем ориентацию
                width = info.get('width', 0)
                height = info.get('height', 0)
                if width > height:
                    orientation = "Горизонтальная"
                elif width < height:
                    orientation = "Вертикальная"
                else:
                    orientation = "Квадратная"
                
                embed.add_field(name="Ориентация", value=orientation, inline=True)
                
                embed.set_thumbnail(url=image_url)
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Ошибка imageinfo: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось получить информацию об изображении."
                    )
                )
    
    @commands.command(
        name="analyze",
        aliases=["analyzeimage", "анализ"],
        help="Анализ изображения с помощью AI"
    )
    async def analyze_image(self, ctx: commands.Context, *, prompt: str = None):
        """
        Анализ изображения с помощью AI
        
        Использование: !analyze [описание] (прикрепите изображение)
        Пример: !analyze что изображено на картинке?
        """
        async with ctx.typing():
            try:
                if not hasattr(self.bot, 'image_processor'):
                    await ctx.send(
                        embed=create_error_embed(
                            "Функция недоступна",
                            "Обработка изображений не настроена."
                        )
                    )
                    return
                
                # Проверяем наличие изображения
                image_url = None
                
                if ctx.message.attachments:
                    for attachment in ctx.message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            image_url = attachment.url
                            break
                
                # Проверяем ссылку на сообщение
                if not image_url and ctx.message.reference:
                    referenced_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                    if referenced_msg.attachments:
                        for attachment in referenced_msg.attachments:
                            if attachment.content_type and attachment.content_type.startswith('image/'):
                                image_url = attachment.url
                                break
                
                if not image_url:
                    await ctx.send(
                        embed=create_error_embed(
                            "Изображение не найдено",
                            "Прикрепите изображение или ответьте на сообщение с изображением."
                        )
                    )
                    return
                
                # Скачиваем изображение
                image_data = await self.bot.image_processor.download_image(image_url)
                
                if not image_data:
                    await ctx.send(
                        embed=create_error_embed(
                            "Ошибка",
                            "Не удалось скачать изображение."
                        )
                    )
                    return
                
                # Анализируем
                if not prompt:
                    prompt = "Опиши это изображение подробно. Что на нем изображено?"
                
                analysis = await self.bot.image_processor.analyze_image_with_llm(
                    image_data,
                    prompt=prompt,
                    resize=True
                )
                
                # Отправляем результат
                embed = create_embed(
                    "🔍 Анализ изображения",
                    analysis
                )
                embed.set_thumbnail(url=image_url)
                
                if prompt != "Опиши это изображение подробно. Что на нем изображено?":
                    embed.set_footer(text=f"Запрос: {prompt}")
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Ошибка analyze: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось проанализировать изображение."
                    )
                )
    
    @commands.command(
        name="filter",
        aliases=["фильтр"],
        help="Применить фильтр к изображению"
    )
    async def apply_filter(self, ctx: commands.Context, filter_type: str = "grayscale"):
        """
        Применение фильтра к изображению
        
        Использование: !filter <тип> (прикрепите изображение)
        Доступные фильтры: grayscale, blur, sharpen, edge, emboss, brightness, contrast
        """
        async with ctx.typing():
            try:
                if not hasattr(self.bot, 'image_processor'):
                    await ctx.send(
                        embed=create_error_embed(
                            "Функция недоступна",
                            "Обработка изображений не настроена."
                        )
                    )
                    return
                
                # Проверяем наличие изображения
                image_url = None
                
                if ctx.message.attachments:
                    for attachment in ctx.message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            image_url = attachment.url
                            break
                
                if not image_url:
                    await ctx.send(
                        embed=create_error_embed(
                            "Изображение не найдено",
                            "Пожалуйста, прикрепите изображение к команде."
                        )
                    )
                    return
                
                # Скачиваем изображение
                image_data = await self.bot.image_processor.download_image(image_url)
                
                if not image_data:
                    await ctx.send(
                        embed=create_error_embed(
                            "Ошибка",
                            "Не удалось скачать изображение."
                        )
                    )
                    return
                
                # Применяем фильтр
                filtered_image = self.bot.image_processor.apply_filter(
                    image_data,
                    filter_type=filter_type
                )
                
                if not filtered_image:
                    await ctx.send(
                        embed=create_error_embed(
                            "Ошибка",
                            f"Неизвестный фильтр: {filter_type}\n"
                            f"Доступные: grayscale, blur, sharpen, edge, emboss, brightness, contrast"
                        )
                    )
                    return
                
                # Отправляем результат
                file = discord.File(
                    fp=io.BytesIO(filtered_image),
                    filename=f"filtered_{filter_type}.png"
                )
                
                embed = create_success_embed(
                    f"Фильтр применен: {filter_type}",
                    "Результат обработки изображения"
                )
                
                await ctx.send(embed=embed, file=file)
                
            except Exception as e:
                logger.error(f"Ошибка filter: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось применить фильтр."
                    )
                )
    
    @commands.command(
        name="resize",
        aliases=["изменить"],
        help="Изменить размер изображения"
    )
    async def resize_image(
        self,
        ctx: commands.Context,
        width: int = 512,
        height: int = 512
    ):
        """
        Изменение размера изображения
        
        Использование: !resize <ширина> <высота> (прикрепите изображение)
        Пример: !resize 800 600
        """
        async with ctx.typing():
            try:
                if not hasattr(self.bot, 'image_processor'):
                    await ctx.send(
                        embed=create_error_embed(
                            "Функция недоступна",
                            "Обработка изображений не настроена."
                        )
                    )
                    return
                
                # Проверяем наличие изображения
                image_url = None
                
                if ctx.message.attachments:
                    for attachment in ctx.message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            image_url = attachment.url
                            break
                
                if not image_url:
                    await ctx.send(
                        embed=create_error_embed(
                            "Изображение не найдено",
                            "Пожалуйста, прикрепите изображение к команде."
                        )
                    )
                    return
                
                # Проверяем размеры
                if width < 10 or height < 10 or width > 4096 or height > 4096:
                    await ctx.send(
                        embed=create_error_embed(
                            "Неверный размер",
                            "Размеры должны быть от 10 до 4096 пикселей."
                        )
                    )
                    return
                
                # Скачиваем изображение
                image_data = await self.bot.image_processor.download_image(image_url)
                
                if not image_data:
                    await ctx.send(
                        embed=create_error_embed(
                            "Ошибка",
                            "Не удалось скачать изображение."
                        )
                    )
                    return
                
                # Изменяем размер
                resized_image = self.bot.image_processor.resize_image(
                    image_data,
                    max_width=width,
                    max_height=height
                )
                
                if not resized_image:
                    await ctx.send(
                        embed=create_error_embed(
                            "Ошибка",
                            "Не удалось изменить размер изображения."
                        )
                    )
                    return
                
                # Отправляем результат
                file = discord.File(
                    fp=io.BytesIO(resized_image),
                    filename=f"resized_{width}x{height}.png"
                )
                
                embed = create_success_embed(
                    f"Размер изменен: {width}x{height}",
                    "Результат обработки изображения"
                )
                
                await ctx.send(embed=embed, file=file)
                
            except Exception as e:
                logger.error(f"Ошибка resize: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось изменить размер изображения."
                    )
                )


async def setup(bot):
    """Функция установки cog"""
    await bot.add_cog(WebAndImageCommands(bot))
