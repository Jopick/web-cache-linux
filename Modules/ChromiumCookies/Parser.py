# Parser.py с исправленной дешифровкой
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
            unix_timestamp = (chrome_timestamp / 1000000) - 11644473600
            dt = datetime.fromtimestamp(unix_timestamp)
            return dt.strftime('%Y.%m.%d %H:%M:%S')
        except:
            return 'Ошибка конвертации'

    def _clean_cookie_value(self, value, encrypted_value=None):
        """
        Очищает значение cookie от нечитаемых символов.
        В современных Chrome cookies шифруются.
        """
        if not value and not encrypted_value:
            return ''
            
        # Сначала пробуем значение из поля value
        if value:
            try:
                # Пробуем декодировать как UTF-8
                if isinstance(value, bytes):
                    decoded = value.decode('utf-8', errors='ignore')
                else:
                    decoded = str(value)
                
                # Убираем непечатаемые символы
                import string
                printable = set(string.printable)
                cleaned = ''.join(filter(lambda x: x in printable, decoded))
                
                if cleaned.strip():
                    return cleaned[:200]  # Ограничиваем длину
            except:
                pass
        
        # Если не вышло, пробуем encrypted_value
        if encrypted_value and isinstance(encrypted_value, bytes):
            try:
                # Пробуем разные кодировки
                for encoding in ['utf-8', 'latin-1', 'cp1251']:
                    try:
                        decoded = encrypted_value.decode(encoding, errors='ignore')
                        # Фильтруем непечатаемые символы
                        import string
                        printable = set(string.printable)
                        cleaned = ''.join(filter(lambda x: x in printable, decoded))
                        if cleaned.strip():
                            return f"[шифр: {cleaned[:100]}]"
                    except:
                        continue
                        
                # Если ничего не вышло, показываем как бинарные данные
                return f"[бинарные данные: {len(encrypted_value)} байт]"
            except:
                pass
        
        # Если вообще ничего нет
        return ''

    def _parse_chrome_cookies(self, cookies_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг cookies браузера"""
        results = []
        
        if not os.path.exists(cookies_path):
            return results
            
        temp_dir = self.__parameters.get('TEMP', '/tmp')
        temp_path = os.path.join(temp_dir, f'temp_cookies_{os.getpid()}.db')
        
        try:
            # Копируем файл
            shutil.copy2(cookies_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            # Проверяем таблицу cookies
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
            if not cursor.fetchone():
                return results
            
            # Определяем структуру таблицы
            cursor.execute("PRAGMA table_info(cookies)")
            columns_info = cursor.fetchall()
            columns = [col[1] for col in columns_info]
            
            # Строим запрос в зависимости от структуры
            select_fields = []
            
            # Определяем какие поля есть
            field_mapping = {
                'host_key': 'host_key',
                'name': 'name',
                'value': 'value',
                'path': 'path',
                'expires_utc': 'expires_utc',
                'is_secure': 'is_secure',
                'is_httponly': 'is_httponly',
                'creation_utc': 'creation_utc',
                'last_access_utc': 'last_access_utc',
                'has_expires': 'has_expires',
                'is_persistent': 'is_persistent',
                'persistent': 'persistent',
                'priority': 'priority',
                'samesite': 'samesite',
                'encrypted_value': 'encrypted_value'
            }
            
            for field, alias in field_mapping.items():
                if field in columns:
                    select_fields.append(field)
                elif field == 'persistent' and 'is_persistent' in columns:
                    select_fields.append('is_persistent as persistent')
                else:
                    select_fields.append(f'NULL as {alias}')
            
            query = f"SELECT {', '.join(select_fields)} FROM cookies"
            cursor.execute(query)
            
            for row in cursor.fetchall():
                try:
                    # Распаковываем значения
                    row_dict = dict(zip([f.split(' as ')[-1] for f in select_fields], row))
                    
                    host_key = row_dict.get('host_key', '')
                    name = row_dict.get('name', '')
                    value = row_dict.get('value', '')
                    path = row_dict.get('path', '')
                    expires_utc = row_dict.get('expires_utc', 0)
                    is_secure = row_dict.get('is_secure', 0)
                    is_httponly = row_dict.get('is_httponly', 0)
                    creation_utc = row_dict.get('creation_utc', 0)
                    last_access_utc = row_dict.get('last_access_utc', 0)
                    has_expires = row_dict.get('has_expires', 0)
                    is_persistent = row_dict.get('persistent', 1)  # persistent или is_persistent
                    priority = row_dict.get('priority', 0)
                    samesite = row_dict.get('samesite', 0)
                    encrypted_value = row_dict.get('encrypted_value')
                    
                    # Очищаем значение cookie
                    cookie_value = self._clean_cookie_value(value, encrypted_value)
                    
                    # Конвертируем временные метки
                    creation_date = self._convert_chrome_time(creation_utc)
                    expires_date = self._convert_chrome_time(expires_utc)
                    last_access_date = self._convert_chrome_time(last_access_utc)
                    
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
                        creation_utc or 0,  # LastUpdateUTC
                        creation_date,      # LastUpdateDate
                        1 if is_secure else 0,
                        1 if is_httponly else 0,
                        cookie_type,
                        priority_text,
                        samesite_text,
                        cookies_path
                    )
                    results.append(record)
                    
                except Exception as e:
                    continue  # Пропускаем некорректные записи
            
            self.__parameters.get('LOG').Info('ChromiumCookies', f'Найдено записей в {browser_name}: {len(results)}')
                
        except Exception as e:
            self.__parameters.get('LOG').Warn('ChromiumCookies', f'Ошибка парсинга: {str(e)}')
        finally:
            if 'conn' in locals():
                conn.close()
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
                
        return results

    async def Start(self) -> Dict:
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
            'CookieValue': ('Значение cookie', 300, 'string', 'Значение cookie'),
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

ВНИМАНИЕ:
В современных версиях Chrome значения cookies шифруются.
Отображаются только читаемые символы.
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
            'Note': 'Значения cookies могут быть зашифрованы. Отображаются только читаемые символы.'
        }
        
        output_writer.SetInfo(info_data)
        output_writer.WriteMeta()
        await output_writer.CloseOutput()
        
        await self.__parameters.get('UIREDRAW')('Завершено!', 100)
        
        return {self.__parameters.get('MODULENAME'): output_writer.GetDBName()}