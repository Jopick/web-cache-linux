# -*- coding: utf-8 -*-
"""
Модуль интерфейса обработки настроек

"""
import json

from typing import Any,Dict,NoReturn

#------------------------------------------------------------------------------    
class SettingsInterface():
    def __init__(self,logInterface):
        self.__settingsFileName:str = 'Settings.json'
        self.__settings:dict = {}
        self.__log = logInterface
        
        # Инициализировать настройки
        self.__ReadSettings()
        
    def __ReadSettings(self) -> NoReturn:
        with open(self.__settingsFileName,'rb') as f:
            try:
                self.__settings = json.load(f)
            except json.decoder.JSONDecodeError as e:
                message = f'Файл настроек содержит ошибки: {e}'
                self.__log.Error('SettingsInterface',message)
                
                self.__settings['CaseFolder'] = 'Cases'
                self.__settings['TemporaryFilesFolder'] = 'Temp'
                

    def GetSettings(self) -> Dict:
        return self.__settings
    
    def GetSettingValueByName(self,parameterName:str) -> Any:
        return self.__settings.get(parameterName)
    