#!/usr/bin/env python3
"""
Скрипт запуска Discord бота с проверками
"""

import os
import sys
import asyncio
import logging

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from bot import main


def check_requirements():
    """Проверка установленных зависимостей"""
    missing = []
    
    try:
        import discord
    except ImportError:
        missing.append('discord.py')
    
    try:
        import aiohttp
    except ImportError:
        missing.append('aiohttp')
    
    try:
        from dotenv import load_dotenv
    except ImportError:
        missing.append('python-dotenv')
    
    if missing:
        print("❌ Отсутствуют зависимости:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\nУстановите их командой:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True


def check_env_file():
    """Проверка наличия .env файла"""
    if not os.path.exists('.env'):
        print("⚠️  Файл .env не найден!")
        print("\n1. Скопируйте .env.example в .env:")
        print("   cp .env.example .env")
        print("\n2. Отредактируйте .env и укажите:")
        print("   - DISCORD_TOKEN (токен вашего бота)")
        print("   - LM_STUDIO_URL (URL LM Studio, обычно http://localhost:1234/v1)")
        print("   - LM_STUDIO_MODEL (название модели)")
        print()
        return False
    
    return True


def check_config():
    """Проверка конфигурации"""
    try:
        Config.validate()
        return True
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\nПроверьте файл .env")
        return False


def check_lm_studio():
    """Предупреждение о LM Studio"""
    print("\n⚠️  Убедитесь что LM Studio запущен:")
    print("   1. Откройте LM Studio")
    print("   2. Перейдите на вкладку 'Local Server'")
    print("   3. Нажмите 'Start Server'")
    print(f"   4. Проверьте что сервер работает на {Config.LM_STUDIO_URL}")
    print()


def print_banner():
    """Вывод приветственного баннера"""
    banner = """
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     🤖 Discord Bot with LM Studio Integration 🤖        ║
║                                                          ║
║           Продвинутый AI-ассистент для Discord          ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_info():
    """Вывод информации о боте"""
    print("📋 Конфигурация:")
    print(f"   Префикс команд: {Config.PREFIX}")
    print(f"   LM Studio URL: {Config.LM_STUDIO_URL}")
    print(f"   Модель: {Config.LM_STUDIO_MODEL}")
    print(f"   Температура: {Config.TEMPERATURE}")
    print(f"   Макс. токенов: {Config.MAX_TOKENS}")
    print(f"   Размер контекста: {Config.MAX_CONTEXT_MESSAGES} сообщений")
    print()


def run_checks():
    """Запуск всех проверок"""
    print("🔍 Проверка системы...\n")
    
    checks = [
        ("Зависимости", check_requirements),
        (".env файл", check_env_file),
        ("Конфигурация", check_config),
    ]
    
    for name, check_func in checks:
        print(f"Проверка {name}...", end=" ")
        if check_func():
            print("✅")
        else:
            print("❌")
            return False
    
    print()
    return True


def main_wrapper():
    """Обертка для запуска с проверками"""
    print_banner()
    
    # Запускаем проверки
    if not run_checks():
        print("\n❌ Проверки не пройдены. Исправьте ошибки и попробуйте снова.")
        sys.exit(1)
    
    # Выводим информацию
    print_info()
    
    # Предупреждение о LM Studio
    check_lm_studio()
    
    # Запускаем бота
    print("🚀 Запуск бота...\n")
    print("=" * 60)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Получен сигнал остановки...")
        print("👋 Бот остановлен. До встречи!")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main_wrapper()
