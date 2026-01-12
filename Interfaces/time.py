# -*- coding: utf-8 -*-
"""Модуль для работы со временем и форматами Chromium"""

from datetime import datetime

def convert_chrome_time(chrome_timestamp) -> str:
    """Конвертирует Chromium timestamp в читаемую дату"""
    if not chrome_timestamp or chrome_timestamp == 0 or chrome_timestamp == '0':
        return ''
    
    try:
        # В закладках время хранится как СТРОКА, конвертируем в int
        if isinstance(chrome_timestamp, str):
            chrome_timestamp = int(chrome_timestamp)
        
        # Chromium время: микросекунды с 1601-01-01
        unix_timestamp = (chrome_timestamp / 1000000) - 11644473600
        dt = datetime.fromtimestamp(unix_timestamp)
        return dt.strftime('%Y.%m.%d %H:%M:%S')
    except (ValueError, OSError, OverflowError, TypeError):
        return 'Ошибка конвертации'

def _format_file_size(bytes_size: int) -> str:
    """Форматирует размер файла в читаемый вид"""
    if not bytes_size:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"
