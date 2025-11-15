# -*- coding: utf-8 -*-
"""
Модуль журналирования сообщений ПО

"""

import os
import logging
import traceback
#------------------------------------------------------------------------------
class LogInterface():
    def __init__(self,appStartDateTime:str):
        self.__logPath = os.path.join(os.getcwd(),'Logs', f'{appStartDateTime}.log')  
        logging.basicConfig(level=logging.INFO,
                                filename=self.__logPath,
                                filemode='w',
                                format='%(asctime)s___%(levelname)s___%(message)s')

    def Error(self,sourceName,message):
        logging.error(f'{sourceName}: {message}')
        
    def Warn(self,sourceName,message):
        logging.warning(f'{sourceName}: {message}')
        
    def Info(self,sourceName,message):
        logging.info(f'{sourceName}: {message}')
            
    @staticmethod
    def DeathRattle(exc_type,exc_value,exc_traceback):
        logging.error('UNCAUGHT EXCEPTION IN MODULE!',
                        exc_info = (exc_type,exc_value,exc_traceback))
        
        print('UNCAUGHT EXCEPTION IN MODULE!')
        print((exc_type,exc_value))
        print(''.join(traceback.format_tb(exc_traceback)))
        