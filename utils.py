"""
Утилиты для бота
"""

import logging
import sys
import traceback
from datetime import datetime
from typing import Optional
import discord
from discord.ext import commands
from config import Config


def setup_logging():
    """Настройка системы логирования"""
    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Консольный handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # Файловый handler
    file_handler = logging.FileHandler(
        Config.LOG_FILE,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Настройка root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Уменьшаем уровень логирования для discord.py
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)


async def error_handler(ctx: commands.Context, error: Exception):
    """
    Централизованная обработка ошибок
    
    Args:
        ctx: Контекст команды
        error: Ошибка
    """
    logger = logging.getLogger(__name__)
    
    # Игнорируем ошибки команды не найдена
    if isinstance(error, commands.CommandNotFound):
        return
    
    # Ошибка отсутствия разрешений
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            embed=create_error_embed(
                "Недостаточно прав",
                "У вас нет прав для использования этой команды."
            )
        )
        return
    
    # Ошибка неправильных аргументов
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            embed=create_error_embed(
                "Неверные аргументы",
                f"Отсутствует обязательный аргумент: `{error.param.name}`\n"
                f"Используйте `{Config.PREFIX}help {ctx.command.name}` для справки."
            )
        )
        return
    
    # Ошибка cooldown
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            embed=create_error_embed(
                "Слишком быстро!",
                f"Подождите {error.retry_after:.1f} секунд перед повторным использованием."
            )
        )
        return
    
    # Остальные ошибки
    logger.error(
        f"Ошибка в команде {ctx.command}: {error}",
        exc_info=error
    )
    
    await ctx.send(
        embed=create_error_embed(
            "Произошла ошибка",
            "Внутренняя ошибка при выполнении команды. "
            "Администраторы уведомлены."
        )
    )


def create_embed(
    title: str,
    description: str,
    color: int = None,
    fields: list = None,
    footer: str = None,
    thumbnail: str = None,
    image: str = None
) -> discord.Embed:
    """
    Создание форматированного embed
    
    Args:
        title: Заголовок
        description: Описание
        color: Цвет
        fields: Список полей [(name, value, inline), ...]
        footer: Текст футера
        thumbnail: URL миниатюры
        image: URL изображения
        
    Returns:
        Discord embed объект
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or Config.EMBED_COLOR,
        timestamp=datetime.utcnow()
    )
    
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    
    if footer:
        embed.set_footer(text=footer)
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    if image:
        embed.set_image(url=image)
    
    return embed


def create_error_embed(title: str, description: str) -> discord.Embed:
    """Создание embed для ошибок"""
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=Config.ERROR_COLOR,
        timestamp=datetime.utcnow()
    )


def create_success_embed(title: str, description: str) -> discord.Embed:
    """Создание embed для успешных операций"""
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=Config.EMBED_COLOR,
        timestamp=datetime.utcnow()
    )


def create_warning_embed(title: str, description: str) -> discord.Embed:
    """Создание embed для предупреждений"""
    return discord.Embed(
        title=f"⚠️ {title}",
        description=description,
        color=Config.WARNING_COLOR,
        timestamp=datetime.utcnow()
    )


def format_uptime(seconds: int) -> str:
    """
    Форматирование времени работы
    
    Args:
        seconds: Количество секунд
        
    Returns:
        Форматированная строка
    """
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}д")
    if hours > 0:
        parts.append(f"{hours}ч")
    if minutes > 0:
        parts.append(f"{minutes}м")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}с")
    
    return " ".join(parts)


def truncate_text(text: str, max_length: int = 2000) -> str:
    """
    Обрезка текста с добавлением многоточия
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        
    Returns:
        Обрезанный текст
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def is_admin(ctx: commands.Context) -> bool:
    """
    Проверка прав администратора
    
    Args:
        ctx: Контекст команды
        
    Returns:
        True если пользователь админ
    """
    if ctx.author.guild_permissions.administrator:
        return True
    
    if Config.ADMIN_ROLE_IDS:
        user_role_ids = [role.id for role in ctx.author.roles]
        return any(role_id in Config.ADMIN_ROLE_IDS for role_id in user_role_ids)
    
    return False


def is_moderator(ctx: commands.Context) -> bool:
    """
    Проверка прав модератора
    
    Args:
        ctx: Контекст команды
        
    Returns:
        True если пользователь модератор
    """
    if is_admin(ctx):
        return True
    
    if Config.MODERATOR_ROLE_IDS:
        user_role_ids = [role.id for role in ctx.author.roles]
        return any(role_id in Config.MODERATOR_ROLE_IDS for role_id in user_role_ids)
    
    return False


class ConfirmationView(discord.ui.View):
    """View для подтверждения действий"""
    
    def __init__(self, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
    
    @discord.ui.button(label="Да", style=discord.ButtonStyle.success)
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        self.value = True
        self.stop()
        await interaction.response.defer()
    
    @discord.ui.button(label="Нет", style=discord.ButtonStyle.danger)
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        self.value = False
        self.stop()
        await interaction.response.defer()


async def get_confirmation(
    ctx: commands.Context,
    message: str,
    timeout: int = 30
) -> bool:
    """
    Получение подтверждения от пользователя
    
    Args:
        ctx: Контекст команды
        message: Сообщение с вопросом
        timeout: Таймаут в секундах
        
    Returns:
        True если подтверждено
    """
    view = ConfirmationView(timeout=timeout)
    
    embed = create_embed(
        "Подтверждение",
        message,
        color=Config.WARNING_COLOR
    )
    
    msg = await ctx.send(embed=embed, view=view)
    await view.wait()
    
    await msg.delete()
    
    return view.value or False
