"""
Cog с утилитными командами
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime
import platform
import psutil
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
from utils import (
    create_embed,
    create_error_embed,
    format_uptime
)
from config import Config

logger = logging.getLogger(__name__)


class UtilityCommands(commands.Cog):
    """Утилитные команды"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_amd_gpu_info(self):
        """Получить информацию об AMD GPU (Windows)"""
        gpu_info = {}
        
        # Метод 1: Базовая информация через WMI
        try:
            import wmi
            c = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            
            # Пробуем получить данные из OpenHardwareMonitor (если запущен)
            sensors_found = False
            for sensor in c.Sensor():
                if 'GPU' in sensor.Name or 'Radeon' in sensor.Name or 'AMD' in sensor.Name:
                    sensors_found = True
                    if 'Temperature' in sensor.SensorType:
                        gpu_info['temperature'] = float(sensor.Value)
                    elif 'Load' in sensor.SensorType:
                        gpu_info['load'] = float(sensor.Value)
                    elif sensor.SensorType == 'Clock' and 'Core' in sensor.Name:
                        gpu_info['clock'] = float(sensor.Value)
            
            if sensors_found:
                logger.info("Данные GPU получены через OpenHardwareMonitor")
        except Exception as e:
            logger.debug(f"OpenHardwareMonitor недоступен: {e}")
        
        # Метод 2: Базовая информация через стандартный WMI
        try:
            import wmi
            c = wmi.WMI()
            
            for gpu in c.Win32_VideoController():
                if 'AMD' in gpu.Name or 'Radeon' in gpu.Name or 'ATI' in gpu.Name:
                    gpu_info['name'] = gpu.Name
                    
                    # Память (в байтах, конвертируем в GB)
                    if gpu.AdapterRAM and gpu.AdapterRAM > 0:
                        gpu_info['memory_total'] = gpu.AdapterRAM / (1024 ** 3)
                    
                    # Статус
                    if hasattr(gpu, 'Status'):
                        gpu_info['status'] = gpu.Status
                    
                    break
        except Exception as e:
            logger.warning(f"Ошибка при получении базовой информации через WMI: {e}")
        
        # Метод 3: Пробуем через py3nvml для AMD (если доступно)
        if not gpu_info.get('load') or not gpu_info.get('temperature'):
            try:
                # Пробуем использовать GPU-Z shared memory (если GPU-Z запущен)
                import mmap
                import struct
                
                try:
                    # GPU-Z использует shared memory с именем "GPUZShMem"
                    shm = mmap.mmap(-1, 256, "GPUZShMem", access=mmap.ACCESS_READ)
                    # Структура данных GPU-Z (упрощенная)
                    # Это не всегда работает, но можно попробовать
                    shm.close()
                except:
                    pass
            except Exception as e:
                logger.debug(f"GPU-Z shared memory недоступен: {e}")
        
        # Метод 4: Через PowerShell и Get-Counter
        if not gpu_info.get('load'):
            try:
                import subprocess
                
                # Пробуем получить загрузку GPU через PowerShell
                result = subprocess.run(
                    ['powershell', '-Command', 
                     '(Get-Counter "\\GPU Engine(*engtype_3D)\\Utilization Percentage").CounterSamples | Select-Object -First 1 | Select-Object -ExpandProperty CookedValue'],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        load = float(result.stdout.strip())
                        if load > 0:
                            gpu_info['load'] = load
                            logger.info(f"Загрузка GPU получена через PowerShell: {load}%")
                    except ValueError:
                        pass
            except Exception as e:
                logger.debug(f"Не удалось получить загрузку через PowerShell: {e}")
        
        # Если так и не получили загрузку и температуру, убираем их из вывода
        # чтобы не показывать нули
        if gpu_info.get('load') == 0.0:
            gpu_info.pop('load', None)
        if gpu_info.get('temperature') == 0.0:
            gpu_info.pop('temperature', None)
        
        return gpu_info if gpu_info else None
    
    @commands.command(
        name="ping",
        help="Проверить задержку бота"
    )
    async def ping(self, ctx: commands.Context):
        """Проверка задержки"""
        latency = round(self.bot.latency * 1000)
        
        # Определяем эмодзи в зависимости от задержки
        if latency < 100:
            emoji = "🟢"
            status = "Отлично"
        elif latency < 200:
            emoji = "🟡"
            status = "Хорошо"
        else:
            emoji = "🔴"
            status = "Плохо"
        
        embed = create_embed(
            f"{emoji} Pong!",
            f"**Задержка:** {latency}ms\n**Статус:** {status}"
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(
        name="info",
        aliases=["about", "botinfo"],
        help="Информация о боте"
    )
    async def info_bot(self, ctx: commands.Context):
        """Информация о боте"""
        uptime = (datetime.now() - self.bot.start_time).total_seconds()
        uptime_str = format_uptime(uptime)
        
        # Подключение к LM Studio
        lm_connected = await self.bot.lm_client.check_connection()
        lm_status = "✅ Подключено" if lm_connected else "❌ Не подключено"
        
        embed = discord.Embed(
            title="🤖 Информация о боте",
            description="Продвинутый Discord бот с интеграцией LM Studio",
            color=Config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📊 Статистика",
            value=(
                f"**Серверов:** {len(self.bot.guilds)}\n"
                f"**Пользователей:** {len(self.bot.users)}\n"
                f"**Каналов:** {sum(len(guild.channels) for guild in self.bot.guilds)}\n"
                f"**Время работы:** {uptime_str}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🤖 AI",
            value=(
                f"**Статус:** {lm_status}\n"
                f"**Модель:** {Config.LM_STUDIO_MODEL}\n"
                f"**Температура:** {Config.TEMPERATURE}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="⚙️ Технологии",
            value=(
                f"**Python:** {platform.python_version()}\n"
                f"**Discord.py:** {discord.__version__}\n"
                f"**Префикс:** {Config.PREFIX}"
            ),
            inline=True
        )
        
        embed.set_footer(text=f"Запрошено {ctx.author.display_name}")
        
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        await ctx.send(embed=embed)
    
    @commands.command(
        name="com_help",
        help="Показать список команд"
    )
    async def help_command(self, ctx: commands.Context, *, command: str = None):
        """Расширенная команда помощи"""
        if command:
            # Помощь по конкретной команде
            cmd = self.bot.get_command(command)
            if not cmd:
                await ctx.send(
                    embed=create_error_embed(
                        "Команда не найдена",
                        f"Команда `{command}` не существует.\n"
                        f"Используйте `{Config.PREFIX}help` для списка всех команд."
                    )
                )
                return
            
            embed = create_embed(
                f"Команда: {cmd.name}",
                cmd.help or "Описание отсутствует"
            )
            
            if cmd.aliases:
                embed.add_field(
                    name="Псевдонимы",
                    value=", ".join(f"`{alias}`" for alias in cmd.aliases),
                    inline=False
                )
            
            if cmd.signature:
                embed.add_field(
                    name="Использование",
                    value=f"`{Config.PREFIX}{cmd.name} {cmd.signature}`",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            return
        
        # Общая помощь
        embed = discord.Embed(
            title="📚 Список команд",
            description=f"Используйте `{Config.PREFIX}help <команда>` для подробной информации",
            color=Config.EMBED_COLOR
        )
        
        # Группируем команды по cog
        for cog_name, cog in self.bot.cogs.items():
            commands_list = []
            for cmd in cog.get_commands():
                if not cmd.hidden:
                    commands_list.append(f"`{cmd.name}`")
            
            if commands_list:
                embed.add_field(
                    name=cog_name.replace('Commands', ''),
                    value=" • ".join(commands_list),
                    inline=False
                )
        
        # Добавляем информацию об упоминаниях
        embed.add_field(
            name="💬 Естественный диалог",
            value=f"Упомяните бота (@{self.bot.user.name}) чтобы начать беседу!",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(
        name="server",
        aliases=["serverinfo"],
        help="Информация о сервере"
    )
    async def server_info(self, ctx: commands.Context):
        """Информация о текущем сервере"""
        guild = ctx.guild
        
        embed = discord.Embed(
            title=f"🏰 {guild.name}",
            color=Config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(
            name="📊 Основное",
            value=(
                f"**Владелец:** {guild.owner.mention}\n"
                f"**Создан:** {guild.created_at.strftime('%d.%m.%Y')}\n"
                f"**ID:** {guild.id}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="👥 Участники",
            value=(
                f"**Всего:** {guild.member_count}\n"
                f"**Людей:** {sum(1 for m in guild.members if not m.bot)}\n"
                f"**Ботов:** {sum(1 for m in guild.members if m.bot)}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📝 Каналы",
            value=(
                f"**Текстовых:** {len(guild.text_channels)}\n"
                f"**Голосовых:** {len(guild.voice_channels)}\n"
                f"**Категорий:** {len(guild.categories)}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🎭 Роли",
            value=f"**Всего:** {len(guild.roles)}",
            inline=True
        )
        
        embed.add_field(
            name="😀 Эмодзи",
            value=f"**Всего:** {len(guild.emojis)}",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(
        name="user",
        aliases=["userinfo", "profile"],
        help="Информация о пользователе"
    )
    async def user_info(self, ctx: commands.Context, member: discord.Member = None):
        """Информация о пользователе"""
        member = member or ctx.author
        
        embed = discord.Embed(
            title=f"👤 {member.display_name}",
            color=member.color or Config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(
            name="📋 Основное",
            value=(
                f"**Имя:** {member.name}\n"
                f"**ID:** {member.id}\n"
                f"**Бот:** {'Да' if member.bot else 'Нет'}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📅 Даты",
            value=(
                f"**Аккаунт создан:**\n{member.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"**Присоединился:**\n{member.joined_at.strftime('%d.%m.%Y %H:%M')}"
            ),
            inline=True
        )
        
        if len(member.roles) > 1:  # > 1 потому что @everyone
            roles = [role.mention for role in member.roles[1:][:10]]  # Первые 10 ролей
            roles_text = ", ".join(roles)
            if len(member.roles) > 11:
                roles_text += f" и еще {len(member.roles) - 11}"
            
            embed.add_field(
                name=f"🎭 Роли ({len(member.roles) - 1})",
                value=roles_text,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(
        name="avatar",
        help="Показать аватар пользователя"
    )
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        """Показать аватар пользователя в полном размере"""
        member = member or ctx.author
        
        embed = create_embed(
            f"Аватар {member.display_name}",
            ""
        )
        embed.set_image(url=member.display_avatar.url)
        
        # Добавляем ссылку на скачивание
        embed.add_field(
            name="Ссылка",
            value=f"[Открыть в полном размере]({member.display_avatar.url})",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(
        name="system",
        help="Системная информация бота"
    )
    async def system_info(self, ctx: commands.Context):
        """Показать системную информацию"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # RAM
        memory = psutil.virtual_memory()
        memory_used = memory.used / (1024 ** 3)  # GB
        memory_total = memory.total / (1024 ** 3)  # GB
        memory_percent = memory.percent
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_used = disk.used / (1024 ** 3)  # GB
        disk_total = disk.total / (1024 ** 3)  # GB
        disk_percent = disk.percent
        
        # GPU - пробуем NVIDIA через GPUtil
        gpu_info = None
        if GPU_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # Берем первый GPU
                    gpu_info = {
                        'name': gpu.name,
                        'load': gpu.load * 100,
                        'memory_used': gpu.memoryUsed / 1024,  # GB
                        'memory_total': gpu.memoryTotal / 1024,  # GB
                        'memory_percent': (gpu.memoryUsed / gpu.memoryTotal) * 100,
                        'temperature': gpu.temperature
                    }
            except Exception as e:
                logger.warning(f"Ошибка получения информации о NVIDIA GPU: {e}")
        
        # Если NVIDIA GPU не найден, пробуем AMD
        if not gpu_info:
            gpu_info = self.get_amd_gpu_info()
        
        embed = create_embed(
            "💻 Системная информация",
            ""
        )
        
        embed.add_field(
            name="🖥️ CPU",
            value=(
                f"**Использование:** {cpu_percent}%\n"
                f"**Ядер:** {cpu_count}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🧠 RAM",
            value=(
                f"**Использовано:** {memory_used:.2f}GB / {memory_total:.2f}GB\n"
                f"**Процент:** {memory_percent}%"
            ),
            inline=True
        )
        
        embed.add_field(
            name="💾 Диск",
            value=(
                f"**Использовано:** {disk_used:.2f}GB / {disk_total:.2f}GB\n"
                f"**Процент:** {disk_percent}%"
            ),
            inline=True
        )
        
        # Добавляем информацию о GPU если она доступна
        if gpu_info:
            gpu_name = gpu_info.get('name', 'Неизвестно')
            gpu_text = f"**Модель:** {gpu_name}\n"
            
            if 'load' in gpu_info:
                gpu_text += f"**Использование:** {gpu_info['load']:.1f}%\n"
            
            if 'memory_used' in gpu_info and 'memory_total' in gpu_info:
                gpu_text += f"**VRAM:** {gpu_info['memory_used']:.2f}GB / {gpu_info['memory_total']:.2f}GB\n"
                gpu_text += f"**VRAM %:** {gpu_info['memory_percent']:.1f}%\n"
            elif 'memory_percent' in gpu_info:
                gpu_text += f"**VRAM %:** {gpu_info['memory_percent']:.1f}%\n"
            
            if 'temperature' in gpu_info:
                gpu_text += f"**Температура:** {gpu_info['temperature']:.0f}°C"
            
            embed.add_field(
                name="🎮 GPU",
                value=gpu_text,
                inline=False
            )
        
        embed.add_field(
            name="🐍 Python",
            value=f"**Версия:** {platform.python_version()}",
            inline=True
        )
        
        embed.add_field(
            name="💬 Discord.py",
            value=f"**Версия:** {discord.__version__}",
            inline=True
        )
        
        await ctx.send(embed=embed)


async def setup(bot):
    """Функция установки cog"""
    await bot.add_cog(UtilityCommands(bot))
