# -*- coding: utf-8 -*-
"""
Модуль основного интерфейса

"""
import os,shutil
from typing import Any,AnyStr,Dict,NoReturn
from datetime import datetime
import re
from abc import ABCMeta, abstractmethod
import sys
import argparse

from Common.Codes import ExitCode
from Common.Routines import FileContentReader
from Interfaces.LogInterface import LogInterface
from Interfaces.SettingsInterface import SettingsInterface
from Interfaces.Solver import Solver

#----------------------------------------------------------------
class Interface():
    def __init__(self):
        # Время старта ПО для лога и создания каталога хранения результатов
        self.__appStartDateTime:str = str(datetime.now()).split('.')[0].replace(':','_')
        
        # Интерфейс журналирования сообщений ПО
        self.__log:LogInterface = LogInterface(self.__appStartDateTime)
        
        # Интерфейс инициализации настроек
        self.__settingsInterface:SettingsInterface = SettingsInterface(self.__log)
        
        # Интерфейс работы с файлами
        self.__fileContentReader:FileContentReader = FileContentReader()
        
        
        # Параметры из настроек
        self.__caseFolder:str = self.__settingsInterface.GetSettingValueByName('CaseFolder')
        self.__tempFolder:str = self.__settingsInterface.GetSettingValueByName('TemporaryFilesFolder')
        
        # Параметры запуска
        self.__dataSourceFullPath:str = None
        self.__outputFileName:str = None
        
        
        # Сформировать словарь интерфейсов приложения        
        self.interfaces:dict = {'LOGGER':self.__log}
        
        self._solver:Solver = None
        
        # Предварительная подготовка к запуску
        self.__ClearTempFolder()
        self.__CheckCaseFolder()
        
    @property
    def GetAppStartDateTime(self) -> AnyStr:
        return self.__appStartDateTime
    
    @property
    def GetSettings(self) -> Dict:
        return self.__settingsInterface.GetSettings()
    
    def GetSettingValueByName(self,parameterName:str) -> Any:
        return self.__settingsInterface.GetSettingValueByName(parameterName)
        
    def __ClearTempFolder(self) -> NoReturn:
        if not os.path.exists(self.__tempFolder):
            os.mkdir(self.__tempFolder)
            message = f'Каталог временных файлов воссоздан: {self.__tempFolder}'
            self.__log.Info('Interface',message)
            return
            
        files:list = self.__fileContentReader.ListDir(self.__tempFolder)
        for file in files:
            filePath = os.path.join(os.getcwd(),self.__tempFolder,file)
            try:
                os.remove(filePath)
            except FileNotFoundError:
                pass

    def __CheckCaseFolder(self) -> NoReturn:
        if not os.path.exists(self.__caseFolder):
            os.mkdir(self.__caseFolder)
            message = f'Каталог кейсов воссоздан: {self.__caseFolder}'
            self.__log.Info('Interface',message)
        
    
    async def Run(self,exitStatus) -> NoReturn: 
        # Инициализировать обработку параметров командной строки
        cliParamsParser = argparse.ArgumentParser(description='CFIR Laboratories Framework')
        cliParamsParser.add_argument('--source_folder',type=str,default='Source',help='Полный путь до каталога с исходными данными для анализа')
        cliParamsParser.add_argument('--output_name',type=str,default='result.sqlite',help='Имя файла с результатами')
        cliParamsParser.add_help
        
        parameters = cliParamsParser.parse_args()
        
        # Выход, если параметры не заданы
        if parameters.source_folder is None or parameters.output_name is None:
            cliParamsParser.print_help()
            exitStatus.status = ExitCode.InputParametersError.value
            return 
        
        # Инициализция параметров из командной строки
        self.__dataSourceFullPath = parameters.source_folder
        self.__outputFileName = parameters.output_name
        
        # Инцициализация модуля-загрузчика логики обработки данных
        self._solver = Solver(self.GetSettings,
                            self.__appStartDateTime,
                            self.interfaces,
                            self.__dataSourceFullPath,
                            self.__outputFileName)
                            
                            
        result = await self._solver.Start()
        if result:
            exitStatus.status = ExitCode.Ok.value
            return
        
        
        
        
        

        
        
        
        
        