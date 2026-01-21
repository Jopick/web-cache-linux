# -*- coding: utf-8 -*-
"""
Модуль обработки истории загрузок браузера Chromium
"""
import os, sqlite3, shutil
from typing import Dict, List, Tuple
from datetime import datetime
from Common.time_utils import convert_chrome_time
from Common.browser_finder import BrowserFinder

class FileSizeFormatter:
    """Класс для форматирования размеров файлов"""
    
    @staticmethod
    def _format_file_size(bytes_size: int) -> str:
        """Форматирует размер файла в читаемый вид"""
        if not bytes_size:
            return "0 B"
            
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"


class DownloadsParser:
    """Класс для парсинга истории загрузок"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
        self._size_formatter = FileSizeFormatter()
    
    def _parse_chrome_downloads(self, history_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг истории загрузок браузера"""
        results = []
        
        if not os.path.exists(history_path):
            return results
            
        # Создаем временную копию для избежания блокировки
        temp_dir = self.__parameters.get('TEMP')
        temp_path = os.path.join(temp_dir, f'temp_downloads_{os.path.basename(history_path)}')
        
        try:
            shutil.copy2(history_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            # Проверяем существование таблицы downloads
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='downloads'")
            if not cursor.fetchone():
                return results
            
            # Получаем историю загрузок
            query = """
            SELECT 
                id,
                target_path,
                tab_url,
                tab_referrer_url,
                start_time,
                end_time,
                received_bytes,
                total_bytes,
                state,
                danger_type,
                interrupt_reason,
                opened,
                last_access_time
            FROM downloads 
            ORDER BY start_time DESC
            """
            
            cursor.execute(query)
            
            for row in cursor.fetchall():
                if len(row) < 13:  # Если данных меньше ожидаемых
                    continue  # Пропускаем эту строку
        
                # Извлекаем значения с преобразованием типов
                download_id = int(row[0]) if row[0] is not None else 0
                target_path = str(row[1]) if row[1] is not None else ''
                tab_url = str(row[2]) if row[2] is not None else ''
                tab_referrer_url = str(row[3]) if row[3] is not None else ''
                start_time = int(row[4]) if row[4] is not None else 0
                end_time = int(row[5]) if row[5] is not None else 0
                received_bytes = int(row[6]) if row[6] is not None else 0
                total_bytes = int(row[7]) if row[7] is not None else 0
                state = int(row[8]) if row[8] is not None else 0
                danger_type = int(row[9]) if row[9] is not None else 0
                interrupt_reason = int(row[10]) if row[10] is not None else 0
                opened = int(row[11]) if row[11] is not None else 0
                last_access_time = int(row[12]) if row[12] is not None else 0
                
                # Конвертируем временные метки
                start_date = convert_chrome_time(start_time)
                end_date = convert_chrome_time(end_time)
                last_access_date = convert_chrome_time(last_access_time)
                
                # Определяем статус загрузки
                state_map = {
                    0: "В процессе",
                    1: "Завершена",
                    2: "Отменена",
                    3: "Прервана"
                }
                status = state_map.get(state, "Неизвестно")
                
                # Определяем уровень опасности
                danger_map = {
                    0: "Безопасный",
                    1: "Опасный",
                    2: "Подозрительный", 
                    3: "Не проверен",
                    4: "Разрешен пользователем"
                }
                danger_level = danger_map.get(danger_type, "Неизвестно")
                
                # Форматируем размеры файлов
                received_size = self._size_formatter._format_file_size(received_bytes)
                total_size = self._size_formatter._format_file_size(total_bytes)
                
                # Вычисляем прогресс загрузки
                progress = 0
                if total_bytes and total_bytes > 0:
                    progress = min(100, int((received_bytes / total_bytes) * 100))
                
                record = (
                    self.__parameters.get('USERNAME', 'Unknown'),
                    browser_name,
                    download_id or 0,
                    target_path or '',
                    tab_url or '',
                    tab_referrer_url or '',
                    start_time or 0,
                    start_date,
                    end_time or 0,
                    end_date,
                    received_bytes or 0,
                    received_size,
                    total_bytes or 0,
                    total_size,
                    progress,
                    status,
                    danger_level,
                    bool(opened),
                    history_path
                )
                results.append(record)
                
        except sqlite3.Error as e:
            self.__parameters.get('LOG').Warn('ChromiumDownloads', f'Ошибка парсинга загрузок: {e}')
        except Exception as e:
            self.__parameters.get('LOG').Error('ChromiumDownloads', f'Критическая ошибка: {e}')
        finally:
            if 'conn' in locals():
                conn.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        return results

    async def find_and_parse_browsers(self) -> List[Tuple]:
        """Поиск браузеров и сбор данных"""
        all_records = []
        
        # ИСПОЛЬЗУЕМ ОБЩИЙ BrowserFinder
        browser_paths = BrowserFinder.get_history_paths()
        
        for i, (history_path, browser_name, browser_folder) in enumerate(browser_paths):
            progress = 10 + (i * 70 // max(len(browser_paths), 1))
            
            # Обновляем UI прогресса
            ui_redraw = self.__parameters.get('UIREDRAW')
            if ui_redraw:
                import asyncio
                asyncio.create_task(ui_redraw(f'Проверка {browser_name}...', progress))
            
            self.__parameters.get('LOG').Info('ChromiumDownloads', f'Найден браузер: {browser_name}')
            records = self._parse_chrome_downloads(history_path, browser_name)
            all_records.extend(records)
            print(f"Найдено загрузок в {browser_name}: {len(records)}")
        
        return all_records
class OutputConfigurator:
    """Класс для настройки вывода данных"""
    
    def __init__(self, parameters: dict):
        self.__parameters = parameters
    
    def _configure_output(self, output_writer):
        """Настраивает поля и структуру вывода"""
        # Структура полей для БД
        record_fields = {
            'UserName': 'TEXT',
            'Browser': 'TEXT', 
            'DownloadID': 'INTEGER',
            'FilePath': 'TEXT',
            'SourceURL': 'TEXT',
            'ReferrerURL': 'TEXT',
            'StartTimeUTC': 'INTEGER',
            'StartDate': 'TEXT',
            'EndTimeUTC': 'INTEGER',
            'EndDate': 'TEXT',
            'ReceivedBytes': 'INTEGER',
            'ReceivedSize': 'TEXT',
            'TotalBytes': 'INTEGER',
            'TotalSize': 'TEXT',
            'Progress': 'INTEGER',
            'Status': 'TEXT',
            'DangerLevel': 'TEXT',
            'Opened': 'INTEGER',
            'DataSource': 'TEXT'
        }
        
        # Описание полей для интерфейса
        fields_description = {
            'UserName': ('Имя пользователя', 120, 'string', 'Имя пользователя ОС'),
            'Browser': ('Браузер', 100, 'string', 'Название браузера'),
            'DownloadID': ('ID загрузки', 80, 'integer', 'Уникальный идентификатор загрузки'),
            'FilePath': ('Путь к файлу', 300, 'string', 'Локальный путь к скачанному файлу'),
            'SourceURL': ('URL источника', 350, 'string', 'URL откуда скачивался файл'),
            'ReferrerURL': ('URL реферера', 350, 'string', 'URL страницы с которой начата загрузка'),
            'StartTimeUTC': ('Начало (UTC)', -1, 'integer', 'Временная метка начала загрузки'),
            'StartDate': ('Дата начала', 180, 'string', 'Дата и время начала загрузки'),
            'EndTimeUTC': ('Конец (UTC)', -1, 'integer', 'Временная метка завершения загрузки'),
            'EndDate': ('Дата завершения', 180, 'string', 'Дата и время завершения загрузки'),
            'ReceivedBytes': ('Получено байт', -1, 'integer', 'Количество полученных байт'),
            'ReceivedSize': ('Получено', 100, 'string', 'Полученный размер в читаемом формате'),
            'TotalBytes': ('Всего байт', -1, 'integer', 'Общий размер файла в байтах'),
            'TotalSize': ('Общий размер', 100, 'string', 'Общий размер в читаемом формате'),
            'Progress': ('Прогресс %', 80, 'integer', 'Процент завершения загрузки'),
            'Status': ('Статус', 100, 'string', 'Статус загрузки'),
            'DangerLevel': ('Уровень опасности', 120, 'string', 'Уровень опасности файла'),
            'Opened': ('Открыт', 60, 'boolean', 'Файл был открыт после загрузки'),
            'DataSource': ('Источник данных', 200, 'string', 'Путь к файлу истории')
        }
        
        output_writer.SetFields(fields_description, record_fields)
        output_writer.CreateDatabaseTables()




class Parser:
    """Основной класс-координатор"""
    
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        self._downloads_parser = DownloadsParser(parameters)
        self._output_configurator = OutputConfigurator(parameters)
    
    async def Start(self) -> Dict:
        storage = self.__parameters.get('STORAGE')
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        if not self.__parameters.get('DBCONNECTION').IsConnected():
            return {}
        
        HELP_TEXT = """
Chromium Downloads Parser:
История загрузок браузеров на базе Chromium

Извлекается из таблицы downloads файлов:
~/.config/google-chrome/Default/History
~/.config/chromium/Default/History

Данные включают:
- Пути к скачанным файлам
- URL источников загрузок
- Размеры файлов и прогресс загрузки
- Статусы загрузок (завершена, отменена, в процессе)
- Уровни опасности файлов
- Временные метки начала и завершения
"""
        
        # Настройка вывода
        self._output_configurator._configure_output(output_writer)
        
        await self.__parameters.get('UIREDRAW')('Поиск браузеров Chromium...', 10)
        
        # Поиск браузеров и сбор данных
        all_records = await self._downloads_parser.find_and_parse_browsers()
        
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