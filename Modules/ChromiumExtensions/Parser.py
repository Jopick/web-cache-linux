# -*- coding: utf-8 -*-
"""
Модуль обработки расширений браузера Chromium
"""
import os, json
from typing import Dict, List, Tuple
from datetime import datetime

class Parser():
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        
    def _parse_extension_manifest(self, manifest_path: str) -> dict:
        """Парсит manifest.json расширения"""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка чтения manifest.json {manifest_path}: {e}")
            return {}

    def _safe_string(self, value) -> str:
        """Безопасно конвертирует значение в строку"""
        if value is None:
            return ''
        elif isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        else:
            return str(value)

    def _parse_chrome_extensions(self, extensions_path: str, browser_name: str) -> List[Tuple]:
        """Парсинг расширений браузера"""
        results = []
        
        if not os.path.exists(extensions_path):
            print(f"Папка расширений не найдена: {extensions_path}")
            return results
            
        try:
            print(f"Сканируем папку расширений: {extensions_path}")
            
            # Ищем все папки расширений
            for ext_id in os.listdir(extensions_path):
                ext_path = os.path.join(extensions_path, ext_id)
                if os.path.isdir(ext_path):
                    print(f"Найдено расширение ID: {ext_id}")
                    
                    # Ищем версии внутри расширения
                    for version in os.listdir(ext_path):
                        version_path = os.path.join(ext_path, version)
                        manifest_path = os.path.join(version_path, 'manifest.json')
                        
                        if os.path.exists(manifest_path):
                            print(f"  Версия: {version}, manifest: {manifest_path}")
                            manifest = self._parse_extension_manifest(manifest_path)
                            
                            if manifest:
                                # Получаем название (может быть в разных полях)
                                name = manifest.get('name', '')
                                if name.startswith('__MSG_'):
                                    # Локализованное название - берем из default_locale
                                    default_locale = manifest.get('default_locale', 'en')
                                    locales_path = os.path.join(version_path, '_locales', default_locale, 'messages.json')
                                    if os.path.exists(locales_path):
                                        try:
                                            with open(locales_path, 'r', encoding='utf-8') as f:
                                                locales = json.load(f)
                                                name_key = name.replace('__MSG_', '').replace('__', '')
                                                if name_key in locales:
                                                    name = locales[name_key].get('message', name)
                                        except:
                                            pass
                                
                                # Безопасно конвертируем все значения в строки
                                permissions = manifest.get('permissions', [])
                                if isinstance(permissions, list):
                                    permissions_str = ', '.join(permissions)
                                else:
                                    permissions_str = str(permissions)
                                
                                # Формируем запись (все поля как строки)
                                record = (
                                    self.__parameters.get('USERNAME', 'Unknown'),
                                    browser_name,
                                    ext_id,
                                    version,
                                    self._safe_string(name),
                                    self._safe_string(manifest.get('version', '')),
                                    self._safe_string(manifest.get('description', '')),
                                    self._safe_string(manifest.get('author', '')),
                                    permissions_str,
                                    manifest_path
                                )
                                results.append(record)
                                print(f"    Добавлено: {name} v{manifest.get('version', '')}")
            
        except Exception as e:
            print(f"Ошибка парсинга расширений: {e}")
            import traceback
            traceback.print_exc()
                
        return results

    async def Start(self) -> Dict:
        print("=== EXTENSIONS PARSER ЗАПУЩЕН ===")
        
        output_writer = self.__parameters.get('OUTPUTWRITER')
        
        if not self.__parameters.get('DBCONNECTION').IsConnected():
            return {}
        
        # Структура полей для БД
        record_fields = {
            'UserName': 'TEXT',
            'Browser': 'TEXT', 
            'ExtensionID': 'TEXT',
            'Version': 'TEXT',
            'Name': 'TEXT',
            'VersionNumber': 'TEXT',
            'Description': 'TEXT',
            'Author': 'TEXT',
            'Permissions': 'TEXT',
            'DataSource': 'TEXT'
        }
        
        # Описание полей для интерфейса
        fields_description = {
            'UserName': ('Имя пользователя', 120, 'string', 'Имя пользователя ОС'),
            'Browser': ('Браузер', 100, 'string', 'Название браузера'),
            'ExtensionID': ('ID расширения', 150, 'string', 'Уникальный идентификатор расширения'),
            'Version': ('Версия', 100, 'string', 'Версия папки расширения'),
            'Name': ('Название', 200, 'string', 'Название расширения'),
            'VersionNumber': ('Номер версии', 100, 'string', 'Номер версии из manifest'),
            'Description': ('Описание', 300, 'string', 'Описание расширения'),
            'Author': ('Автор', 150, 'string', 'Автор расширения'),
            'Permissions': ('Права', 400, 'string', 'Права доступа расширения'),
            'DataSource': ('Источник данных', 200, 'string', 'Путь к manifest.json')
        }
        
        HELP_TEXT = """
Chromium Extensions Parser:
Расширения браузеров на базе Chromium

Извлекается из папок:
~/.config/google-chrome/Default/Extensions/
~/.config/chromium/Default/Extensions/

Данные включают:
- Названия расширений
- Идентификаторы и версии
- Описания и авторов
- Права доступа
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
            
            extensions_path = os.path.join(
                os.path.expanduser('~'),
                '.config', 
                browser_folder,
                'Default',
                'Extensions'
            )
            
            if os.path.exists(extensions_path):
                self.__parameters.get('LOG').Info('ChromiumExtensions', f'Найден браузер: {browser_name}')
                records = self._parse_chrome_extensions(extensions_path, browser_name)
                all_records.extend(records)
                print(f"Найдено расширений в {browser_name}: {len(records)}")
        
        # Запись результатов
        await self.__parameters.get('UIREDRAW')('Запись результатов...', 80)
        
        for record in all_records:
            try:
                output_writer.WriteRecord(record)
            except Exception as e:
                print(f"Ошибка записи записи в БД: {e}")
                print(f"Проблемная запись: {record}")
        
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