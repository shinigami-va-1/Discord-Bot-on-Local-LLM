"""
Менеджер разговоров для управления историей и контекстом
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ConversationManager:
    """Управление историей разговоров"""
    
    def __init__(self, max_history: int = 10):
        """
        Args:
            max_history: Максимальное количество сообщений в истории
        """
        self.max_history = max_history
        
        # Структура: {channel_id: {user_id: [messages]}}
        self.conversations: Dict[int, Dict[int, List[Dict]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # Время последнего сообщения для таймаута
        self.last_activity: Dict[tuple, datetime] = {}
        
        # Глобальная статистика
        self.stats = {
            'total_messages': 0,
            'total_conversations': 0
        }
    
    async def add_message(
        self,
        channel_id: int,
        user_id: int,
        user_message: str,
        bot_response: str
    ):
        """
        Добавление сообщения в историю
        
        Args:
            channel_id: ID канала
            user_id: ID пользователя
            user_message: Сообщение пользователя
            bot_response: Ответ бота
        """
        conversation = self.conversations[channel_id][user_id]
        
        # Добавляем сообщение пользователя
        conversation.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now()
        })
        
        # Добавляем ответ бота
        conversation.append({
            "role": "assistant",
            "content": bot_response,
            "timestamp": datetime.now()
        })
        
        # Обрезаем историю если слишком длинная
        if len(conversation) > self.max_history * 2:  # *2 потому что user+assistant
            conversation[:] = conversation[-(self.max_history * 2):]
        
        # Обновляем время последней активности
        self.last_activity[(channel_id, user_id)] = datetime.now()
        
        # Обновляем статистику
        self.stats['total_messages'] += 2
    
    async def get_history(
        self,
        channel_id: int,
        user_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Получение истории разговора
        
        Args:
            channel_id: ID канала
            user_id: ID пользователя
            limit: Лимит сообщений (None = все)
            
        Returns:
            Список сообщений в формате OpenAI
        """
        conversation = self.conversations[channel_id][user_id]
        
        if not conversation:
            return []
        
        # Применяем лимит если указан
        if limit:
            conversation = conversation[-(limit * 2):]
        
        # Возвращаем без временных меток
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in conversation
        ]
    
    async def clear_history(
        self,
        channel_id: int,
        user_id: Optional[int] = None
    ):
        """
        Очистка истории разговора
        
        Args:
            channel_id: ID канала
            user_id: ID пользователя (None = все пользователи в канале)
        """
        if user_id:
            if channel_id in self.conversations:
                if user_id in self.conversations[channel_id]:
                    del self.conversations[channel_id][user_id]
                    logger.info(f"История очищена для user {user_id} в канале {channel_id}")
        else:
            if channel_id in self.conversations:
                del self.conversations[channel_id]
                logger.info(f"Вся история очищена для канала {channel_id}")
    
    async def get_conversation_summary(
        self,
        channel_id: int,
        user_id: int
    ) -> Dict:
        """
        Получение сводки о разговоре
        
        Returns:
            Словарь с информацией о разговоре
        """
        conversation = self.conversations[channel_id][user_id]
        
        if not conversation:
            return {
                'message_count': 0,
                'user_messages': 0,
                'bot_messages': 0,
                'first_message': None,
                'last_message': None
            }
        
        user_msgs = [m for m in conversation if m['role'] == 'user']
        bot_msgs = [m for m in conversation if m['role'] == 'assistant']
        
        return {
            'message_count': len(conversation),
            'user_messages': len(user_msgs),
            'bot_messages': len(bot_msgs),
            'first_message': conversation[0]['timestamp'] if conversation else None,
            'last_message': conversation[-1]['timestamp'] if conversation else None
        }
    
    async def cleanup_old_conversations(self, timeout_seconds: int = 3600):
        """
        Очистка старых неактивных разговоров
        
        Args:
            timeout_seconds: Таймаут неактивности в секундах
        """
        now = datetime.now()
        timeout = timedelta(seconds=timeout_seconds)
        
        keys_to_remove = []
        
        for key, last_time in self.last_activity.items():
            if now - last_time > timeout:
                keys_to_remove.append(key)
        
        for channel_id, user_id in keys_to_remove:
            await self.clear_history(channel_id, user_id)
            del self.last_activity[(channel_id, user_id)]
        
        if keys_to_remove:
            logger.info(f"Очищено {len(keys_to_remove)} неактивных разговоров")
    
    async def get_all_conversations_count(self) -> int:
        """Получение общего количества активных разговоров"""
        count = 0
        for channel_conversations in self.conversations.values():
            count += len(channel_conversations)
        return count
    
    async def export_conversation(
        self,
        channel_id: int,
        user_id: int
    ) -> str:
        """
        Экспорт разговора в текстовый формат
        
        Returns:
            Форматированная строка с историей разговора
        """
        conversation = self.conversations[channel_id][user_id]
        
        if not conversation:
            return "История разговора пуста."
        
        lines = ["=== История разговора ===\n"]
        
        for msg in conversation:
            timestamp = msg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            role = "Пользователь" if msg['role'] == 'user' else "Бот"
            lines.append(f"[{timestamp}] {role}:")
            lines.append(f"{msg['content']}\n")
        
        return "\n".join(lines)
    
    def get_stats(self) -> Dict:
        """Получение общей статистики"""
        return {
            **self.stats,
            'active_conversations': len(self.last_activity),
            'channels_with_conversations': len(self.conversations)
        }


class RateLimiter:
    """Ограничитель частоты запросов"""
    
    def __init__(self, max_requests: int, period: int):
        """
        Args:
            max_requests: Максимум запросов
            period: Период в секундах
        """
        self.max_requests = max_requests
        self.period = period
        self.requests: Dict[int, List[datetime]] = defaultdict(list)
    
    async def check_rate_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        """
        Проверка лимита запросов
        
        Returns:
            (разрешено, секунд до сброса)
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.period)
        
        # Удаляем старые запросы
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if req_time > cutoff
        ]
        
        # Проверяем лимит
        if len(self.requests[user_id]) >= self.max_requests:
            oldest = self.requests[user_id][0]
            wait_time = int((oldest + timedelta(seconds=self.period) - now).total_seconds())
            return False, wait_time
        
        # Добавляем текущий запрос
        self.requests[user_id].append(now)
        return True, None
    
    async def reset_user(self, user_id: int):
        """Сброс лимита для пользователя"""
        if user_id in self.requests:
            del self.requests[user_id]
