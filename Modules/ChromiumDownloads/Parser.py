# -*- coding: utf-8 -*-
"""
Модуль обработки истории загрузок браузера Chromium
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
            return ''
            
        try:
            # Chromium время: микросекунды с 1601-01-01
            unix_timestamp = (chrome_timestamp / 1000000) - 11644473600
            dt = datetime.fromtimestamp(unix_timestamp)
            return dt.strftime('%Y.%m.%d %H:%M:%S')
        except (ValueError, OSError, OverflowError):
            return 'Ошибка конвертации'

    def _format_file_size(self, bytes_size: int) -> str:
        """Форматирует размер файла в читаемый вид"""
        if not bytes_size:
            return "0 B"
            
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"

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
                try:
                    (download_id, target_path, tab_url, tab_referrer_url, start_time,
                    end_time, received_bytes, total_bytes, state, danger_type,
                    interrupt_reason, opened, last_access_time) = (
                        row[0] if len(row) > 0 else 0,
                        row[1] if len(row) > 1 else '',
                        row[2] if len(row) > 2 else '',
                        row[3] if len(row) > 3 else '',
                        row[4] if len(row) > 4 else 0,
                        row[5] if len(row) > 5 else 0,
                        row[6] if len(row) > 6 else 0,
                        row[7] if len(row) > 7 else 0,
                        row[8] if len(row) > 8 else 0,
                        row[9] if len(row) > 9 else 0,
                        row[10] if len(row) > 10 else 0,
                        row[11] if len(row) > 11 else 0,
                        row[12] if len(row) > 12 else 0
                    )
                except IndexError:
                    continue
                
                # Конвертируем временные метки
                start_date = self._convert_chrome_time(start_time)
                end_date = self._convert_chrome_time(end_time)
                last_access_date = self._convert_chrome_time(last_access_time)
                
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
                received_size = self._format_file_size(received_bytes)
                total_size = self._format_file_size(total_bytes)
                
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

    async def Start(self) -> Dict:
        storage = self.__parameters.get('STORAGE')
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        if not self.__parameters.get('DBCONNECTION').IsConnected():
            return {}
        
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
            
            history_path = os.path.join(
                os.path.expanduser('~'),
                '.config', 
                browser_folder,
                'Default',
                'History'
            )
            
            if os.path.exists(history_path):
                self.__parameters.get('LOG').Info('ChromiumDownloads', f'Найден браузер: {browser_name}')
                records = self._parse_chrome_downloads(history_path, browser_name)
                all_records.extend(records)
                print(f"Найдено загрузок в {browser_name}: {len(records)}")
        
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