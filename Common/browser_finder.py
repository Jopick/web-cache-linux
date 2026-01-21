# -*- coding: utf-8 -*-
"""
Общий модуль для поиска браузеров Chromium на системе
"""

import os
from typing import List, Tuple, Optional


class BrowserFinder:
    """Класс для поиска браузеров Chromium на системе"""
    
    # Список поддерживаемых браузеров
    SUPPORTED_BROWSERS = [
        ('google-chrome', 'Google Chrome'),
        ('chromium', 'Chromium'), 
        ('microsoft-edge', 'Microsoft Edge'),
        ('opera', 'Opera'),
        ('brave', 'Brave')
    ]
    
    @staticmethod
    def get_browser_paths(base_path: str, file_name: str) -> List[Tuple[str, str, str]]:
        """
        Ищет файлы браузеров по заданному пути и имени файла
        
        Args:
            base_path: Базовый путь для поиска (например, '~/.config')
            file_name: Имя файла для поиска (например, 'History', 'Cookies')
            
        Returns:
            Список кортежей: (полный_путь_к_файлу, имя_браузера, папка_браузера)
        """
        browser_paths = []
        
        for browser_folder, browser_name in BrowserFinder.SUPPORTED_BROWSERS:
            full_path = os.path.join(
                os.path.expanduser(base_path), 
                browser_folder,
                'Default',
                file_name
            )
            
            if os.path.exists(full_path):
                browser_paths.append((full_path, browser_name, browser_folder))
                
        return browser_paths
    
    @staticmethod
    def get_history_paths() -> List[Tuple[str, str, str]]:
        """
        Ищет файлы истории браузеров
        
        Returns:
            Список кортежей: (путь_к_history, имя_браузера, папка_браузера)
        """
        return BrowserFinder.get_browser_paths('~/.config', 'History')
    
    @staticmethod
    def get_cookies_paths() -> List[Tuple[str, str, str]]:
        """
        Ищет файлы cookies браузеров
        
        Returns:
            Список кортежей: (путь_к_cookies, имя_браузера, папка_браузера)
        """
        return BrowserFinder.get_browser_paths('~/.config', 'Cookies')
    
    @staticmethod
    def get_bookmarks_paths() -> List[Tuple[str, str, str]]:
        """
        Ищет файлы закладок браузеров
        
        Returns:
            Список кортежей: (путь_к_bookmarks, имя_браузера, папка_браузера)
        """
        return BrowserFinder.get_browser_paths('~/.config', 'Bookmarks')
    
    @staticmethod
    def get_extensions_paths() -> List[Tuple[str, str, str]]:
        """
        Ищет папки расширений браузеров
        
        Returns:
            Список кортежей: (путь_к_extensions, имя_браузера, папка_браузера)
        """
        browser_paths = []
        
        for browser_folder, browser_name in BrowserFinder.SUPPORTED_BROWSERS:
            extensions_path = os.path.join(
                os.path.expanduser('~/.config'), 
                browser_folder,
                'Default',
                'Extensions'
            )
            
            if os.path.exists(extensions_path):
                browser_paths.append((extensions_path, browser_name, browser_folder))
                
        return browser_paths
    
    @staticmethod
    def find_browser_by_name(browser_name: str, file_type: str = 'History') -> Optional[str]:
        """
        Находит путь к конкретному файлу браузера по имени
        Returns:
            Путь к файлу или None если не найден
        """
        browser_name_lower = browser_name.lower()
        
        for browser_folder, name in BrowserFinder.SUPPORTED_BROWSERS:
            if name.lower() == browser_name_lower:
                file_path = os.path.join(
                    os.path.expanduser('~/.config'),
                    browser_folder,
                    'Default',
                    file_type
                )
                return file_path if os.path.exists(file_path) else None
                
        return None
    
    @staticmethod
    def get_all_available_browsers() -> List[str]:
        """
        Возвращает список всех браузеров, найденных на системе
        
        Returns:
            Список имен браузеров
        """
        available_browsers = []
        
        for browser_folder, browser_name in BrowserFinder.SUPPORTED_BROWSERS:
            # Проверяем наличие хотя бы одного файла браузера
            history_path = os.path.join(
                os.path.expanduser('~/.config'),
                browser_folder,
                'Default',
                'History'
            )
            
            if os.path.exists(history_path):
                available_browsers.append(browser_name)
                
        return available_browsers