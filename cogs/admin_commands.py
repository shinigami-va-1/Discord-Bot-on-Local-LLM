"""
Cog с административными командами
"""

import discord
from discord.ext import commands
import logging
from utils import (
    create_embed,
    create_error_embed,
    create_success_embed,
    is_admin,
    is_moderator,
    get_confirmation
)
from config import Config

logger = logging.getLogger(__name__)


class AdminCommands(commands.Cog):
    """Административные команды"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_check(self, ctx: commands.Context) -> bool:
        """Проверка прав для всех команд в этом cog"""
        if not is_admin(ctx):
            await ctx.send(
                embed=create_error_embed(
                    "Недостаточно прав",
                    "Эта команда доступна только администраторам."
                )
            )
            return False
        return True
    
    @commands.command(
        name="clearall",
        help="[ADMIN] Очистить всю историю в канале"
    )
    async def clear_all_history(self, ctx: commands.Context):
        """Очистка всей истории разговоров в канале"""
        # Запрашиваем подтверждение
        confirmed = await get_confirmation(
            ctx,
            "Вы уверены, что хотите очистить всю историю разговоров в этом канале?"
        )
        
        if not confirmed:
            await ctx.send("Операция отменена.")
            return
        
        await self.bot.conversation_manager.clear_history(ctx.channel.id)
        
        await ctx.send(
            embed=create_success_embed(
                "История очищена",
                "Вся история разговоров в этом канале была удалена."
            )
        )
    
    @commands.command(
        name="stats",
        help="[ADMIN] Статистика бота"
    )
    async def stats_bot(self, ctx: commands.Context):
        """Показать статистику работы бота"""
        stats = self.bot.conversation_manager.get_stats()
        conv_count = await self.bot.conversation_manager.get_all_conversations_count()
        
        # Время работы
        uptime = (datetime.now() - self.bot.start_time).total_seconds()
        uptime_str = format_uptime(uptime)
        
        # Информация о LM Studio
        models = await self.bot.lm_client.get_available_models()
        lm_status = "✅ Подключено" if await self.bot.lm_client.check_connection() else "❌ Отключено"
        
        embed = create_embed(
            "📊 Статистика бота",
            f"**Время работы:** {uptime_str}\n"
            f"**Серверов:** {len(self.bot.guilds)}\n"
            f"**Пользователей:** {len(self.bot.users)}\n"
        )
        
        embed.add_field(
            name="💬 Разговоры",
            value=(
                f"Активных: {conv_count}\n"
                f"Всего сообщений: {stats['total_messages']}\n"
                f"Каналов: {stats['channels_with_conversations']}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🤖 LM Studio",
            value=(
                f"Статус: {lm_status}\n"
                f"URL: {Config.LM_STUDIO_URL}\n"
                f"Модель: {Config.LM_STUDIO_MODEL}\n"
                f"Доступно моделей: {len(models)}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="⚙️ Параметры",
            value=(
                f"Температура: {Config.TEMPERATURE}\n"
                f"Max токенов: {Config.MAX_TOKENS}\n"
                f"Max история: {Config.MAX_CONTEXT_MESSAGES}"
            ),
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(
        name="models",
        help="[ADMIN] Список доступных моделей в LM Studio"
    )
    async def list_models(self, ctx: commands.Context):
        """Показать список доступных моделей"""
        async with ctx.typing():
            try:
                models = await self.bot.lm_client.get_available_models()
                
                if not models:
                    await ctx.send(
                        embed=create_error_embed(
                            "Модели не найдены",
                            "Не удалось получить список моделей. Проверьте подключение к LM Studio."
                        )
                    )
                    return
                
                models_list = "\n".join([f"• `{model}`" for model in models])
                current = f"\n\n**Текущая модель:** `{Config.LM_STUDIO_MODEL}`"
                
                embed = create_embed(
                    "🤖 Доступные модели",
                    models_list + current
                )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Ошибка получения моделей: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка",
                        "Не удалось получить список моделей."
                    )
                )
    
    @commands.command(
        name="setmodel",
        help="[ADMIN] Изменить используемую модель"
    )
    async def set_model(self, ctx: commands.Context, *, model_name: str):
        """Установка модели для генерации"""
        models = await self.bot.lm_client.get_available_models()
        
        if model_name not in models:
            await ctx.send(
                embed=create_error_embed(
                    "Модель не найдена",
                    f"Модель `{model_name}` не найдена в LM Studio.\n"
                    f"Используйте `{Config.PREFIX}models` для просмотра доступных моделей."
                )
            )
            return
        
        Config.LM_STUDIO_MODEL = model_name
        
        await ctx.send(
            embed=create_success_embed(
                "Модель изменена",
                f"Теперь используется модель: `{model_name}`"
            )
        )
    
    @commands.command(
        name="setsystem",
        help="[ADMIN] Изменить системный промпт"
    )
    async def set_system_prompt(self, ctx: commands.Context, *, prompt: str):
        """Установка системного промпта"""
        Config.SYSTEM_PROMPT = prompt
        
        await ctx.send(
            embed=create_success_embed(
                "Системный промпт изменен",
                f"Новый системный промпт:\n```{prompt[:500]}...```"
            )
        )
    
    @commands.command(
        name="reload",
        help="[ADMIN] Перезагрузить расширения"
    )
    async def reload_extensions(self, ctx: commands.Context):
        """Перезагрузка всех cog расширений"""
        async with ctx.typing():
            try:
                extensions = [
                    'cogs.chat_commands',
                    'cogs.admin_commands',
                    'cogs.utility_commands'
                ]
                
                for ext in extensions:
                    await self.bot.reload_extension(ext)
                
                await ctx.send(
                    embed=create_success_embed(
                        "Расширения перезагружены",
                        f"Успешно перезагружено {len(extensions)} расширений."
                    )
                )
                
                logger.info(f"Расширения перезагружены пользователем {ctx.author}")
                
            except Exception as e:
                logger.error(f"Ошибка перезагрузки: {e}", exc_info=True)
                await ctx.send(
                    embed=create_error_embed(
                        "Ошибка перезагрузки",
                        f"Не удалось перезагрузить расширения: {str(e)}"
                    )
                )
    
    @commands.command(
        name="announce",
        help="[ADMIN] Отправить объявление во все каналы"
    )
    async def announce(self, ctx: commands.Context, *, message: str):
        """Отправка объявления во все текстовые каналы"""
        confirmed = await get_confirmation(
            ctx,
            f"Отправить следующее объявление во все каналы?\n\n{message[:200]}"
        )
        
        if not confirmed:
            await ctx.send("Объявление отменено.")
            return
        
        embed = create_embed(
            "📢 Объявление",
            message
        )
        embed.set_footer(text=f"От: {ctx.author.display_name}")
        
        sent_count = 0
        failed_count = 0
        
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                try:
                    await channel.send(embed=embed)
                    sent_count += 1
                    break  # Отправляем только в первый доступный канал
                except discord.Forbidden:
                    failed_count += 1
                    continue
        
        await ctx.send(
            embed=create_success_embed(
                "Объявление отправлено",
                f"Успешно: {sent_count}\nОшибок: {failed_count}"
            )
        )
    
    @commands.command(
        name="cleanup",
        help="[ADMIN] Очистка старых разговоров"
    )
    async def cleanup_conversations(self, ctx: commands.Context):
        """Очистка неактивных разговоров"""
        await self.bot.conversation_manager.cleanup_old_conversations(
            Config.CONTEXT_TIMEOUT
        )
        
        await ctx.send(
            embed=create_success_embed(
                "Очистка выполнена",
                f"Старые разговоры (неактивные более {Config.CONTEXT_TIMEOUT}с) были удалены."
            )
        )


async def setup(bot):
    """Функция установки cog"""
    await bot.add_cog(AdminCommands(bot))


from datetime import datetime
from utils import format_uptime
