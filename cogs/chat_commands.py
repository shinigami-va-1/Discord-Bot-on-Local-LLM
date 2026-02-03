"""
Cog с командами для работы с чатом и AI
"""

import discord
from discord.ext import commands
import logging
from typing import Optional
from utils import create_embed, create_error_embed, create_success_embed
from config import Config

logger = logging.getLogger(__name__)


class ChatCommands(commands.Cog):
    """Команды для взаимодействия с AI"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(
        name="ask",
        aliases=["ai", "chat"],
        help="Задать вопрос AI ассистенту"
    )
    async def ask(self, ctx: commands.Context, *, question: str):
        """
        Задать вопрос AI
        
        Использование: !ask <ваш вопрос>
        """
        async with ctx.typing():
            try:
                # Получаем историю
                history = await self.bot.conversation_manager.get_history(
                    ctx.channel.id,
                    ctx.author.id
                )
                
                # Генерируем ответ
                response = await self.bot.lm_client.generate_response(
                    user_message=question,
                    conversation_history=history,
                    system_prompt=Config.SYSTEM_PROMPT
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
                logger.error(f"Ошибка в команде ask: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось сгенерировать ответ. Проверьте подключение к LM Studio."
                    )
                )
    
    @commands.command(
        name="clear",
        aliases=["reset"],
        help="Очистить историю разговора"
    )
    async def clear_history(self, ctx: commands.Context):
        """Очистка истории разговора с AI"""
        await self.bot.conversation_manager.clear_history(
            ctx.channel.id,
            ctx.author.id
        )
        
        await ctx.send(
            embed=create_success_embed(
                "История очищена",
                "Ваша история разговора была успешно очищена."
            )
        )
    
    @commands.command(
        name="history",
        aliases=["conv"],
        help="Показать историю разговора"
    )
    async def show_history(self, ctx: commands.Context):
        """Показать текущую историю разговора"""
        history = await self.bot.conversation_manager.get_history(
            ctx.channel.id,
            ctx.author.id
        )
        
        if not history:
            await ctx.send(
                embed=create_embed(
                    "История разговора",
                    "История пуста. Начните разговор используя команду `!ask` или упомянув бота."
                )
            )
            return
        
        # Форматируем историю
        formatted = []
        for i, msg in enumerate(history, 1):
            role = "👤 Вы" if msg['role'] == 'user' else "🤖 Бот"
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            formatted.append(f"**{i}. {role}:** {content}")
        
        embed = create_embed(
            "История разговора",
            "\n\n".join(formatted),
            footer=f"Всего сообщений: {len(history)}"
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(
        name="export",
        help="Экспортировать историю разговора"
    )
    async def export_history(self, ctx: commands.Context):
        """Экспорт истории разговора в файл"""
        export = await self.bot.conversation_manager.export_conversation(
            ctx.channel.id,
            ctx.author.id
        )
        
        if export == "История разговора пуста.":
            await ctx.send(
                embed=create_embed(
                    "Экспорт истории",
                    "История разговора пуста."
                )
            )
            return
        
        # Создаем файл
        file = discord.File(
            fp=export.encode('utf-8'),
            filename=f"conversation_{ctx.author.id}_{ctx.channel.id}.txt"
        )
        
        await ctx.send(
            "Вот ваша история разговора:",
            file=file
        )
    
    @commands.command(
        name="summarize",
        aliases=["summary"],
        help="Получить краткое содержание разговора"
    )
    async def summarize_conversation(self, ctx: commands.Context):
        """Получить AI-сводку разговора"""
        history = await self.bot.conversation_manager.get_history(
            ctx.channel.id,
            ctx.author.id
        )
        
        if not history:
            await ctx.send(
                embed=create_error_embed(
                    "Нет истории",
                    "История разговора пуста."
                )
            )
            return
        
        async with ctx.typing():
            try:
                # Формируем промпт для суммаризации
                conversation_text = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in history
                ])
                
                summary_prompt = (
                    f"Пожалуйста, создай краткое содержание следующего разговора:\n\n"
                    f"{conversation_text}\n\n"
                    f"Выдели основные темы и важные моменты."
                )
                
                summary = await self.bot.lm_client.generate_response(
                    user_message=summary_prompt,
                    system_prompt="Ты эксперт по анализу и суммаризации текстов."
                )
                
                embed = create_embed(
                    "📝 Краткое содержание разговора",
                    summary
                )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Ошибка суммаризации: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось создать краткое содержание."
                    )
                )
    
    @commands.command(
        name="code",
        help="Попросить AI сгенерировать код"
    )
    async def generate_code(self, ctx: commands.Context, *, description: str):
        """
        Генерация кода по описанию
        
        Использование: !code <описание задачи>
        """
        async with ctx.typing():
            try:
                code_prompt = (
                    f"Создай код для следующей задачи:\n{description}\n\n"
                    f"Предоставь чистый, документированный код с комментариями."
                )
                
                response = await self.bot.lm_client.generate_response(
                    user_message=code_prompt,
                    system_prompt="Ты опытный программист. Создавай качественный, читаемый код."
                )
                
                # Отправляем в code block
                code_message = f"```python\n{response}\n```" if "```" not in response else response
                
                await self.bot.send_long_message(ctx.channel, code_message, reference=ctx.message)
                
            except Exception as e:
                logger.error(f"Ошибка генерации кода: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось сгенерировать код."
                    )
                )
    
    @commands.command(
        name="translate",
        help="Перевести текст"
    )
    async def translate(
        self,
        ctx: commands.Context,
        target_language: str,
        *,
        text: str
    ):
        """
        Перевод текста на другой язык
        
        Использование: !translate <язык> <текст>
        Пример: !translate english Привет, как дела?
        """
        async with ctx.typing():
            try:
                translate_prompt = (
                    f"Переведи следующий текст на {target_language}:\n\n{text}"
                )
                
                translation = await self.bot.lm_client.generate_response(
                    user_message=translate_prompt,
                    system_prompt="Ты профессиональный переводчик. Делай точные и естественные переводы."
                )
                
                embed = create_embed(
                    f"Перевод на {target_language}",
                    translation
                )
                embed.add_field(
                    name="Оригинал",
                    value=text[:1024],
                    inline=False
                )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Ошибка перевода: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось выполнить перевод."
                    )
                )
    
    @commands.command(
        name="temperature",
        help="Изменить температуру генерации (креативность)"
    )
    async def set_temperature(self, ctx: commands.Context, temp: float):
        """
        Установка температуры генерации
        
        Использование: !temperature <0.0-2.0>
        Низкие значения = более предсказуемо
        Высокие значения = более креативно
        """
        if not 0 <= temp <= 2:
            await ctx.send(
                embed=create_error_embed(
                    "Неверное значение",
                    "Температура должна быть между 0.0 и 2.0"
                )
            )
            return
        
        # Сохраняем в конфиг (это можно расширить для пользовательских настроек)
        Config.TEMPERATURE = temp
        
        await ctx.send(
            embed=create_success_embed(
                "Температура изменена",
                f"Новая температура генерации: {temp}\n"
                f"{'Более предсказуемые ответы' if temp < 0.5 else 'Более креативные ответы'}"
            )
        )


async def setup(bot):
    """Функция установки cog"""
    await bot.add_cog(ChatCommands(bot))
