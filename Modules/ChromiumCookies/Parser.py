# -*- coding: utf-8 -*-
"""
Модуль обработки cookies браузера Chromium
"""
import os, sqlite3, shutil
import json, base64
from typing import Dict, List, Tuple
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from Common.time_utils import (
    convert_chrome_time, 
    get_cookie_type, 
    get_priority_text, 
    get_samesite_text
)
from Common.browser_finder import BrowserFinder

from Common.time_utils import convert_chrome_time

# Пробуем импортировать browser-cookie3
try:
    import browser_cookie3
    BROWSER_COOKIE3_AVAILABLE = True
    print("[INFO] browser-cookie3 доступен, будет использован для дешифровки")
except ImportError:
    BROWSER_COOKIE3_AVAILABLE = False
    print("[INFO] browser-cookie3 не установлен, дешифровка будет ограничена")


class CookieDecryptor:
    """Дешифратор значений cookie"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
        self.__decrypted_cookies_cache = {}  # Кэш для cookies из browser-cookie3
        
    def _get_decrypted_cookies(self, browser_name: str) -> Dict[str, str]:
        """
        Получает расшифрованные cookies через browser-cookie3
        """
        cache_key = browser_name.lower()
        if cache_key in self.__decrypted_cookies_cache:
            return self.__decrypted_cookies_cache[cache_key]
        
        decrypted_cookies = {}
        
        if not BROWSER_COOKIE3_AVAILABLE:
            self.__parameters.get('LOG').Warn('ChromiumCookies',
                'browser-cookie3 не доступен, дешифровка невозможна')
            return decrypted_cookies
        
        try:
            self.__parameters.get('LOG').Info('ChromiumCookies',
                f'Получение cookies через browser-cookie3 для {browser_name}')
            
            # Выбираем правильный метод для браузера
            if 'chrome' in browser_name.lower():
                cj = browser_cookie3.chrome()
            elif 'chromium' in browser_name.lower():
                cj = browser_cookie3.chromium()
            elif 'edge' in browser_name.lower():
                cj = browser_cookie3.edge()
            elif 'opera' in browser_name.lower():
                cj = browser_cookie3.opera()
            elif 'brave' in browser_name.lower():
                cj = browser_cookie3.brave()
            else:
                cj = browser_cookie3.chrome()  # По умолчанию
            
            # Создаем словарь для быстрого поиска: ключ = "host_key|name"
            for cookie in cj:
                key = f"{cookie.domain}|{cookie.name}"
                decrypted_cookies[key] = cookie.value
            
            self.__parameters.get('LOG').Info('ChromiumCookies',
                f'Получено {len(decrypted_cookies)} расшифрованных cookies через browser-cookie3')
            
        except Exception as e:
            self.__parameters.get('LOG').Error('ChromiumCookies',
                f'Ошибка получения cookies через browser-cookie3: {e}')
        
        self.__decrypted_cookies_cache[cache_key] = decrypted_cookies
        return decrypted_cookies
    
    def _decrypt_cookie_value(self, encrypted_value: bytes, cookies_path: str = None) -> str:
        """
        Пытается расшифровать значение cookie (запасной метод)
        """
        if not encrypted_value:
            return ''
            
        try:
            # Пробуем просто декодировать как текст
            decoded = encrypted_value.decode('utf-8', errors='ignore')
            
            # Если это читаемый текст и не начинается с v10/v11, возвращаем его
            if decoded and len(decoded) > 0 and not decoded.startswith(('v10', 'v11')):
                # Проверяем, есть ли печатаемые символы
                if any(c.isprintable() or c.isspace() for c in decoded[:100]):
                    return decoded[:500]  # Ограничиваем длину
            
            # Если данные начинаются с v10 или v11
            if encrypted_value.startswith(b'v10') or encrypted_value.startswith(b'v11'):
                # На Linux дешифровка сложна, возвращаем информацию
                return f"[зашифровано AES-GCM v{encrypted_value[1:3].decode()}: {len(encrypted_value)} байт]"
            
            # Для других бинарных данных
            return f"[бинарные данные: {len(encrypted_value)} байт]"
                
        except:
            return f"[бинарные данные: {len(encrypted_value)} байт]"


class CookieValueResolver:
    """Определитель значений cookie"""
    
    def __init__(self, cookie_decryptor: CookieDecryptor):
        self.cookie_decryptor = cookie_decryptor
        
    def get_cookie_value(self, name: str, host_key: str, value: str, 
                         encrypted_value: bytes, decrypted_cookies: Dict[str, str],
                         cookies_path: str = None) -> str:
        """
        Определяет значение cookie, пытаясь дешифровать если нужно
        """
        # Если есть обычное значение, используем его
        if value:
            return value
        
        # Пробуем найти в расшифрованных cookies из browser-cookie3
        if name and host_key:
            lookup_key = f"{host_key}|{name}"
            if lookup_key in decrypted_cookies:
                self.cookie_decryptor._parameters.get('LOG').Info('ChromiumCookies',
                    f'Найдено расшифрованное значение для {name} через browser-cookie3')
                return decrypted_cookies[lookup_key]
        
        # Если есть зашифрованное значение, но не нашли в browser-cookie3
        if encrypted_value:
            # Пробуем нашу дешифровку как запасной вариант
            decrypted = self.cookie_decryptor._decrypt_cookie_value(encrypted_value, cookies_path)
            if decrypted and not decrypted.startswith('[зашифровано') and not decrypted.startswith('[бинарные'):
                return decrypted
            return decrypted
        
        return ""
class CookiesFileParser:
    """Парсер файлов cookies SQLite"""
    
    def __init__(self, parameters: dict, cookie_value_resolver: CookieValueResolver):
        self.__parameters = parameters
        self.cookie_value_resolver = cookie_value_resolver
    
    def parse_cookies_file(self, cookies_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг cookies браузера"""
        results = []
        
        # Получаем расшифрованные cookies через browser-cookie3
        decrypted_cookies = self.cookie_value_resolver.cookie_decryptor._get_decrypted_cookies(browser_name)
        
        if not os.path.exists(cookies_path):
            print(f"[DEBUG] Файл не найден: {cookies_path}")
            return results
            
        print(f"[DEBUG] Начинаем парсинг: {cookies_path}")
            
        # Создаем временную копию для избежания блокировки
        temp_dir = self.__parameters.get('TEMP')
        temp_path = os.path.join(temp_dir, f'temp_cookies_{os.path.basename(cookies_path)}')
        
        try:
            shutil.copy2(cookies_path, temp_path)
            print(f"[DEBUG] Создана временная копия: {temp_path}")
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            # Проверяем существование таблицы cookies
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
            if not cursor.fetchone():
                print("[DEBUG] Таблица 'cookies' не найдена в базе")
                return results
            
            # Получаем cookies - включаем encrypted_value
            query = """
            SELECT 
                creation_utc,
                host_key,
                name, 
                value,
                encrypted_value,
                path,
                expires_utc,
                is_secure,
                is_httponly,
                last_access_utc,
                has_expires,
                is_persistent,
                priority,
                samesite,
                last_update_utc
            FROM cookies 
            ORDER BY last_access_utc DESC
            """
            
            cursor.execute(query)
            
            for row in cursor.fetchall():
                try:
                    # Безопасное извлечение по индексам
                    creation_utc = row[0] if len(row) > 0 else 0
                    host_key = row[1] if len(row) > 1 else ''
                    name = row[2] if len(row) > 2 else ''
                    value = row[3] if len(row) > 3 else ''
                    encrypted_value = row[4] if len(row) > 4 else b''
                    path = row[5] if len(row) > 5 else ''
                    expires_utc = row[6] if len(row) > 6 else 0
                    is_secure = row[7] if len(row) > 7 else 0
                    is_httponly = row[8] if len(row) > 8 else 0
                    last_access_utc = row[9] if len(row) > 9 else 0
                    has_expires = row[10] if len(row) > 10 else 0
                    is_persistent = row[11] if len(row) > 11 else 0
                    priority = row[12] if len(row) > 12 else 0
                    samesite = row[13] if len(row) > 13 else 0
                    last_update_utc = row[14] if len(row) > 14 else 0
        
                except IndexError:
                    continue
                
                # Определяем фактическое значение cookie
                cookie_value = self.cookie_value_resolver.get_cookie_value(
                    name, host_key, value, encrypted_value, 
                    decrypted_cookies, cookies_path
                )
                
                # Конвертируем временные метки
                creation_date = convert_chrome_time(creation_utc)
                expires_date = convert_chrome_time(expires_utc)
                last_access_date = convert_chrome_time(last_access_utc)
                last_update_date = convert_chrome_time(last_update_utc)
                
                # Определяем тип cookie и другие свойства
                cookie_type = get_cookie_type(is_persistent)
                priority_text = get_priority_text(priority)
                samesite_text = get_samesite_text(samesite)
                
                record = (
                    self.__parameters.get('USERNAME', 'Unknown'),
                    browser_name,
                    host_key or '',
                    name or '',
                    cookie_value,
                    path or '',
                    creation_utc or 0,
                    creation_date,
                    expires_utc or 0,
                    expires_date,
                    last_access_utc or 0,
                    last_access_date,
                    last_update_utc or 0,
                    last_update_date,
                    bool(is_secure),
                    bool(is_httponly),
                    cookie_type,
                    priority_text,
                    samesite_text,
                    cookies_path
                )
                results.append(record)
                
                # ДОБАВИМ ОТЛАДОЧНЫЙ ВЫВОД
                if len(results) % 100 == 0:
                    print(f"[DEBUG] Обработано записей: {len(results)}")
                
        except sqlite3.Error as e:
            self.__parameters.get('LOG').Warn('ChromiumCookies', f'Ошибка парсинга cookies: {e}')
            print(f"[DEBUG] Ошибка SQLite: {e}")
        except Exception as e:
            self.__parameters.get('LOG').Error('ChromiumCookies', f'Критическая ошибка: {e}')
            print(f"[DEBUG] Критическая ошибка: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        print(f"[DEBUG] Завершен парсинг, найдено записей: {len(results)}")
        return results

class CookiesProcessor:
    """Основной процессор обработки cookies"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
        self.cookie_decryptor = CookieDecryptor(parameters)
        self.cookie_value_resolver = CookieValueResolver(self.cookie_decryptor)
        self.cookies_file_parser = CookiesFileParser(parameters, self.cookie_value_resolver)
        
    def process_all_browsers(self) -> List[Tuple]:
        """Обрабатывает cookies всех найденных браузеров"""
        all_records = []
        browser_paths = BrowserFinder.get_cookies_paths()
        
        for i, (cookies_path, browser_name, browser_folder) in enumerate(browser_paths):
            self.__parameters.get('LOG').Info('ChromiumCookies', f'Найден браузер: {browser_name}')
            records = self.cookies_file_parser.parse_cookies_file(cookies_path, browser_name)
            all_records.extend(records)
            print(f"[DEBUG] Найдено cookies в {browser_name}: {len(records)}")
        
        return all_records


class Parser():
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        self.cookies_processor = CookiesProcessor(parameters)
        
    def _parse_chrome_cookies(self, cookies_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг cookies браузера"""
        return self.cookies_processor.cookies_file_parser.parse_cookies_file(cookies_path, browser_name)

    async def Start(self) -> Dict:
        storage = self.__parameters.get('STORAGE')
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        print(f"[DEBUG] Start вызван, output_writer: {output_writer}")
        
        if not self.__parameters.get('DBCONNECTION').IsConnected():
            print("[DEBUG] Нет подключения к БД")
            return {}
        
        # Структура полей для БД
        record_fields = {
            'UserName': 'TEXT',
            'Browser': 'TEXT', 
            'Host': 'TEXT',
            'CookieName': 'TEXT',
            'CookieValue': 'TEXT',
            'Path': 'TEXT',
            'CreationUTC': 'INTEGER',
            'CreationDate': 'TEXT',
            'ExpiresUTC': 'INTEGER',
            'ExpiresDate': 'TEXT',
            'LastAccessUTC': 'INTEGER', 
            'LastAccessDate': 'TEXT',
            'LastUpdateUTC': 'INTEGER',
            'LastUpdateDate': 'TEXT',
            'IsSecure': 'INTEGER',
            'IsHttpOnly': 'INTEGER',
            'CookieType': 'TEXT',
            'Priority': 'TEXT',
            'SameSite': 'TEXT',
            'DataSource': 'TEXT'
        }
        
        # Описание полей для интерфейса
        fields_description = {
            'UserName': ('Имя пользователя', 120, 'string', 'Имя пользователя ОС'),
            'Browser': ('Браузер', 100, 'string', 'Название браузера'),
            'Host': ('Домен', 200, 'string', 'Домен cookie'),
            'CookieName': ('Имя cookie', 150, 'string', 'Название cookie'),
            'CookieValue': ('Значение cookie', 300, 'string', 'Значение cookie (может быть зашифровано)'),
            'Path': ('Путь', 100, 'string', 'Путь на сервере'),
            'CreationUTC': ('Создание (UTC)', -1, 'integer', 'Временная метка создания'),
            'CreationDate': ('Дата создания', 180, 'string', 'Дата создания cookie'),
            'ExpiresUTC': ('Истечение (UTC)', -1, 'integer', 'Временная метка истечения'),
            'ExpiresDate': ('Дата истечения', 180, 'string', 'Дата истечения срока действия'),
            'LastAccessUTC': ('Последний доступ (UTC)', -1, 'integer', 'Временная метка последнего доступа'),
            'LastAccessDate': ('Дата последнего доступа', 180, 'string', 'Дата последнего использования'),
            'LastUpdateUTC': ('Последнее обновление (UTC)', -1, 'integer', 'Временная метка обновления'),
            'LastUpdateDate': ('Дата обновления', 180, 'string', 'Дата последнего обновления'),
            'IsSecure': ('Secure', 60, 'boolean', 'Только HTTPS'),
            'IsHttpOnly': ('HttpOnly', 60, 'boolean', 'Недоступен для JavaScript'),
            'CookieType': ('Тип', 80, 'string', 'Сессионный/Постоянный'),
            'Priority': ('Приоритет', 80, 'string', 'Приоритет cookie'),
            'SameSite': ('SameSite', 80, 'string', 'Политика SameSite'),
            'DataSource': ('Источник данных', 200, 'string', 'Путь к файлу cookies')
        }
        
        HELP_TEXT = """
Chromium Cookies Parser:
Cookies (куки) браузеров на базе Chromium

Извлекается из файлов:
~/.config/google-chrome/Default/Cookies
~/.config/chromium/Default/Cookies

ВНИМАНИЕ:
В современных версиях Chrome значения cookies шифруются.
Парсер использует browser-cookie3 для дешифровки, если он доступен.

Данные включают:
- Домены и имена cookies
- Значения cookies (дешифруются через browser-cookie3)
- Сроки действия и создания
- Флаги безопасности (Secure, HttpOnly)
- Типы cookies (сессионные/постоянные)
- Политики SameSite
- Приоритеты cookies

Требования для дешифровки:
1. Установленный browser-cookie3: pip install browser-cookie3
2. Доступ к браузеру (Chrome/Chromium может потребоваться запустить)
"""
        
        # Настройка вывода
        print("[DEBUG] Настройка полей output_writer")
        output_writer.SetFields(fields_description, record_fields)
        output_writer.CreateDatabaseTables()
        
        await self.__parameters.get('UIREDRAW')('Поиск браузеров Chromium...', 10)
        
        # Обработка всех браузеров
        all_records = self.cookies_processor.process_all_browsers()
        
        print(f"[DEBUG] Всего найдено записей: {len(all_records)}")
        
        # Запись результатов
        await self.__parameters.get('UIREDRAW')('Запись результатов...', 80)
        
        print(f"[DEBUG] Начинаем запись {len(all_records)} записей в output_writer")
        record_count = 0
        for i, record in enumerate(all_records):
            try:
                output_writer.WriteRecord(record)
                record_count += 1
                if i % 50 == 0:
                    print(f"[DEBUG] Записано записей: {i+1}")
            except Exception as e:
                print(f"[DEBUG] Ошибка при записи записи {i}: {e}")
        
        print(f"[DEBUG] Все записи отправлены в output_writer, всего записей: {record_count}")
        
        # Завершение работы
        await self.__parameters.get('UIREDRAW')('Формирование БД...', 95)
        
        print("[DEBUG] Удаляем временные таблицы")
        output_writer.RemoveTempTables()
        
        print("[DEBUG] Создаем индексы")
        await output_writer.CreateDatabaseIndexes(self.__parameters.get('MODULENAME'))
        
        info_data = {
            'Name': self.__parameters.get('MODULENAME'),
            'Help': HELP_TEXT,
            'Timestamp': self.__parameters.get('CASENAME'),
            'Vendor': 'LabFramework',
            'RecordsProcessed': str(len(all_records)),
            'Note': 'Значения cookies дешифруются через browser-cookie3. Убедитесь, что он установлен (pip install browser-cookie3).'
        }
        
        print("[DEBUG] Устанавливаем метаинформацию")
        output_writer.SetInfo(info_data)
        
        print("[DEBUG] Записываем метаданные")
        output_writer.WriteMeta()
        
        print("[DEBUG] Закрываем вывод")
        await output_writer.CloseOutput()
        
        await self.__parameters.get('UIREDRAW')('Завершено!', 100)
        
        db_name = output_writer.GetDBName()
        print(f"[DEBUG] Имя БД: {db_name}")
        
        return {self.__parameters.get('MODULENAME'): db_name}