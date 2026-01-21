# -*- coding: utf-8 -*-
"""
Общие утилиты для работы со временем Chrome
"""

from datetime import datetime, timedelta


def convert_chrome_time(chrome_timestamp: int) -> str:
    """
    Конвертирует временную метку Chrome в читаемую дату.
    Chrome timestamp = микросекунды с 1601-01-01
    
    """
    if not chrome_timestamp or chrome_timestamp == 0:
        return ""
    
    try:
        # Chrome epoch: 1601-01-01
        chrome_epoch = datetime(1601, 1, 1)
        
        # Конвертируем микросекунды в секунды
        delta_seconds = chrome_timestamp / 1_000_000
        
        # Добавляем к Chrome epoch
        result_time = chrome_epoch + timedelta(seconds=delta_seconds)
        
        return result_time.strftime('%Y.%m.%d %H:%M:%S')
    
    except (ValueError, OverflowError, OSError):
        return ""


# Функции из cookies модуля
def get_cookie_type(is_persistent: int) -> str:
    """Определяет тип cookie"""
    return "Сессионный" if not is_persistent else "Постоянный"


def get_priority_text(priority: int) -> str:
    """Возвращает текстовое представление приоритета cookie"""
    priority_map = {0: "Низкий", 1: "Средний", 2: "Высокий"}
    return priority_map.get(priority, "Неизвестно")


def get_samesite_text(samesite: int) -> str:
    """Возвращает текстовое представление SameSite cookie"""
    samesite_map = {-1: "Не задано", 0: "Не задано", 1: "Lax", 2: "Strict", 3: "None"}
    return samesite_map.get(samesite, "Неизвестно")