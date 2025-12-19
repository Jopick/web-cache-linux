# -*- coding: utf-8 -*-
"""
Модуль обработки истории браузера Chromium
"""
import os, sqlite3, shutil
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from abc import ABC, abstractmethod


class TimeConverter:
    """Класс для конвертации временных меток Chromium"""
    
    @staticmethod
    def convert_chrome_time(chrome_timestamp: int) -> str:
        """Конвертирует Chromium timestamp в читаемую дату"""
        if not chrome_timestamp or chrome_timestamp == 0:
            return ''
            
        try:
            # Chromium время: микросекунды с 1601-01-01
            # Конвертируем в Unix время (секунды с 1970-01-01)
            unix_timestamp = (chrome_timestamp / 1000000) - 11644473600
            dt = datetime.fromtimestamp(unix_timestamp)
            return dt.strftime('%Y.%m.%d %H:%M:%S')
        except (ValueError, OSError, OverflowError):
            return ''


class DatabaseManager:
    """Класс для управления подключением к базе данных"""
    
    def __init__(self, temp_dir: str, history_path: str):
        self.temp_dir = temp_dir
        self.history_path = history_path
        self.temp_path: Optional[str] = None
        self.conn: Optional[sqlite3.Connection] = None
        
    def __enter__(self):
        """Создание временной копии и подключение к БД"""
        self.temp_path = os.path.join(
            self.temp_dir, 
            f'temp_history_{os.path.basename(self.history_path)}'
        )
        shutil.copy2(self.history_path, self.temp_path)
        self.conn = sqlite3.connect(self.temp_path)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Закрытие соединения и удаление временного файла"""
        if self.conn:
            self.conn.close()
        if self.temp_path and os.path.exists(self.temp_path):
            os.remove(self.temp_path)
            
    def get_cursor(self) -> sqlite3.Cursor:
        """Получение курсора базы данных"""
        if self.conn:
            return self.conn.cursor()
        raise sqlite3.Error("Нет подключения к базе данных")


class HistoryParser:
    """Класс для парсинга истории посещений"""
    
    def __init__(self, logger, username: str = 'Unknown'):
        self.logger = logger
        self.username = username
        self.time_converter = TimeConverter()
        
    def parse_history(self, history_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг истории браузера"""
        results = []
        
        if not os.path.exists(history_path):
            return results
            
        try:
            with DatabaseManager(
                temp_dir=os.path.dirname(history_path),  # Временная директория
                history_path=history_path
            ) as db_manager:
                cursor = db_manager.get_cursor()
                
                # Проверяем существование таблицы urls
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls'")
                if not cursor.fetchone():
                    return results
                
                # Получаем историю посещений
                query = """
                SELECT 
                    url, 
                    title, 
                    visit_count, 
                    typed_count, 
                    last_visit_time
                FROM urls 
                ORDER BY last_visit_time DESC
                """
                
                cursor.execute(query)
                results = self._process_rows(cursor, browser_name)
                
        except sqlite3.Error as e:
            self.logger.Warn('ChromiumHistory', f'Ошибка парсинга: {e}')
        except Exception as e:
            self.logger.Error('ChromiumHistory', f'Критическая ошибка: {e}')
                
        return results
    
    def _process_rows(self, cursor: sqlite3.Cursor, browser_name: str) -> List[Tuple]:
        """Обработка строк из результата запроса"""
        results = []
        
        for row in cursor.fetchall():
            url, title, visit_count, typed_count, last_visit_time = row
            
            # Конвертируем время
            visit_date = self.time_converter.convert_chrome_time(last_visit_time)
            
            record = (
                self.username,
                browser_name,
                url or '',
                title or '',
                visit_count or 0,
                typed_count or 0,
                last_visit_time or 0,
                visit_date,
                browser_name  # Можно передавать history_path, но в коде было browser_name
            )
            results.append(record)
            
        return results


class BrowserFinder:
    """Класс для поиска браузеров на системе"""
    
    BROWSERS = [
        ('google-chrome', 'Google Chrome'),
        ('chromium', 'Chromium'),
        ('microsoft-edge', 'Microsoft Edge'),
        ('opera', 'Opera'),
        ('brave', 'Brave')
    ]
    
    @staticmethod
    def find_browser_history_paths() -> List[Tuple[str, str, str]]:
        """Поиск путей к файлам истории браузеров"""
        found_browsers = []
        
        for browser_folder, browser_name in BrowserFinder.BROWSERS:
            history_path = os.path.join(
                os.path.expanduser('~'),
                '.config', 
                browser_folder,
                'Default',
                'History'
            )
            
            if os.path.exists(history_path):
                found_browsers.append((history_path, browser_folder, browser_name))
                
        return found_browsers


class OutputConfigurator:
    """Класс для настройки вывода данных"""
    
    @staticmethod
    def get_record_fields() -> Dict[str, str]:
        """Структура полей для БД"""
        return {
            'UserName': 'TEXT',
            'Browser': 'TEXT', 
            'URL': 'TEXT',
            'Title': 'TEXT',
            'VisitCount': 'INTEGER',
            'TypedCount': 'INTEGER', 
            'LastVisitTime': 'INTEGER',
            'LastVisitDate': 'TEXT',
            'DataSource': 'TEXT'
        }
    
    @staticmethod
    def get_fields_description() -> Dict[str, Tuple]:
        """Описание полей для интерфейса"""
        return {
            'UserName': ('Имя пользователя', 120, 'string', 'Имя пользователя ОС'),
            'Browser': ('Браузер', 100, 'string', 'Название браузера'),
            'URL': ('URL', 400, 'string', 'Адрес страницы'),
            'Title': ('Заголовок', 300, 'string', 'Заголовок страницы'),
            'VisitCount': ('Кол-во посещений', 100, 'integer', 'Количество посещений'),
            'TypedCount': ('Кол-во вводов', 100, 'integer', 'Количество прямых переходов'),
            'LastVisitTime': ('Время посещения (timestamp)', -1, 'integer', 'Временная метка Chromium'),
            'LastVisitDate': ('Дата посещения', 180, 'string', 'Дата и время посещения'),
            'DataSource': ('Источник данных', 200, 'string', 'Путь к файлу истории')
        }
    
    @staticmethod
    def get_help_text() -> str:
        """Текст помощи для модуля"""
        return """
Chromium History Parser:
История посещений браузеров на базе Chromium

Извлекается из файлов:
~/.config/google-chrome/Default/History
~/.config/chromium/Default/History

Данные включают:
- URL посещенных страниц
- Заголовки страниц  
- Количество посещений
- Время последнего посещения
"""


class MainParser:
    """Основной класс-оркестратор"""
    
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        self.output_config = OutputConfigurator()
        
    async def Start(self) -> Dict:
        """Основной метод запуска парсера"""
        storage = self.__parameters.get('STORAGE')
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        if not self.__parameters.get('DBCONNECTION').IsConnected():
            return {}
        
        # Настройка вывода
        output_writer.SetFields(
            self.output_config.get_fields_description(),
            self.output_config.get_record_fields()
        )
        output_writer.CreateDatabaseTables()
        
        await self.__parameters.get('UIREDRAW')('Поиск браузеров Chromium...', 10)
        
        # Поиск браузеров
        browser_finder = BrowserFinder()
        found_browsers = browser_finder.find_browser_history_paths()
        
        all_records = []
        history_parser = HistoryParser(
            logger=self.__parameters.get('LOG'),
            username=self.__parameters.get('USERNAME', 'Unknown')
        )
        
        for i, (history_path, browser_folder, browser_name) in enumerate(found_browsers):
            progress = 10 + (i * 70 // max(len(found_browsers), 1))
            await self.__parameters.get('UIREDRAW')(f'Проверка {browser_name}...', progress)
            
            self.__parameters.get('LOG').Info('ChromiumHistory', f'Найден браузер: {browser_name}')
            records = history_parser.parse_history(history_path, browser_name)
            all_records.extend(records)
            print(f"Найдено записей в {browser_name}: {len(records)}")
        
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
            'Help': self.output_config.get_help_text(),
            'Timestamp': self.__parameters.get('CASENAME'),
            'Vendor': 'LabFramework',
            'RecordsProcessed': str(len(all_records))
        }
        
        output_writer.SetInfo(info_data)
        output_writer.WriteMeta()
        await output_writer.CloseOutput()
        
        await self.__parameters.get('UIREDRAW')('Завершено!', 100)
        
        return {self.__parameters.get('MODULENAME'): output_writer.GetDBName()}