# -*- coding: utf-8 -*-
"""
Модуль обработки закладок браузера Chromium
"""
import os, json
from typing import Dict, List, Tuple
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from Common.time_utils import convert_chrome_time
from Interfaces.time import _format_file_size

class Parser():
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        
    #def _convert_chrome_time(self, chrome_timestamp) -> str:
    #    """Конвертирует Chromium timestamp в читаемую дату"""
    #    if not chrome_timestamp or chrome_timestamp == 0 or chrome_timestamp == '0':
    #        return ''
    #        
    #    try:
    #        # В закладках время хранится как СТРОКА, конвертируем в int
    #        if isinstance(chrome_timestamp, str):
    #            chrome_timestamp = int(chrome_timestamp)
    #        
    #        # Chromium время: микросекунды с 1601-01-01
    #        unix_timestamp = (chrome_timestamp / 1000000) - 11644473600
    #        dt = datetime.fromtimestamp(unix_timestamp)
    #        return dt.strftime('%Y.%m.%d %H:%M:%S')
    #    except (ValueError, OSError, OverflowError, TypeError) as e:
     #       print(f"Ошибка конвертации времени {chrome_timestamp}: {e}")
     #       return 'Ошибка конвертации'

    def _parse_chrome_bookmarks(self, bookmarks_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг закладок браузера - исправленная версия"""
        results = []
        
        if not os.path.exists(bookmarks_path):
            print(f"Файл закладок не найден: {bookmarks_path}")
            return results
            
        try:
            with open(bookmarks_path, 'r', encoding='utf-8') as f:
                bookmarks_data = json.load(f)
            
            print(f"Успешно загружен JSON из {bookmarks_path}")
            
            # Парсим корневые элементы
            roots = bookmarks_data.get('roots', {})
            print(f"Найдено корневых элементов: {list(roots.keys())}")
            
            # Обрабатываем все корневые папки
            for root_name, root_node in roots.items():
                if root_node:
                    folder_name = {
                        'bookmark_bar': 'Панель закладок',
                        'other': 'Другие закладки', 
                        'synced': 'Синхронизированные'
                    }.get(root_name, root_name)
                    
                    # Рекурсивно обрабатываем все вложенные элементы
                    bookmarks_in_folder = self._process_bookmark_node(root_node, folder_name, browser_name, bookmarks_path)
                    results.extend(bookmarks_in_folder)
                    print(f"В папке '{folder_name}' найдено закладок: {len(bookmarks_in_folder)}")
            
            print(f"Всего найдено закладок: {len(results)}")
                    
        except Exception as e:
            print(f"Ошибка парсинга закладок: {e}")
            import traceback
            traceback.print_exc()
                
        return results

    def _process_bookmark_node(self, node: dict, current_path: str, browser_name: str, data_source: str) -> List[Tuple]:
        """Обрабатывает узел закладки (рекурсивно)"""
        results = []
        
        if not node:
            return results
            
        node_type = node.get('type')
        
        if node_type == 'url':
            # Это закладка - добавляем в результаты
            try:
                # Конвертируем время (оно может быть строкой!)
                date_added = node.get('date_added', 0)
                date_modified = node.get('date_modified', 0)
                
                # Если время строка - конвертируем в int
                if isinstance(date_added, str):
                    date_added = int(date_added) if date_added and date_added != '0' else 0
                if isinstance(date_modified, str):
                    date_modified = int(date_modified) if date_modified and date_modified != '0' else 0
                
                bookmark = (
                    'ivan',  # временно фиксированное имя
                    browser_name,
                    current_path,
                    node.get('name', 'Без имени'),
                    node.get('url', ''),
                    date_added,
                    self._convert_chrome_time(date_added),
                    date_modified,
                    self._convert_chrome_time(date_modified),
                    data_source
                )
                results.append(bookmark)
                print(f"Добавлена закладка: {node.get('name')}")
                
            except Exception as e:
                print(f"Ошибка обработки закладки {node.get('name')}: {e}")
                
        elif node_type == 'folder':
            # Это папка - обрабатываем детей рекурсивно
            folder_name = node.get('name', 'Без имени')
            new_path = f"{current_path}/{folder_name}"
            
            for child in node.get('children', []):
                child_results = self._process_bookmark_node(child, new_path, browser_name, data_source)
                results.extend(child_results)
                
        return results

    async def Start(self) -> Dict:
        print("=== BOOKMARKS PARSER ЗАПУЩЕН ===")
        
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        # Структура полей для БД
        record_fields = {
            'UserName': 'TEXT',
            'Browser': 'TEXT', 
            'Folder': 'TEXT',
            'Title': 'TEXT',
            'URL': 'TEXT',
            'DateAddedUTC': 'INTEGER',
            'DateAdded': 'TEXT',
            'DateModifiedUTC': 'INTEGER',
            'DateModified': 'TEXT',
            'DataSource': 'TEXT'
        }
        
        fields_description = {
            'UserName': ('Имя пользователя', 120, 'string', 'Имя пользователя ОС'),
            'Browser': ('Браузер', 100, 'string', 'Название браузера'),
            'Folder': ('Папка', 200, 'string', 'Папка закладки'),
            'Title': ('Название', 250, 'string', 'Название закладки'),
            'URL': ('URL', 350, 'string', 'Адрес закладки'),
            'DateAddedUTC': ('Дата добавления (UTC)', -1, 'integer', 'Временная метка добавления'),
            'DateAdded': ('Дата добавления', 180, 'string', 'Дата и время добавления'),
            'DateModifiedUTC': ('Дата изменения (UTC)', -1, 'integer', 'Временная метка изменения'),
            'DateModified': ('Дата изменения', 180, 'string', 'Дата и время изменения'),
            'DataSource': ('Источник данных', 200, 'string', 'Путь к файлу закладок')
        }
        
        # Настройка вывода
        output_writer.SetFields(fields_description, record_fields)
        output_writer.CreateDatabaseTables()
        
        # Тестовый парсинг
        bookmarks_path = os.path.expanduser('~/.config/google-chrome/Default/Bookmarks')
        
        if os.path.exists(bookmarks_path):
            records = self._parse_chrome_bookmarks(bookmarks_path, 'Google Chrome')
            print(f"Итоговое количество закладок: {len(records)}")
            
            # Запись результатов
            for record in records:
                output_writer.WriteRecord(record)
            
            # Покажем первые 5 закладок
            for i, record in enumerate(records[:5]):
                print(f"{i+1}. [{record[2]}] {record[3]} - {record[4]}")
        else:
            print("Файл закладок не найден")
        
        # Завершение работы
        output_writer.RemoveTempTables()
        await output_writer.CreateDatabaseIndexes(self.__parameters.get('MODULENAME'))
        
        info_data = {
            'Name': self.__parameters.get('MODULENAME'),
            'Help': 'Bookmarks парсер для Chromium браузеров',
            'Timestamp': self.__parameters.get('CASENAME'),
            'Vendor': 'LabFramework'
        }
        
        output_writer.SetInfo(info_data)
        output_writer.WriteMeta()
        await output_writer.CloseOutput()
        
        return {self.__parameters.get('MODULENAME'): output_writer.GetDBName()}