"""
Клиент для взаимодействия с LM Studio API
"""

import aiohttp
import logging
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)


class LMStudioClient:
    """Клиент для работы с LM Studio через OpenAI-совместимое API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.chat_endpoint = f"{self.base_url}/chat/completions"
        self.models_endpoint = f"{self.base_url}/models"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание сессии"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def check_connection(self) -> bool:
        """Проверка подключения к LM Studio"""
        try:
            session = await self._get_session()
            async with session.get(
                self.models_endpoint,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Ошибка подключения к LM Studio: {e}")
            return False
    
    async def get_available_models(self) -> List[str]:
        """Получение списка доступных моделей"""
        try:
            session = await self._get_session()
            async with session.get(self.models_endpoint) as response:
                if response.status == 200:
                    data = await response.json()
                    return [model['id'] for model in data.get('data', [])]
                return []
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return []
    
    async def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        top_p: float = None,
        stream: bool = False
    ) -> str:
        """
        Генерация ответа через LM Studio
        
        Args:
            user_message: Сообщение пользователя
            conversation_history: История разговора
            system_prompt: Системный промпт
            temperature: Температура генерации
            max_tokens: Максимум токенов
            top_p: Top-p sampling
            stream: Потоковая генерация
            
        Returns:
            Сгенерированный ответ
        """
        try:
            # Формируем сообщения
            messages = []
            
            # Добавляем системный промпт
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            # Добавляем историю
            if conversation_history:
                messages.extend(conversation_history)
            
            # Добавляем текущее сообщение
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Параметры запроса
            payload = {
                "model": Config.LM_STUDIO_MODEL,
                "messages": messages,
                "temperature": temperature or Config.TEMPERATURE,
                "max_tokens": max_tokens or Config.MAX_TOKENS,
                "top_p": top_p or Config.TOP_P,
                "stream": stream
            }
            
            session = await self._get_session()
            
            if stream:
                return await self._generate_stream(session, payload)
            else:
                return await self._generate_sync(session, payload)
                
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}", exc_info=True)
            raise
    
    async def _generate_sync(
        self,
        session: aiohttp.ClientSession,
        payload: dict
    ) -> str:
        """Синхронная генерация"""
        async with session.post(
            self.chat_endpoint,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Ошибка API: {response.status} - {error_text}")
            
            data = await response.json()
            
            # Извлекаем ответ
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            else:
                raise Exception("Неожиданный формат ответа от API")
    
    async def _generate_stream(
        self,
        session: aiohttp.ClientSession,
        payload: dict
    ) -> str:
        """Потоковая генерация (для будущей реализации)"""
        # TODO: Реализовать потоковую генерацию
        payload['stream'] = False
        return await self._generate_sync(session, payload)
    
    async def generate_with_context(
        self,
        user_message: str,
        context: str,
        question_type: str = "general"
    ) -> str:
        """
        Генерация с дополнительным контекстом
        
        Args:
            user_message: Вопрос пользователя
            context: Дополнительный контекст
            question_type: Тип вопроса (general, code, creative, etc.)
        """
        enhanced_prompt = self._build_contextual_prompt(
            user_message,
            context,
            question_type
        )
        
        return await self.generate_response(
            user_message=enhanced_prompt,
            system_prompt=Config.SYSTEM_PROMPT
        )
    
    def _build_contextual_prompt(
        self,
        message: str,
        context: str,
        question_type: str
    ) -> str:
        """Построение промпта с контекстом"""
        prompts = {
            "code": f"Контекст: {context}\n\nВопрос по коду: {message}",
            "creative": f"Творческий контекст: {context}\n\nЗадание: {message}",
            "analysis": f"Данные для анализа: {context}\n\nВопрос: {message}",
            "general": f"Дополнительная информация: {context}\n\n{message}"
        }
        
        return prompts.get(question_type, prompts["general"])
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Генерация эмбеддинга текста (если поддерживается)
        
        Args:
            text: Текст для эмбеддинга
            
        Returns:
            Вектор эмбеддинга
        """
        # TODO: Реализовать если LM Studio поддерживает эмбеддинги
        raise NotImplementedError("Эмбеддинги пока не поддерживаются")
