# -*- coding: utf-8 -*-
"""
Общие утилиты для работы со временем Chrome
"""
from datetime import datetime

def convert_chrome_time(chrome_timestamp):
    """
    Конвертирует Chromium timestamp в читаемую дату
    """
    if not chrome_timestamp or chrome_timestamp == 0 or chrome_timestamp == '0':
        return ''
    
    try:
        # Если время передано как строка - конвертируем в int
        if isinstance(chrome_timestamp, str):
            chrome_timestamp = int(chrome_timestamp)
        
        # Chromium время: микросекунды с 1601-01-01
        # Конвертируем в Unix время (секунды с 1970-01-01)
        unix_timestamp = (chrome_timestamp / 1000000) - 11644473600
        dt = datetime.fromtimestamp(unix_timestamp)
        return dt.strftime('%Y.%m.%d %H:%M:%S')
    except (ValueError, OSError, OverflowError, TypeError):
        return ''
