# -*- coding: utf-8 -*-
"""
Модуль обработки истории браузера Chromium
"""
import os
from typing import Dict

class Parser():
    def __init__(self, parameters: dict):  
        self.__parameters = parameters
        
    async def Start(self) -> Dict:
        print("=== Chromium History Parser ===")
        print("Это тестовый запуск модуля")
        print("Параметры полученные модулем:")
        
        # Выводим полученные параметры для отладки
        for key, value in self.__parameters.items():
            if key not in ['DBCONNECTION', 'OUTPUTWRITER', 'REGISTRYFILEHANDLER']:
                print(f"  {key}: {value}")
        
        # Возвращаем пустой результат для теста
        return {"ChromiumHistory": "test_db.sqlite"}