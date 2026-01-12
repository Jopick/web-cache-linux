"""
Модуль обработки истории браузера Chromium
"""
import os, sqlite3, shutil
from typing import Dict, List, Tuple
from datetime import datetime


class TimeConverter:
    """Конвертер временных меток Chromium"""
    
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


class HistoryFileParser:
    """Парсер файлов истории SQLite"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
        self.time_converter = TimeConverter()
    
    def parse_history_file(self, history_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг истории браузера из SQLite файла"""
        results = []
        
        if not os.path.exists(history_path):
            return results
            
        # Создаем временную копию для избежания блокировки
        temp_dir = self.__parameters.get('TEMP')
        temp_path = os.path.join(temp_dir, f'temp_history_{os.path.basename(history_path)}')
        
        try:
            shutil.copy2(history_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
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
            
            for row in cursor.fetchall():
                if len(row) < 5:  # Проверяем, что в строке достаточно данных
                    continue  # Пропускаем строку с недостающими данными
    
                # Извлекаем значения с преобразованием типов
                url = str(row[0]) if row[0] is not None else ''
                title = str(row[1]) if row[1] is not None else ''
                visit_count = int(row[2]) if row[2] is not None else 0
                typed_count = int(row[3]) if row[3] is not None else 0
                last_visit_time = int(row[4]) if row[4] is not None else 0
                
                # Конвертируем время
                visit_date = self.time_converter.convert_chrome_time(last_visit_time)
                
                record = (
                    self.__parameters.get('USERNAME', 'Unknown'),
                    browser_name,
                    url or '',
                    title or '',
                    visit_count or 0,
                    typed_count or 0,
                    last_visit_time or 0,
                    visit_date,
                    history_path
                )
                results.append(record)
                
        except sqlite3.Error as e:
            self.__parameters.get('LOG').Warn('ChromiumHistory', f'Ошибка парсинга: {e}')
        except Exception as e:
            self.__parameters.get('LOG').Error('ChromiumHistory', f'Критическая ошибка: {e}')
        finally:
            if 'conn' in locals():
                conn.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        return results


class BrowserFinder:
    """Поиск браузеров на системе"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
        
    def get_browser_paths(self) -> List[Tuple[str, str, str]]:
        """Возвращает список путей к файлам истории браузеров"""
        browsers = [
            ('google-chrome', 'Google Chrome'),
            ('chromium', 'Chromium'),
            ('microsoft-edge', 'Microsoft Edge'),
            ('opera', 'Opera'),
            ('brave', 'Brave')
        ]
        
        browser_paths = []
        
        for browser_folder, browser_name in browsers:
            history_path = os.path.join(
                os.path.expanduser('~'),
                '.config', 
                browser_folder,
                'Default',
                'History'
            )
            
            if os.path.exists(history_path):
                browser_paths.append((history_path, browser_name, browser_folder))
                
        return browser_paths


class HistoryProcessor:
    """Основной процессор обработки истории"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
        self.history_parser = HistoryFileParser(parameters)
        self.browser_finder = BrowserFinder(parameters)
        
    def process_all_browsers(self) -> List[Tuple]:
        """Обрабатывает историю всех найденных браузеров"""
        all_records = []
        browser_paths = self.browser_finder.get_browser_paths()
        
        for i, (history_path, browser_name, browser_folder) in enumerate(browser_paths):
            progress = 10 + (i * 70 // max(len(browser_paths), 1))
            
            # Обновляем UI (если нужно)
            ui_redraw = self.__parameters.get('UIREDRAW')
            if ui_redraw:
                import asyncio
                asyncio.create_task(ui_redraw(f'Проверка {browser_name}...', progress))
            
            self.__parameters.get('LOG').Info('ChromiumHistory', f'Найден браузер: {browser_name}')
            records = self.history_parser.parse_history_file(history_path, browser_name)
            all_records.extend(records)
            print(f"Найдено записей в {browser_name}: {len(records)}")
        
        return all_records


class Parser:
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        self.history_processor = HistoryProcessor(parameters)
        
    def _convert_chrome_time(self, chrome_timestamp: int) -> str:
        """Конвертирует Chromium timestamp в читаемую дату"""
        return TimeConverter.convert_chrome_time(chrome_timestamp)

    def _parse_chrome_history(self, history_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг истории браузера"""
        return self.history_processor.history_parser.parse_history_file(history_path, browser_name)

    async def Start(self) -> Dict:
        storage = self.__parameters.get('STORAGE')
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        if not self.__parameters.get('DBCONNECTION').IsConnected():
            return {}
        
        # Структура полей для БД
        record_fields = {
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
        
        # Описание полей для интерфейса
        fields_description = {
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
        
        HELP_TEXT = """

"""
        
        # Настройка вывода
        output_writer.SetFields(fields_description, record_fields)
        output_writer.CreateDatabaseTables()
        
        await self.__parameters.get('UIREDRAW')('Поиск браузеров Chromium...', 10)
        
        # Обработка всех браузеров
        all_records = self.history_processor.process_all_browsers()
        
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
            'RecordsProcessed': str(len(all_records))
        }
        
        output_writer.SetInfo(info_data)
        output_writer.WriteMeta()
        await output_writer.CloseOutput()
        
        await self.__parameters.get('UIREDRAW')('Завершено!', 100)
        
        return {self.__parameters.get('MODULENAME'): output_writer.GetDBName()}