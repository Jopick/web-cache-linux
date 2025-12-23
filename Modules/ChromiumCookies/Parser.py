# Parser.py с исправленной дешифровкой
# -*- coding: utf-8 -*-
"""
Модуль обработки cookies браузера Chromium
"""
import os, sqlite3, shutil
from typing import Dict, List, Tuple
from datetime import datetime


class CookiesTimeConverter:
    """Класс для конвертации временных меток cookies"""
    
    @staticmethod
    def _convert_chrome_time(chrome_timestamp: int) -> str:
        """Конвертирует Chromium timestamp в читаемую дату"""
        if not chrome_timestamp or chrome_timestamp == 0:
            return 'Не ограничен'
            
        try:
            unix_timestamp = (chrome_timestamp / 1000000) - 11644473600
            dt = datetime.fromtimestamp(unix_timestamp)
            return dt.strftime('%Y.%m.%d %H:%M:%S')
        except:
            return 'Ошибка конвертации'


class CookieValueCleaner:
    """Класс для очистки значений cookies"""
    
    @staticmethod
    def _clean_cookie_value(value, encrypted_value=None):
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


class CookiesMappings:
    """Класс для маппингов значений cookies"""
    
    @staticmethod
    def get_cookie_type(is_persistent):
        """Определяет тип cookie"""
        return "Сессионный" if not is_persistent else "Постоянный"
    
    @staticmethod
    def get_priority_text(priority):
        """Определяет текст приоритета"""
        priority_map = {0: "Низкий", 1: "Средний", 2: "Высокий"}
        return priority_map.get(priority, "Неизвестно")
    
    @staticmethod
    def get_samesite_text(samesite):
        """Определяет текст SameSite"""
        samesite_map = {0: "Не задано", 1: "Lax", 2: "Strict", 3: "None"}
        return samesite_map.get(samesite, "Неизвестно")


class CookiesTableAnalyzer:
    """Класс для анализа структуры таблицы cookies"""
    
    @staticmethod
    def analyze_table_structure(cursor):
        """Анализирует структуру таблицы cookies"""
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
        if not cursor.fetchone():
            return None
        
        cursor.execute("PRAGMA table_info(cookies)")
        columns_info = cursor.fetchall()
        columns = [col[1] for col in columns_info]
        
        return columns


class CookiesQueryBuilder:
    """Класс для построения запросов к таблице cookies"""
    
    @staticmethod
    def build_select_query(columns):
        """Строит SELECT запрос в зависимости от структуры таблицы"""
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
        
        return f"SELECT {', '.join(select_fields)} FROM cookies", select_fields


class CookiesRowProcessor:
    """Класс для обработки строк cookies"""
    
    def __init__(self, parameters: dict, time_converter: CookiesTimeConverter, 
                 value_cleaner: CookieValueCleaner, mappings: CookiesMappings):
        self.__parameters = parameters
        self._time_converter = time_converter
        self._value_cleaner = value_cleaner
        self._mappings = mappings
    
    def process_row(self, row_dict: dict, browser_name: str, cookies_path: str) -> Tuple:
        """Обрабатывает строку cookies и возвращает кортеж"""
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
        cookie_value = self._value_cleaner._clean_cookie_value(value, encrypted_value)
        
        # Конвертируем временные метки
        creation_date = self._time_converter._convert_chrome_time(creation_utc)
        expires_date = self._time_converter._convert_chrome_time(expires_utc)
        last_access_date = self._time_converter._convert_chrome_time(last_access_utc)
        
        # Определяем характеристики cookie
        cookie_type = self._mappings.get_cookie_type(is_persistent)
        priority_text = self._mappings.get_priority_text(priority)
        samesite_text = self._mappings.get_samesite_text(samesite)
        
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
        
        return record


class CookiesParser:
    """Класс для парсинга cookies браузера"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
        self._time_converter = CookiesTimeConverter()
        self._value_cleaner = CookieValueCleaner()
        self._mappings = CookiesMappings()
        self._table_analyzer = CookiesTableAnalyzer()
        self._query_builder = CookiesQueryBuilder()
        self._row_processor = CookiesRowProcessor(parameters, self._time_converter, 
                                                 self._value_cleaner, self._mappings)
    
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
            
            # Анализируем структуру таблицы
            columns = self._table_analyzer.analyze_table_structure(cursor)
            if not columns:
                return results
            
            # Строим запрос
            query, select_fields = self._query_builder.build_select_query(columns)
            cursor.execute(query)
            
            for row in cursor.fetchall():
                try:
                    # Распаковываем значения
                    field_names = [f.split(' as ')[-1] for f in select_fields]
                    row_dict = dict(zip(field_names, row))
                    
                    record = self._row_processor.process_row(row_dict, browser_name, cookies_path)
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


class CookiesOutputConfigurator:
    """Класс для настройки вывода данных cookies"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
    
    def _configure_output(self, output_writer):
        """Настраивает поля и структуру вывода"""
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
        
        output_writer.SetFields(fields_description, record_fields)
        output_writer.CreateDatabaseTables()


class CookiesBrowserFinder:
    """Класс для поиска браузеров с cookies"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
    
    async def _find_browsers_cookies(self, cookies_parser: CookiesParser) -> List[Tuple]:
        """Поиск браузеров и сбор данных cookies"""
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
                records = cookies_parser._parse_chrome_cookies(cookies_path, browser_name)
                all_records.extend(records)
        
        return all_records


class Parser:
    """Основной класс-координатор для парсинга cookies"""
    
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        self._cookies_parser = CookiesParser(parameters)
        self._output_configurator = CookiesOutputConfigurator(parameters)
        self._browser_finder = CookiesBrowserFinder(parameters)
    
    async def Start(self) -> Dict:
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        if not self.__parameters.get('DBCONNECTION').IsConnected():
            return {}
        
        HELP_TEXT = """
Chromium Cookies Parser:
Cookies (куки) браузеров на базе Chromium

ВНИМАНИЕ:
В современных версиях Chrome значения cookies шифруются.
Отображаются только читаемые символы.
"""
        
        # Настройка вывода
        self._output_configurator._configure_output(output_writer)
        
        await self.__parameters.get('UIREDRAW')('Поиск браузеров Chromium...', 10)
        
        # Поиск браузеров и сбор данных cookies
        all_records = await self._browser_finder._find_browsers_cookies(self._cookies_parser)
        
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