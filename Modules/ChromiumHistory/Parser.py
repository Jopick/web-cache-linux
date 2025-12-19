# -*- coding: utf-8 -*-
"""
Модуль обработки истории браузера Chromium
"""
import os
import sqlite3
import shutil
from typing import Dict, List, Tuple
from datetime import datetime


class Parser:
    def __init__(self, parameters: dict):
        self.__parameters = parameters

    def _convert_chrome_time(self, chrome_timestamp: int) -> str:
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

    def _parse_chrome_history(self, history_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг истории браузера"""
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
                url, title, visit_count, typed_count, last_visit_time = row

                # Конвертируем время
                visit_date = self._convert_chrome_time(last_visit_time)

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

    async def Start(self) -> Dict:
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
            'VisitDate': 'TEXT',
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
            'VisitDate': ('Дата посещения', 180, 'string', 'Дата и время посещения'),
            'DataSource': ('Источник данных', 200, 'string', 'Путь к файлу истории')
        }

        HELP_TEXT = """
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
                self.__parameters.get('LOG').Info('ChromiumHistory', f'Найден браузер: {browser_name}')
                records = self._parse_chrome_history(history_path, browser_name)
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