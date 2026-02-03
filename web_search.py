"""
Модуль для веб-поиска и предоставления актуальной информации LLM
Исправлена версия с поддержкой прокси
"""

import aiohttp
from aiohttp_socks import ProxyConnector
import logging
from typing import List, Dict, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Инструмент веб-поиска для LLM с поддержкой прокси"""
    
    def __init__(self, proxy_url: str = None):
        """
        Инициализация веб-поиска
        
        Args:
            proxy_url: URL прокси для обхода блокировок
        """
        self.session: Optional[aiohttp.ClientSession] = None
        self.proxy_url = proxy_url
        self.search_api = "https://api.duckduckgo.com/"
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание сессии с прокси"""
        if self.session is None or self.session.closed:
            # Создаём сессию с прокси если указан
            if self.proxy_url:
                try:
                    connector = ProxyConnector.from_url(self.proxy_url)
                    self.session = aiohttp.ClientSession(connector=connector)
                    logger.info(f"WebSearchTool: Используется прокси {self.proxy_url}")
                except Exception as e:
                    logger.warning(f"WebSearchTool: Не удалось создать прокси коннектор: {e}")
                    self.session = aiohttp.ClientSession()
            else:
                self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def search_duckduckgo(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, str]]:
        """
        Поиск через DuckDuckGo Instant Answer API
        
        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов
            
        Returns:
            Список результатов поиска
        """
        try:
            session = await self._get_session()
            
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            logger.info(f"Выполняется поиск DuckDuckGo: '{query}'")
            
            async with session.get(
                self.search_api,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                # DuckDuckGo может возвращать 202 (Accepted) - это нормально
                if response.status == 202:
                    logger.warning(f"DuckDuckGo вернул 202 (запрос принят, но нет мгновенных результатов)")
                    return []
                
                if response.status != 200:
                    logger.error(f"DuckDuckGo API error: {response.status}")
                    return []
                
                data = await response.json()
                results = []
                
                # Обработка основного ответа
                if data.get('AbstractText'):
                    results.append({
                        'title': data.get('Heading', 'DuckDuckGo Answer'),
                        'snippet': data['AbstractText'],
                        'url': data.get('AbstractURL', ''),
                        'source': data.get('AbstractSource', 'DuckDuckGo')
                    })
                
                # Обработка связанных тем
                for topic in data.get('RelatedTopics', [])[:max_results - len(results)]:
                    if isinstance(topic, dict) and 'Text' in topic:
                        results.append({
                            'title': topic.get('FirstURL', '').split('/')[-1].replace('_', ' '),
                            'snippet': topic.get('Text', ''),
                            'url': topic.get('FirstURL', ''),
                            'source': 'DuckDuckGo'
                        })
                
                logger.info(f"DuckDuckGo вернул {len(results)} результатов")
                return results[:max_results]
                
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при поиске DuckDuckGo")
            return []
        except Exception as e:
            logger.error(f"Ошибка поиска DuckDuckGo: {e}", exc_info=True)
            return []
    
    async def search_duckduckgo_html(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, str]]:
        """
        Альтернативный поиск через HTML версию DuckDuckGo
        Используется когда Instant Answer API не работает
        
        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов
            
        Returns:
            Список результатов поиска
        """
        try:
            session = await self._get_session()
            
            params = {
                'q': query,
                'kl': 'ru-ru'  # Регион
            }
            
            logger.info(f"Выполняется HTML поиск DuckDuckGo: '{query}'")
            
            async with session.get(
                "https://html.duckduckgo.com/html/",
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as response:
                if response.status != 200:
                    logger.error(f"DuckDuckGo HTML error: {response.status}")
                    return []
                
                html = await response.text()
                
                # Парсинг результатов с BeautifulSoup для лучшего качества
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    results = []
                    
                    # Ищем все результаты поиска
                    result_divs = soup.find_all('div', class_='result')
                    
                    for div in result_divs[:max_results]:
                        try:
                            # Заголовок и ссылка
                            title_link = div.find('a', class_='result__a')
                            if not title_link:
                                continue
                            
                            title = title_link.get_text(strip=True)
                            href = title_link.get('href', '')
                            
                            # Получаем реальный URL (DuckDuckGo использует редиректы)
                            if href.startswith('//duckduckgo.com/l/?'):
                                import urllib.parse
                                parsed = urllib.parse.urlparse(href)
                                params = urllib.parse.parse_qs(parsed.query)
                                url = params.get('uddg', [''])[0]
                                if not url:
                                    continue
                                # Декодируем URL
                                url = urllib.parse.unquote(url)
                            else:
                                url = href
                            
                            # Описание (snippet)
                            snippet_elem = div.find('a', class_='result__snippet')
                            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                            
                            if not snippet:
                                snippet = f'Результат поиска для "{query}"'
                            
                            # Извлекаем домен для источника
                            try:
                                from urllib.parse import urlparse
                                domain = urlparse(url).netloc
                                source = domain.replace('www.', '')
                            except:
                                source = 'Web'
                            
                            results.append({
                                'title': title,
                                'snippet': snippet[:300],  # Ограничиваем длину
                                'url': url,
                                'source': source
                            })
                            
                        except Exception as e:
                            logger.debug(f"Ошибка парсинга результата: {e}")
                            continue
                    
                    logger.info(f"DuckDuckGo HTML вернул {len(results)} результатов с разных сайтов")
                    return results
                    
                except ImportError:
                    # Fallback на regex если BeautifulSoup не установлен
                    logger.warning("BeautifulSoup не установлен, используем простой парсинг")
                    import re
                    results = []
                    
                    pattern = r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
                    matches = re.findall(pattern, html)
                    
                    for url, title in matches[:max_results]:
                        if url and title:
                            if url.startswith('//duckduckgo.com/l/?'):
                                continue
                            
                            results.append({
                                'title': title.strip(),
                                'snippet': f'Результат поиска для "{query}"',
                                'url': url,
                                'source': 'Web'
                            })
                    
                    logger.info(f"DuckDuckGo HTML вернул {len(results)} результатов")
                    return results
                
        except Exception as e:
            logger.error(f"Ошибка HTML поиска DuckDuckGo: {e}", exc_info=True)
            return []
    
    async def search_wikipedia(self, query: str, lang: str = 'en') -> Optional[Dict[str, str]]:
        """
        Поиск в Wikipedia через API
        
        Args:
            query: Поисковый запрос
            lang: Язык Wikipedia (en, ru, etc.)
            
        Returns:
            Результат поиска из Wikipedia или None
        """
        try:
            session = await self._get_session()
            
            logger.info(f"Поиск в Wikipedia ({lang}): '{query}'")
            
            # Поиск статьи
            search_url = f"https://{lang}.wikipedia.org/w/api.php"
            search_params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': query,
                'srlimit': 1
            }
            
            async with session.get(
                search_url,
                params=search_params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    return None
                
                search_data = await response.json()
                search_results = search_data.get('query', {}).get('search', [])
                
                if not search_results:
                    logger.info("Wikipedia: ничего не найдено")
                    return None
                
                page_id = search_results[0]['pageid']
                title = search_results[0]['title']
            
            # Получение содержимого
            content_params = {
                'action': 'query',
                'format': 'json',
                'prop': 'extracts',
                'exintro': True,
                'explaintext': True,
                'pageids': page_id
            }
            
            async with session.get(
                search_url,
                params=content_params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    return None
                
                content_data = await response.json()
                pages = content_data.get('query', {}).get('pages', {})
                
                if str(page_id) in pages:
                    extract = pages[str(page_id)].get('extract', '')
                    
                    logger.info(f"Wikipedia: найдена статья '{title}'")
                    
                    return {
                        'title': title,
                        'snippet': extract[:500] + '...' if len(extract) > 500 else extract,
                        'url': f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        'source': f'Wikipedia ({lang.upper()})'
                    }
                
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при поиске Wikipedia")
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска Wikipedia: {e}", exc_info=True)
            return None
    
    async def get_current_time_info(self) -> Dict[str, str]:
        """
        Получение текущей даты и времени
        
        Returns:
            Информация о текущем времени
        """
        now = datetime.now()
        
        return {
            'title': 'Текущее время',
            'snippet': (
                f"Дата: {now.strftime('%d.%m.%Y')}\n"
                f"Время: {now.strftime('%H:%M:%S')}\n"
                f"День недели: {now.strftime('%A')}"
            ),
            'url': '',
            'source': 'System'
        }
    
    async def fetch_url_content(
        self,
        url: str,
        max_length: int = 2000
    ) -> Optional[str]:
        """
        Получение содержимого страницы по URL с умным извлечением текста
        
        Args:
            url: URL страницы
            max_length: Максимальная длина текста
            
        Returns:
            Текст содержимого или None
        """
        try:
            session = await self._get_session()
            
            logger.info(f"Загрузка содержимого URL: {url}")
            
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as response:
                if response.status != 200:
                    logger.warning(f"URL вернул статус {response.status}")
                    return None
                
                # Получаем текст
                html = await response.text()
                
                # Пробуем использовать BeautifulSoup для умного извлечения
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Удаляем скрипты и стили
                    for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                        script.decompose()
                    
                    # Ищем основной контент
                    main_content = soup.find('article') or soup.find('main') or soup.find('body')
                    
                    if main_content:
                        # Извлекаем текст с параграфов
                        paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3', 'li'])
                        text_parts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                        clean_text = '\n'.join(text_parts)
                    else:
                        clean_text = soup.get_text(separator='\n', strip=True)
                    
                    # Убираем множественные переносы строк
                    import re
                    clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)
                    clean_text = re.sub(r' +', ' ', clean_text)
                    
                    logger.info(f"Извлечено {len(clean_text)} символов текста")
                    return clean_text[:max_length]
                    
                except ImportError:
                    # Fallback на простую очистку HTML
                    logger.warning("BeautifulSoup не установлен, используем простую очистку")
                    import re
                    clean_text = re.sub(r'<[^>]+>', '', html)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    return clean_text[:max_length]
                
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при загрузке URL")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения содержимого URL: {e}")
            return None
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        include_wikipedia: bool = True
    ) -> List[Dict[str, str]]:
        """
        Комбинированный поиск через несколько источников
        
        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов
            include_wikipedia: Включить поиск в Wikipedia
            
        Returns:
            Список результатов поиска
        """
        all_results = []
        
        # Поиск в DuckDuckGo (Instant Answer API)
        ddg_results = await self.search_duckduckgo(query, max_results)
        all_results.extend(ddg_results)
        
        # Если DuckDuckGo API не дал результатов (например, 202), пробуем HTML версию
        if len(all_results) == 0:
            logger.info("API не дал результатов, пробуем HTML версию DuckDuckGo")
            ddg_html_results = await self.search_duckduckgo_html(query, max_results)
            all_results.extend(ddg_html_results)
        
        # Если DuckDuckGo не дал результатов или дал мало, пробуем Wikipedia
        if include_wikipedia and len(all_results) < max_results:
            # Определяем язык запроса (простая эвристика)
            is_russian = any(ord('а') <= ord(char.lower()) <= ord('я') for char in query)
            
            if is_russian:
                # Сначала пробуем русскую Wikipedia
                logger.info("Запрос на русском, пробуем ru.wikipedia.org")
                wiki_result = await self.search_wikipedia(query, lang='ru')
                if wiki_result:
                    all_results.append(wiki_result)
                
                # Если всё ещё мало результатов, пробуем английскую
                if len(all_results) < max_results:
                    wiki_result_en = await self.search_wikipedia(query, lang='en')
                    if wiki_result_en:
                        all_results.append(wiki_result_en)
            else:
                # Для английского запроса - только английская Wikipedia
                wiki_result = await self.search_wikipedia(query, lang='en')
                if wiki_result:
                    all_results.append(wiki_result)
        
        logger.info(f"Всего найдено результатов: {len(all_results)}")
        return all_results[:max_results]
    
    async def search_with_content(
        self,
        query: str,
        max_results: int = 3,
        fetch_content: bool = True
    ) -> List[Dict[str, str]]:
        """
        Расширенный поиск с загрузкой контента найденных страниц
        Даёт более полную информацию для LLM
        
        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов
            fetch_content: Загружать ли полный контент страниц
            
        Returns:
            Список результатов с полным контентом
        """
        # Сначала делаем обычный поиск
        results = await self.search(query, max_results=max_results)
        
        if not fetch_content or not results:
            return results
        
        # Загружаем контент для каждого результата
        logger.info(f"Загрузка полного контента для {len(results)} результатов...")
        
        enhanced_results = []
        for result in results:
            url = result.get('url', '')
            
            # Пропускаем если нет URL или это Wikipedia (уже есть snippet)
            if not url or 'wikipedia.org' in url:
                enhanced_results.append(result)
                continue
            
            # Загружаем контент
            content = await self.fetch_url_content(url, max_length=1500)
            
            if content:
                # Добавляем полный контент к результату
                result['full_content'] = content
                result['snippet'] = content[:500] + '...' if len(content) > 500 else content
                logger.info(f"✅ Загружен контент с {result.get('source', 'сайта')}")
            
            enhanced_results.append(result)
        
        logger.info(f"Подготовлено {len(enhanced_results)} результатов с контентом")
        return enhanced_results
    
    def format_search_results(
        self,
        results: List[Dict[str, str]],
        query: str
    ) -> str:
        """
        Форматирование результатов поиска для передачи в LLM
        
        Args:
            results: Список результатов
            query: Исходный запрос
            
        Returns:
            Отформатированная строка с результатами
        """
        if not results:
            return f"Поиск по запросу '{query}' не дал результатов."
        
        # Группируем результаты по источникам
        sources_count = {}
        for result in results:
            source = result.get('source', 'Unknown')
            sources_count[source] = sources_count.get(source, 0) + 1
        
        formatted = f"🔍 Результаты поиска по запросу '{query}':\n"
        formatted += f"Найдено: {len(results)} результатов с {len(sources_count)} источников\n\n"
        
        for i, result in enumerate(results, 1):
            title = result.get('title', 'Без названия')
            source = result.get('source', 'Неизвестный источник')
            url = result.get('url', '')
            snippet = result.get('snippet', 'Нет описания')
            
            formatted += f"═══ Результат #{i} ═══\n"
            formatted += f"📌 {title}\n"
            formatted += f"🌐 Источник: {source}\n"
            
            if url:
                formatted += f"🔗 URL: {url}\n"
            
            formatted += f"📄 Описание:\n{snippet}\n"
            
            # Если есть полный контент, добавляем его
            if 'full_content' in result and result['full_content']:
                formatted += f"\n📖 Полный текст (фрагмент):\n{result['full_content'][:800]}...\n"
            
            formatted += "\n"
        
        formatted += f"💡 Используй информацию из этих {len(results)} источников для ответа.\n"
        
        return formatted


class SearchEnhancedLLM:
    """
    Обертка для LLM с возможностью веб-поиска
    Позволяет LLM получать актуальную информацию из интернета
    """
    
    def __init__(self, lm_client, web_search_tool: WebSearchTool):
        self.lm_client = lm_client
        self.web_search = web_search_tool
    
    async def generate_with_search(
        self,
        user_message: str,
        conversation_history: List[Dict] = None,
        system_prompt: str = None,
        auto_search: bool = True
    ) -> str:
        """
        Генерация ответа с автоматическим веб-поиском при необходимости
        
        Args:
            user_message: Сообщение пользователя
            conversation_history: История разговора
            system_prompt: Системный промпт
            auto_search: Автоматически определять необходимость поиска
            
        Returns:
            Ответ LLM с учетом данных из интернета
        """
        # Определяем, нужен ли поиск
        search_keywords = [
            # Вопросительные слова
            'что такое', 'кто такой', 'кто такая', 'где находится', 'когда',
            'какой', 'какая', 'какие', 'сколько', 'почему', 'зачем',
            
            # Запросы актуальной информации
            'последние новости', 'актуальная информация', 'новости',
            'последние события', 'что нового', 'свежие новости',
            'сегодня', 'вчера', 'недавно', 'в этом году', 'в этом месяце',
            
            # Явные запросы поиска
            'поиск', 'найди', 'найди информацию', 'расскажи о', 
            'информация о', 'узнай', 'проверь', 'погугли',
            
            # Вопросы о текущем состоянии
            'кто сейчас', 'кто является', 'кто занимает', 'кто возглавляет',
            'текущий', 'сейчас', 'на данный момент', 'в настоящее время',
            'актуальный', 'современный',
            
            # Вопросы требующие фактов
            'факты о', 'статистика', 'данные о', 'цифры',
            'победитель', 'лидер', 'чемпион', 'рекорд',
            
            # События и персоналии
            'биография', 'история', 'достижения', 'карьера'
        ]
        
        # Проверяем на английском
        english_keywords = [
            'what is', 'who is', 'where is', 'when', 'how',
            'latest news', 'current', 'today', 'recent',
            'search for', 'find', 'tell me about', 'information about',
            'who won', 'winner', 'champion', 'latest'
        ]
        
        message_lower = user_message.lower()
        
        needs_search = auto_search and (
            any(keyword in message_lower for keyword in search_keywords) or
            any(keyword in message_lower for keyword in english_keywords)
        )
        
        # Дополнительная проверка: если в сообщении есть вопросительный знак и оно короткое
        # (вероятно, простой вопрос требующий факта)
        if not needs_search and '?' in user_message and len(user_message.split()) < 15:
            # Проверяем, начинается ли с вопросительного слова
            first_words = message_lower.split()[:2]
            question_words = ['кто', 'что', 'где', 'когда', 'почему', 'как', 'какой', 
                            'who', 'what', 'where', 'when', 'why', 'how', 'which']
            if any(word in question_words for word in first_words):
                needs_search = True
        
        if needs_search:
            logger.info(f"🔍 Автоматический поиск активирован для запроса: {user_message[:50]}...")
            
            # Выполняем расширенный поиск с загрузкой контента
            search_results = await self.web_search.search_with_content(
                user_message, 
                max_results=3,
                fetch_content=True  # Загружаем полный контент страниц
            )
            
            if search_results:
                # Форматируем результаты
                search_context = self.web_search.format_search_results(
                    search_results,
                    user_message
                )
                
                logger.info(f"✅ Найдено {len(search_results)} результатов, добавляем в контекст")
                
                # Добавляем контекст к сообщению
                enhanced_message = (
                    f"Вопрос пользователя: {user_message}\n\n"
                    f"Актуальная информация из интернета:\n{search_context}\n\n"
                    f"Инструкция: Используй предоставленную актуальную информацию для ответа. "
                    f"Если информация полезна, упомяни источники в конце ответа. "
                    f"Отвечай естественно, не упоминая, что ты искал информацию, "
                    f"просто дай информативный ответ на основе найденных данных."
                )
                
                # Генерируем ответ с контекстом
                return await self.lm_client.generate_response(
                    user_message=enhanced_message,
                    conversation_history=conversation_history,
                    system_prompt=system_prompt
                )
            else:
                logger.info("❌ Поиск не дал результатов, используем обычную генерацию")
        
        # Обычная генерация без поиска
        return await self.lm_client.generate_response(
            user_message=user_message,
            conversation_history=conversation_history,
            system_prompt=system_prompt
        )
    
    async def search_and_summarize(self, query: str) -> str:
        """
        Поиск информации и создание краткого содержания
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Краткое содержание найденной информации
        """
        logger.info(f"🔍 Поиск и суммаризация: '{query}'")
        
        search_results = await self.web_search.search(query, max_results=5)
        
        if not search_results:
            return "К сожалению, не удалось найти информацию по вашему запросу."
        
        # Форматируем результаты
        context = self.web_search.format_search_results(search_results, query)
        
        # Просим LLM создать краткое содержание
        summary_prompt = (
            f"На основе следующих результатов поиска создай краткое и информативное "
            f"резюме:\n\n{context}\n\n"
            f"Упомяни ключевые факты и источники информации."
        )
        
        return await self.lm_client.generate_response(
            user_message=summary_prompt,
            system_prompt="Ты эксперт по анализу и суммаризации информации из веб-источников."
        )
