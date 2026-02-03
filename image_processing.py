"""
Модуль для обработки и анализа изображений в Discord
Исправлена версия с поддержкой LM Studio vision моделей
"""

import aiohttp
from aiohttp_socks import ProxyConnector
import logging
import base64
import io
from typing import Optional, Dict, List
from PIL import Image
import json

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Обработчик изображений для Discord бота"""
    
    def __init__(self, lm_client=None, proxy_url: str = None):
        """
        Инициализация процессора изображений
        
        Args:
            lm_client: Клиент LM Studio (для моделей с поддержкой vision)
            proxy_url: URL прокси для обхода блокировок
        """
        self.lm_client = lm_client
        self.proxy_url = proxy_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.max_image_size = 5 * 1024 * 1024  # 5 MB
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание сессии с прокси"""
        if self.session is None or self.session.closed:
            # Создаём сессию с прокси если указан
            if self.proxy_url:
                try:
                    connector = ProxyConnector.from_url(self.proxy_url)
                    self.session = aiohttp.ClientSession(connector=connector)
                    logger.info(f"ImageProcessor: Используется прокси {self.proxy_url}")
                except Exception as e:
                    logger.warning(f"ImageProcessor: Не удалось создать прокси коннектор: {e}")
                    self.session = aiohttp.ClientSession()
            else:
                self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def download_image(self, url: str) -> Optional[bytes]:
        """
        Скачивание изображения по URL
        
        Args:
            url: URL изображения
            
        Returns:
            Байты изображения или None
        """
        try:
            session = await self._get_session()
            
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    logger.error(f"Ошибка скачивания изображения: {response.status}")
                    return None
                
                # Проверка размера
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > self.max_image_size:
                    logger.error(f"Изображение слишком большое: {content_length} bytes")
                    return None
                
                image_data = await response.read()
                
                if len(image_data) > self.max_image_size:
                    logger.error(f"Изображение слишком большое: {len(image_data)} bytes")
                    return None
                
                return image_data
                
        except Exception as e:
            logger.error(f"Ошибка скачивания изображения: {e}", exc_info=True)
            return None
    
    def get_image_info(self, image_data: bytes) -> Dict[str, any]:
        """
        Получение информации об изображении
        
        Args:
            image_data: Байты изображения
            
        Returns:
            Словарь с информацией об изображении
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            
            return {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'width': image.width,
                'height': image.height,
                'file_size': len(image_data),
                'has_transparency': image.mode in ('RGBA', 'LA', 'P')
            }
            
        except Exception as e:
            logger.error(f"Ошибка анализа изображения: {e}")
            return {}
    
    def resize_image(
        self,
        image_data: bytes,
        max_width: int = 1024,
        max_height: int = 1024,
        quality: int = 85
    ) -> Optional[bytes]:
        """
        Изменение размера изображения
        
        Args:
            image_data: Исходное изображение
            max_width: Максимальная ширина
            max_height: Максимальная высота
            quality: Качество сжатия (для JPEG)
            
        Returns:
            Байты измененного изображения или None
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Вычисляем новый размер с сохранением пропорций
            ratio = min(max_width / image.width, max_height / image.height)
            
            if ratio < 1:
                new_size = (int(image.width * ratio), int(image.height * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Сохраняем в буфер
            output = io.BytesIO()
            
            # Определяем формат для сохранения
            format_to_save = image.format if image.format else 'PNG'
            if format_to_save == 'JPEG':
                image.save(output, format=format_to_save, quality=quality, optimize=True)
            else:
                image.save(output, format=format_to_save, optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка изменения размера: {e}")
            return None
    
    def encode_image_base64(self, image_data: bytes) -> str:
        """
        Кодирование изображения в base64
        
        Args:
            image_data: Байты изображения
            
        Returns:
            Base64 строка
        """
        return base64.b64encode(image_data).decode('utf-8')
    
    async def analyze_image_with_llm(
        self,
        image_data: bytes,
        prompt: str = "Опиши это изображение подробно",
        resize: bool = True
    ) -> str:
        """
        Анализ изображения с помощью LLM
        
        Args:
            image_data: Байты изображения
            prompt: Промпт для анализа
            resize: Изменить размер перед отправкой
            
        Returns:
            Описание изображения
        """
        if not self.lm_client:
            return "LLM клиент не настроен для анализа изображений."
        
        try:
            # Изменяем размер для экономии токенов
            if resize:
                processed_image = self.resize_image(image_data, max_width=512, max_height=512)
                if processed_image:
                    image_data = processed_image
            
            # Кодируем в base64
            image_base64 = self.encode_image_base64(image_data)
            
            # Пробуем разные методы анализа
            try:
                # Способ 1: Пробуем vision API (LLaVA, BakLLaVA и другие vision модели)
                response = await self._analyze_with_vision_api(image_base64, prompt)
                return response
            except Exception as vision_error:
                logger.warning(f"Vision API недоступен: {vision_error}")
                
                try:
                    # Способ 2: Пробуем как обычный текстовый запрос с описанием
                    response = await self._analyze_with_text_description(image_data, prompt)
                    return response
                except Exception as text_error:
                    logger.warning(f"Текстовый анализ недоступен: {text_error}")
                    
                    # Способ 3: Базовая информация об изображении
                    return await self._analyze_without_vision(image_data, prompt)
                
        except Exception as e:
            logger.error(f"Ошибка анализа изображения: {e}", exc_info=True)
            return "Не удалось проанализировать изображение."
    
    async def _analyze_with_vision_api(
        self,
        image_base64: str,
        prompt: str
    ) -> str:
        """
        Анализ через vision API (OpenAI-compatible для LM Studio)
        
        Работает с моделями типа: LLaVA, BakLLaVA, и другими multimodal моделями
        """
        session = await self._get_session()
        
        # Получаем название модели из клиента или используем дефолтное
        model_name = "local-model"
        if hasattr(self.lm_client, 'model'):
            model_name = self.lm_client.model
        
        # Формат для OpenAI-compatible API с vision
        payload = {
            "model": model_name,  # Используем актуальное имя модели
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        # Используем LM Studio endpoint
        endpoint = self.lm_client.base_url.rstrip('/') + '/chat/completions'
        
        logger.info(f"Отправка запроса vision к {endpoint} с моделью {model_name}")
        
        async with session.post(
            endpoint,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Vision API error {response.status}: {error_text}")
            
            data = await response.json()
            
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                logger.info("Vision анализ выполнен успешно")
                return content
            else:
                raise Exception("Неожиданный формат ответа от vision API")
    
    async def _analyze_with_text_description(
        self,
        image_data: bytes,
        prompt: str
    ) -> str:
        """
        Альтернативный метод: генерация текста с описанием характеристик изображения
        """
        info = self.get_image_info(image_data)
        
        # Формируем детальное описание изображения
        description = f"""Изображение со следующими характеристиками:
- Формат: {info.get('format', 'Неизвестно')}
- Размер: {info.get('width', 0)}x{info.get('height', 0)} пикселей
- Размер файла: {info.get('file_size', 0) / 1024:.2f} KB
- Цветовой режим: {info.get('mode', 'Неизвестно')}
"""
        
        if info.get('has_transparency'):
            description += "- Изображение содержит прозрачность\n"
        
        # Определяем ориентацию
        if info.get('width', 0) > info.get('height', 0):
            description += "- Ориентация: Горизонтальная (альбомная)\n"
        elif info.get('width', 0) < info.get('height', 0):
            description += "- Ориентация: Вертикальная (портретная)\n"
        else:
            description += "- Ориентация: Квадратная\n"
        
        # Просим LLM сгенерировать ответ на основе этой информации
        enhanced_prompt = f"""{description}

Запрос пользователя: {prompt}

Пожалуйста, ответь на запрос пользователя, учитывая предоставленную информацию об изображении. 
Если запрос требует визуального анализа содержимого (что именно изображено), честно скажи, 
что для этого нужна модель с поддержкой vision, но предостави всю техническую информацию, которая доступна."""
        
        # Используем обычный LLM запрос
        response = await self.lm_client.generate_response(
            user_message=enhanced_prompt,
            system_prompt="Ты помощник для анализа изображений. Предоставляй точную информацию на основе данных."
        )
        
        return response
    
    async def _analyze_without_vision(
        self,
        image_data: bytes,
        prompt: str
    ) -> str:
        """
        Базовый анализ изображения без vision модели
        Возвращает только техническую информацию
        """
        info = self.get_image_info(image_data)
        
        analysis = f"""📊 Техническая информация об изображении:

• Формат: {info.get('format', 'Неизвестно')}
• Размер: {info.get('width', 0)}x{info.get('height', 0)} пикселей
• Размер файла: {info.get('file_size', 0) / 1024:.2f} KB
• Цветовой режим: {info.get('mode', 'Неизвестно')}
"""
        
        if info.get('has_transparency'):
            analysis += "• Прозрачность: Да\n"
        
        # Определяем ориентацию
        if info.get('width', 0) > info.get('height', 0):
            analysis += "• Ориентация: Горизонтальная (альбомная)\n"
        elif info.get('width', 0) < info.get('height', 0):
            analysis += "• Ориентация: Вертикальная (портретная)\n"
        else:
            analysis += "• Ориентация: Квадратная\n"
        
        analysis += """
⚠️ Примечание: Для полного анализа содержимого изображения требуется модель с поддержкой vision (например, LLaVA или BakLLaVA).

💡 Чтобы включить анализ содержимого:
1. Загрузите vision модель в LM Studio (например, llava-v1.6-vicuna-7b)
2. Запустите её в LM Studio
3. Попробуйте команду снова
"""
        
        return analysis
    
    def create_image_grid(
        self,
        images: List[bytes],
        grid_size: tuple = None,
        padding: int = 10
    ) -> Optional[bytes]:
        """
        Создание сетки из нескольких изображений
        
        Args:
            images: Список изображений в байтах
            grid_size: Размер сетки (ширина, высота), auto если None
            padding: Отступ между изображениями
            
        Returns:
            Байты объединенного изображения
        """
        try:
            if not images:
                return None
            
            # Открываем все изображения
            pil_images = [Image.open(io.BytesIO(img)) for img in images]
            
            # Определяем размер сетки
            if grid_size is None:
                import math
                count = len(pil_images)
                cols = math.ceil(math.sqrt(count))
                rows = math.ceil(count / cols)
                grid_size = (cols, rows)
            
            cols, rows = grid_size
            
            # Находим максимальный размер для стандартизации
            max_width = max(img.width for img in pil_images)
            max_height = max(img.height for img in pil_images)
            
            # Создаем холст
            canvas_width = cols * max_width + (cols + 1) * padding
            canvas_height = rows * max_height + (rows + 1) * padding
            
            canvas = Image.new('RGB', (canvas_width, canvas_height), color='white')
            
            # Размещаем изображения
            for i, img in enumerate(pil_images):
                row = i // cols
                col = i % cols
                
                x = col * (max_width + padding) + padding
                y = row * (max_height + padding) + padding
                
                # Центрируем изображение если оно меньше
                x_offset = (max_width - img.width) // 2
                y_offset = (max_height - img.height) // 2
                
                canvas.paste(img, (x + x_offset, y + y_offset))
            
            # Сохраняем результат
            output = io.BytesIO()
            canvas.save(output, format='PNG', optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка создания сетки изображений: {e}")
            return None
    
    def apply_filter(
        self,
        image_data: bytes,
        filter_type: str = 'grayscale'
    ) -> Optional[bytes]:
        """
        Применение фильтра к изображению
        
        Args:
            image_data: Исходное изображение
            filter_type: Тип фильтра (grayscale, blur, sharpen, etc.)
            
        Returns:
            Обработанное изображение
        """
        try:
            from PIL import ImageFilter, ImageEnhance
            
            image = Image.open(io.BytesIO(image_data))
            
            if filter_type == 'grayscale':
                image = image.convert('L')
            elif filter_type == 'blur':
                image = image.filter(ImageFilter.BLUR)
            elif filter_type == 'sharpen':
                image = image.filter(ImageFilter.SHARPEN)
            elif filter_type == 'edge':
                image = image.filter(ImageFilter.FIND_EDGES)
            elif filter_type == 'emboss':
                image = image.filter(ImageFilter.EMBOSS)
            elif filter_type == 'brightness':
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(1.5)
            elif filter_type == 'contrast':
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)
            else:
                return None
            
            # Сохраняем результат
            output = io.BytesIO()
            image.save(output, format='PNG', optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка применения фильтра: {e}")
            return None
