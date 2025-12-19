# -*- coding: utf-8 -*-
"""
Модуль обработки cookies браузера Chromium
"""
import os, sqlite3, shutil
from typing import Dict, List, Tuple
from datetime import datetime

class Parser():
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        
    def _convert_chrome_time(self, chrome_timestamp: int) -> str:
        """Конвертирует Chromium timestamp в читаемую дату"""
        if not chrome_timestamp or chrome_timestamp == 0:
            return 'Не ограничен'
            
        try:
            # Chromium время: микросекунды с 1601-01-01
            unix_timestamp = (chrome_timestamp / 1000000) - 11644473600
            dt = datetime.fromtimestamp(unix_timestamp)
            return dt.strftime('%Y.%m.%d %H:%M:%S')
        except (ValueError, OSError, OverflowError):
            return 'Ошибка конвертации'

    def _decrypt_cookie_value(self, encrypted_value: bytes) -> str:
        """
        Пытается расшифровать значение cookie.
        В современных версиях Chrome cookies шифруются.
        """
        if not encrypted_value:
            return ''
            
        try:
            # Простая попытка декодирования как текста
            # В реальной системе нужно использовать ключ дешифрования из Local State
            decoded = encrypted_value.decode('utf-8', errors='ignore')
            if decoded and len(decoded) > 0:
                return f"[зашифровано: {len(encrypted_value)} байт]"
            else:
                return "[пустое зашифрованное значение]"
        except:
            return f"[бинарные данные: {len(encrypted_value)} байт]"

    def _parse_chrome_cookies(self, cookies_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг cookies браузера"""
        results = []
        
        if not os.path.exists(cookies_path):
            return results
            
        # Создаем временную копию для избежания блокировки
        temp_dir = self.__parameters.get('TEMP')
        temp_path = os.path.join(temp_dir, f'temp_cookies_{os.path.basename(cookies_path)}')
        
        try:
            shutil.copy2(cookies_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            # Проверяем существование таблицы cookies
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
            if not cursor.fetchone():
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
                cookie_value = value if value else self._decrypt_cookie_value(encrypted_value)
                
                # Конвертируем временные метки
                creation_date = self._convert_chrome_time(creation_utc)
                expires_date = self._convert_chrome_time(expires_utc)
                last_access_date = self._convert_chrome_time(last_access_utc)
                last_update_date = self._convert_chrome_time(last_update_utc)
                
                # Определяем тип cookie
                cookie_type = "Сессионный" if not is_persistent else "Постоянный"
                
                # Определяем приоритет
                priority_map = {0: "Низкий", 1: "Средний", 2: "Высокий"}
                priority_text = priority_map.get(priority, "Неизвестно")
                
                # Определяем SameSite
                samesite_map = {0: "Не задано", 1: "Lax", 2: "Strict", 3: "None"}
                samesite_text = samesite_map.get(samesite, "Неизвестно")
                
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
                
        except sqlite3.Error as e:
            self.__parameters.get('LOG').Warn('ChromiumCookies', f'Ошибка парсинга cookies: {e}')
        except Exception as e:
            self.__parameters.get('LOG').Error('ChromiumCookies', f'Критическая ошибка: {e}')
        finally:
            if 'conn' in locals():
                conn.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        return results

    async def Start(self) -> Dict:
        storage = self.__parameters.get('STORAGE')
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        if not self.__parameters.get('DBCONNECTION').IsConnected():
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
Для дешифровки требуется ключ из файла Local State.

Данные включают:
- Домены и имена cookies
- Значения cookies (могут быть зашифрованы)
- Сроки действия и создания
- Флаги безопасности (Secure, HttpOnly)
- Типы cookies (сессионные/постоянные)
- Политики SameSite
- Приоритеты cookies
"""
        
        # Настройка вывода
        output_writer.SetFields(fields_description, record_fields)
        output_writer.CreateDatabaseTables()
        
        await self.__parameters.get('UIREDRAW')('Поиск браузеров Chromium...', 10)
        
        # Поиск браузеров
        browsers = [
            ('google-chrome', 'Google Chrome'),
            ('chromium', 'Chromium'),
            ('microsoft-edge', 'Microsoft Edge'),
            ('opera', 'Opera'),
            ('brave', 'Brave')
        ]
        
        all_records = []
        
        for i, (browser_folder, browser_name) in enumerate(browsers):
            progress = 10 + (i * 70 // len(browsers))
            await self.__parameters.get('UIREDRAW')(f'Проверка {browser_name}...', progress)
            
            cookies_path = os.path.join(
                os.path.expanduser('~'),
                '.config', 
                browser_folder,
                'Default',
                'Cookies'
            )
            
            if os.path.exists(cookies_path):
                self.__parameters.get('LOG').Info('ChromiumCookies', f'Найден браузер: {browser_name}')
                records = self._parse_chrome_cookies(cookies_path, browser_name)
                all_records.extend(records)
                print(f"Найдено cookies в {browser_name}: {len(records)}")
        
        # Запись результатов
        await self.__parameters.get('UIREDRAW')('Запись результатов...', 80)
        
        for record in all_records:
            output_writer.WriteRecord(record)
        
        # Завершение работы
        await self.__parameters.get('UIREDRAW')('Формирование БД...', 95)
        
        output_writer.RemoveTempTables()
        await output_writer.CreateDatabaseIndexes(self.__parameters.get('MODULENAME'))
        
        info_data = {
            'Name': self.__parameters.get('MODULENAME'),
            'Help': HELP_TEXT,
            'Timestamp': self.__parameters.get('CASENAME'),
            'Vendor': 'LabFramework',
            'RecordsProcessed': str(len(all_records)),
            'Note': 'Значения cookies могут быть зашифрованы. Для дешифровки требуется ключ из Local State.'
        }
        
        output_writer.SetInfo(info_data)
        output_writer.WriteMeta()
        await output_writer.CloseOutput()
        
        await self.__parameters.get('UIREDRAW')('Завершено!', 100)
        
        return {self.__parameters.get('MODULENAME'): output_writer.GetDBName()}