# -*- coding: utf-8 -*-
"""
Модуль рутин по работе с файлами

"""

import os,io,re,regipy,shutil
import sqlite3
from enum import IntEnum
from construct import core
from abc import ABCMeta, abstractmethod
from typing import Any,AnyStr,List,Tuple,Dict,NoReturn,Optional
from datetime import datetime,timedelta,tzinfo 
from calendar import timegm


UNIX_EPOCH_AS_FILETIME:int = 116444736000000000  # January 1, 1970 as MS file time

# Разница между UnixEpoch и Cocoa/WebKit
COCOA_AT_UNIXEPOCH:int = 978307200

HUNDREDS_OF_NANOSECONDS:int = 10000000
NANOSECONDS_DELIMITER:float = 1000000000.

#----------------------------------------------------------------
#----------------------------------------------------------------
#------------КЛАССЫ ДЛЯ РАБОТЫ С РЕЕСТРОМ WINDOWS----------------
#----------------------------------------------------------------
#----------------------------------------------------------------
# Абстрактный обработчик файла-улья реестра
class _AbstractRegistryFileHandler():
    __metaclass__ = ABCMeta
    def __init__(self,tempFolder:str,log:Any):
        # Входные параметры
        self._fcr:Any = FileContentReader()
        self._tempFolder:str = tempFolder
        self._log:Any = log
                
        self._regHandle:regipy.registry.RegistryHive = None
        self._regFileFullPath:str = None
        self._storageRegFileFullPath:str = None
        
    def __del__(self):
        self._regHandle = None
        self._storageRegFileFullPath = None
        
    def SetStorageRegistryFileFullPath(self,fullPath) -> NoReturn:
        self._storageRegFileFullPath = fullPath
    
    @abstractmethod
    def GetRegistryHandle(self):
        pass

    def GetRegistryPath(self) -> AnyStr:
        return self._regFileFullPath
        
    def _RemoveRegistryFile(self):
        if self._regFileFullPath is not None:
            try:
                os.remove(self._regFileFullPath)
            except OSError as e:
                message = f'Файл не может быть удален: {e}!'
                self._log.Warn(f'_AbstractRegistryFileHandler._RemoveRegistryFile: ',message)
        
#------------------------------------------------------------------------------
# Обработчик файла-улья без изменений
class RegistryFileHandler(_AbstractRegistryFileHandler):
    def __init__(self,tempFolder:str,log:Any):
        super().__init__(tempFolder,log)
             
    def GetRegistryHandle(self) -> Optional[regipy.registry.RegistryHive]:
        if self._storageRegFileFullPath is not None:
            # Сделать копию во временный каталог
            #regFileName:str = self._storageRegFileFullPath.rsplit('\\',1)[1]
            regFileName:str = os.path.basename(self._storageRegFileFullPath)
            self._regFileFullPath = os.path.join(self._tempFolder,regFileName)
            shutil.copy(self._storageRegFileFullPath,self._regFileFullPath)
            
            # Передать файл реестра на вход regipy и получить хэндл
            try:
                self._regHandle = regipy.registry.RegistryHive(self._regFileFullPath)
            except (FileNotFoundError,PermissionError,BaseException):
                self._regHandle = None
                
        else:
            self._regHandle = None
            
        # Удалить копию файла реестра - содержимое считано в оперативку
        self._RemoveRegistryFile()     

        return self._regHandle

#----------------------------------------------------------------
#----------------------------------------------------------------
#----------------КЛАССЫ ДЛЯ РАБОТЫ С ВРЕМЕННЫМИ МЕТКАМИ----------
#----------------------------------------------------------------
class UTC(tzinfo):
    """UTC"""
    def utcoffset(self, dt:datetime) -> timedelta:
        return timedelta(0)

    def tzname(self, dt:datetime) -> AnyStr:
        return "UTC"

    def dst(self, dt:datetime) -> timedelta:
        return timedelta(0)
#----------------------------------------------------------------
class FixedOffset(tzinfo):
    # Класс для задания смещения часового пояса
    def __init__(self,offset:int,name:str):
        if offset >= 0:
            self.__offset = timedelta(minutes = offset)
        else:
            self.__offset = timedelta(days = -1,
                                      minutes = 24*60-abs(offset))
        self.__name = name
        
    def utcoffset(self,dt:datetime=None) -> timedelta:
        return self.__offset
    
    def tzname(self,dt:str='') -> AnyStr:
        return self.__name
    
    def dst(self,dt=None) -> timedelta:
        return timedelta(0)
#----------------------------------------------------------------
class TimeConverter():
    @staticmethod               
    def UnixTimestampToDatetime(unixTimestamp:int,addMicroseconds:bool=False) -> datetime: 
        if not addMicroseconds:
            dtObj = datetime.fromtimestamp(unixTimestamp,UTC())
            return dtObj
        else:
            ts,micro = divmod(unixTimestamp,1000000)
            dtObj = datetime.fromtimestamp(ts,UTC())
            dtObj.replace(microsecond=micro)
            return dtObj
    
    @staticmethod               
    def DatetimeToFILETIME(datetimeObject) -> int:
        """
        Converts a datetime to Microsoft filetime format. If the object is
        time zone-naive, it is forced to UTC before conversion.

        DatetimeToFILETIME(datetime(2009, 7, 25, 23, 0))
        '128930364000000000'

        DatetimeToFILETIME(datetime(1970, 1, 1, 0, 0, tzinfo=utc))
        '116444736000000000'
    
        DatetimeToFILETIME(datetime(2009, 7, 25, 23, 0, 0, 100))
        128930364000001000
        """
        if (datetimeObject.tzinfo is None) or (datetimeObject.tzinfo.utcoffset(datetimeObject) is None):
            datetimeObject = datetimeObject.replace(tzinfo=UTC())
        ft = UNIX_EPOCH_AS_FILETIME + (timegm(datetimeObject.timetuple()) * HUNDREDS_OF_NANOSECONDS)
        return ft + (datetimeObject.microsecond * 10)
    
    @staticmethod
    def FILETIMEToDatetime(FTtimestamp,tzInfoStruct=None) -> datetime:
        """
        Converts a Microsoft filetime number to a Python datetime. The new
        datetime object is time zone-naive but is equivalent to tzinfo=utc.

        FILETIMEToDatetime(116444736000000000)
        datetime.datetime(1970, 1, 1, 0, 0)

        FILETIMEToDatetime(128930364000000000)
        datetime.datetime(2009, 7, 25, 23, 0)
    
        FILETIMEToDatetime(128930364000001000)
        datetime.datetime(2009, 7, 25, 23, 0, 0, 100)
        """
        # Get seconds and remainder in terms of Unix epoch
        (s, ns100) = divmod(FTtimestamp - UNIX_EPOCH_AS_FILETIME, HUNDREDS_OF_NANOSECONDS)
        # Convert to datetime object
        try:
            if tzInfoStruct is not None:
                dt = datetime.fromtimestamp(s,tz=tzInfoStruct)
            else:
                dt = datetime.fromtimestamp(s,tz=UTC())
        except OSError:
            dt = datetime.fromtimestamp(UNIX_EPOCH_AS_FILETIME,tz=UTC())
        # Add remainder in as microseconds. Python 3.2 requires an integer
        dt = dt.replace(microsecond=(ns100 // 10))
 
        return dt
        
    @staticmethod
    def CocoaTimeToFILETIME(cocoaTimestamp,nanoSec=False) -> int:
        # ВО Cocoa это количество секунд(наносекунд) с 00:00 01.01.2001
        # cocoaDateTimeBase = datetime(2001,1,1)
        # unixDateTimeBase = datetime(1970,1,1)
        # delta = cocoaDateTimeBase - unixDateTimeBase
        delta = timedelta(seconds=COCOA_AT_UNIXEPOCH)

        if cocoaTimestamp not in (0, None, ''):
            if type(cocoaTimestamp) == str or\
                type(cocoaTimestamp) == float:
                cocoaTimestamp = int(cocoaTimestamp)
    
            if nanoSec:
                cocoaTimestamp = int(float(cocoaTimestamp)/NANOSECONDS_DELIMITER)
   
            cocoaDateTimeObj = datetime.fromtimestamp(timestamp=cocoaTimestamp,tz=UTC()) + delta

            return TimeConverter.DatetimeToFILETIME(cocoaDateTimeObj)
    
   
    @staticmethod
    def GetTimeInISOFormat(dt) -> AnyStr:
        return dt.isoformat()
    
    @staticmethod
    def GetTimeInSoftwareFormat(dt,microseconds=False) -> AnyStr:
        if not microseconds:
            return '{y}.{m}.{d} {HH}:{MM}:{SS}'.format(d = dt.day if dt.day > 9 else '0'+str(dt.day),
                                                       m = dt.month if dt.month > 9 else '0'+str(dt.month),
                                                       y = dt.year,
                                                       HH = dt.hour if dt.hour > 9 else '0'+str(dt.hour),
                                                       MM = dt.minute if dt.minute > 9 else '0'+str(dt.minute),
                                                       SS = dt.second if dt.second > 9 else '0'+str(dt.second))
        else:
            return '{y}.{m}.{d} {HH}:{MM}:{SS}.{mS}'.format(d = dt.day if dt.day > 9 else '0'+str(dt.day),
                                                            m = dt.month if dt.month > 9 else '0'+str(dt.month),
                                                            y = dt.year,
                                                            HH = dt.hour if dt.hour > 9 else '0'+str(dt.hour),
                                                            MM = dt.minute if dt.minute > 9 else '0'+str(dt.minute),
                                                            SS = dt.second if dt.second > 9 else '0'+str(dt.second),
                                                            mS = dt.microsecond)   

#----------------------------------------------------------------
#----------------------------------------------------------------
#----------------КЛАСС ДЛЯ РАБОТЫ С ФАЙЛАМИ----------------------
#----------------------------------------------------------------

class FileContentReader():
    @staticmethod
    def IsExists(fullPath:str) -> bool:
        try:
            return os.path.exists(fullPath)
        except FileNotFoundError:
            return False
    
    @staticmethod
    def ListDir(folderFullPath:str) -> List:
        try:
            return os.listdir(folderFullPath)
        except FileNotFoundError:
            return []
    
    @staticmethod
    def GetSQLiteDBFileContent(folderPath:str,fileName:str='',includeTimestamps:bool=True) -> Tuple:
        result:tuple = None
        dbFilePath:str = None
        shmFilePath:str = None
        walFilePath:str = None
        dbContent:bytes = None
        shmContent:bytes = None
        walContent:bytes = None
        createTimeStampUTC:int = None
        modifyTimeStampUTC:int = None
        accessTimeStampUTC:int = None
               
        # Сформировать пути до файлов
        if fileName != '':
            dbFilePath = os.path.join(folderPath,fileName)
            shmFileName = f'{fileName}-shm'
            walFileName = f'{fileName}-wal'
            shmFilePath = os.path.join(folderPath,shmFileName) 
            walFilePath = os.path.join(folderPath,walFileName)
        else:
            dbFilePath = folderPath              
            shmFilePath = f'{folderPath}-shm'
            walFilePath = f'{folderPath}-wal'
            
        if includeTimestamps:
            try:
                # Получить временные отметки файла
                unixCTime = os.stat(dbFilePath).st_ctime
                unixMTime = os.stat(dbFilePath).st_mtime
                unixATime = os.stat(dbFilePath).st_atime
                createTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixCTime))
                modifyTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixMTime))
                accessTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixATime))
            except FileNotFoundError:
                pass
            
        with open(dbFilePath,'rb') as dbf:
            try:
                dbContent = dbf.read()
            except FileNotFoundError:
                pass
        
        with open(shmFilePath,'rb') as shmf:
            try:
                shmContent = shmf.read()
            except FileNotFoundError:
                pass
        
        with open(walFilePath,'rb') as walf:
            try:
                walContent = walf.read()
            except FileNotFoundError:
                pass

   
        return ({'CREATE':createTimeStampUTC,
                   'MODIFY':modifyTimeStampUTC,
                   'ACCESS':accessTimeStampUTC},
                   dbFilePath,
                   dbContent,
                   shmContent,
                   walContent)
        
    @staticmethod
    def GetTextFileContent(folderPath:str,fileName:str='',encoding:str='utf-8',includeTimestamps:bool=True) -> Tuple:
        result:tuple = None 
        content:bytes = None
        createTimeStampUTC:int = None
        modifyTimeStampUTC:int = None
        accessTimeStampUTC:int = None
        records:dict = {}
        
        # Сформировать пути до файлов
        if fileName != '':
            filePath = os.path.join(folderPath,fileName)
        else:
            filePath = folderPath
        
        
        if includeTimestamps:
            try:
                # Получить временные отметки файла
                unixCTime = os.stat(filePath).st_ctime
                unixMTime = os.stat(filePath).st_mtime
                unixATime = os.stat(filePath).st_atime
                createTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixCTime))
                modifyTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixMTime))
                accessTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixATime))
            except FileNotFoundError:
                pass
            
        with open(filePath,'rb') as f:
            try:
                content = f.read()
            except FileNotFoundError:
                pass
        
        if content is not None:
            # Буферизировать массив байт
            bufferedWrapper = io.TextIOWrapper(
                                    buffer = io.BytesIO(content),
                                    encoding = encoding,
                                    errors = 'ignore',
                                    line_buffering=True)
            
            # !!!! Костыль через словарь сделан в целях ускорения
            # !!!! Простое переключение элементов списка
            # !!!! работает в 3 раза дольше чем переключение ключа словаря
            buffLen = len(bufferedWrapper.readlines())
            bufferedWrapper.seek(0)
            for i in range(0,buffLen):
                readStr = bufferedWrapper.readline()
                if readStr != '':
                    records[i] = readStr
                if i >= buffLen:
                    break
                 
        return ({'CREATE':createTimeStampUTC,
                   'MODIFY':modifyTimeStampUTC,
                   'ACCESS':accessTimeStampUTC},
                   filePath,
                   records)
    
    @staticmethod
    def GetBinaryFileContent(folderPath:str,fileName:str='',includeTimestamps:bool=True) -> Tuple:
        result:tuple = None 
        content:bytes = None
        createTimeStampUTC:int = None
        modifyTimeStampUTC:int = None
        accessTimeStampUTC:int = None
        
        # Сформировать пути до файлов
        if fileName != '':
            filePath = os.path.join(folderPath,fileName)
        else:
            filePath = folderPath
        
        
        if includeTimestamps:
            try:
                # Получить временные отметки файла
                unixCTime = os.stat(filePath).st_ctime
                unixMTime = os.stat(filePath).st_mtime
                unixATime = os.stat(filePath).st_atime
                createTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixCTime))
                modifyTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixMTime))
                accessTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixATime))
            except FileNotFoundError:
                pass
            
        with open(filePath,'rb') as f:
            try:
                content = f.read()
            except FileNotFoundError:
                pass
                 
        return ({'CREATE':createTimeStampUTC,
                   'MODIFY':modifyTimeStampUTC,
                   'ACCESS':accessTimeStampUTC},
                   filePath,
                   content)
                   
#----------------------------------------------------------------
#----------------------------------------------------------------
#----------------КЛАСС ДЛЯ РАБОТЫ С SQLITE-----------------------
#----------------------------------------------------------------
#----------------------------------------------------------------
class SQLiteRAMProcessing(IntEnum):
    allowRAM = 0,
    noRAM = 1
    
#----------------------------------------------------------------
class _AbstractDatabaseClass():
    __metaclass__ = ABCMeta
    def __init__(self,dbPath,log):
        self._log:Any = log
        self._connection:sqlite3.Connection = None
        self._cursor:sqlite3.Cursor = None
        self._dbPath:str = dbPath
        self._cwd:str = os.getcwd()
        
    @abstractmethod
    def __SetConnection(self) -> NoReturn:
        pass
    
    @abstractmethod
    def _SetCursor(self) -> NoReturn:
        pass
    
    @abstractmethod
    def ExecCommit(self,query:str,params:Any='') -> NoReturn:
        pass
    
    @abstractmethod
    def Exec(self,query:str,params:Any='') -> NoReturn:
        pass
    
    @abstractmethod    
    def Fetch(self,query:str,params:Any='') -> List:
        pass
    
    @abstractmethod
    def Commit(self) -> NoReturn:
        pass
    
    @abstractmethod    
    def CloseConnection(self) -> NoReturn:
        pass
    
    def GetDatabasePath(self) -> AnyStr:
        return self._dbPath

#----------------------------------------------------------------
class _AbstractLocalDatabaseClass(_AbstractDatabaseClass):
    __metaclass__ = ABCMeta
    def __init__(self,dbPath,log):
        super().__init__(dbPath,log)
     
    @abstractmethod
    def __SetConnection(self) -> NoReturn:
        pass
    
    @abstractmethod
    def _SetCursor(self) -> NoReturn:
        pass
    
    @abstractmethod
    def _SwitchOnForeignKeys(self) -> NoReturn:
       pass
   
    @abstractmethod
    def _SwitchOnCaseInsensitiveLike(self) -> NoReturn:
        pass
    
    def _RegExp(self, expr, item) -> Optional[re.Match]:
        reg = re.compile(expr,flags=re.I)
        return reg.search(str(item)) is not None
    
    def _Lower(self,value) -> AnyStr:
        return str(value).lower()
        
    def _AddLowerFunction(self) -> NoReturn:
        if self._connection is not None:
            # Переопределение функции преобразования к нижнему регистру
            self._connection.create_function("LOWER", 1, self._Lower)
         
    def _AddRegExpSearch(self) -> NoReturn:
        if self._connection is not None:
            # Прикрутить функцию поиска по регулярному выражению
            self._connection.create_function("REGEXP", 2, self._RegExp)
    
    def ExecCommit(self,query:str,params:Any='') -> NoReturn:
        try:
            self._cursor.execute(query, params)
            self._connection.commit()
        except sqlite3.OperationalError as e:
            message = f'Ошибка запроса к БД: {e}'
            self._log.Warn('_AbstractLocalDatabaseClass',message)
        
    def Fetch(self,query:str,params:Any='') -> List:
        try:
            self._cursor.execute(query, params)
            self._connection.commit()    
            return self._cursor.fetchall()
        except (sqlite3.OperationalError,sqlite3.ProgrammingError) as e:
            message = f'Ошибка запроса к БД: {e}'
            self._log.Warn('_AbstractLocalDatabaseClass',message)
            return []

    def Exec(self,query:str,params:Any='') -> NoReturn:
        self._cursor.execute(query, params)
        
    def Commit(self) -> NoReturn:
        self._connection.commit()
        
    @abstractmethod    
    def CloseConnection(self) -> NoReturn:
        pass
    
    def _CheckCreateFolders(self) -> NoReturn:
        # Функция для создания нужных подкаталогов, чтобы можно было создать БД
         #db_path = self._dbPath.replace('\\', '/')
        #itemsList = db_path.split('/')
        #db_path = self._dbPath.replace('\\', '/')
        #itemsList = db_path.split('/')

        if not self._dbPath:
            return
        
        # Для Linux - просто создаем папку для файла БД
        db_dir = os.path.dirname(self._dbPath)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        #itemsList = self._dbPath.rsplit('\\',2)
        #cases = itemsList[0]
        #case = itemsList[1]

        # Проверяем последовательно каталоги
        #if cases.find(':\\') == -1:
        #    cwdCases = os.path.join(self._cwd,cases)
        #    if not os.path.exists(cwdCases):                    
        #        os.mkdir(cwdCases)
        #    cwdCasesCase = os.path.join(cwdCases,case)
        #    if not os.path.exists(cwdCasesCase):                    
        #        os.mkdir(cwdCasesCase)
            
        #else:
        #    cwdCases = cases
        #    if not os.path.exists(cwdCases):                    
        #        os.mkdir(cwdCases)
        #    cwdCasesCase = os.path.join(cwdCases,case)
        #    if not os.path.exists(cwdCasesCase):                    
        #        os.mkdir(cwdCasesCase)

#----------------------------------------------------------------
# Интерфейс для работы с имеющимися SQLite
class SQLiteDatabaseInterfaceReader(_AbstractLocalDatabaseClass):
    def __init__(self,dbPath,log): 
        super().__init__(dbPath,log)
               
        # Установить соединение из настроек и курсор        
        self._connection = self.__SetConnection()
        
        if self._connection is not None:
            self._cursor = self._SetCursor()
            self._SwitchOnForeignKeys()
            self._AddRegExpSearch()
            self._AddLowerFunction()
            self.__SwitchOnReadOnlyMode()
            self._SwitchOnCaseInsensitiveLike()
     

    def IsConnected(self) -> bool:
        if self._connection is not None:
            return True
        else: 
            return False
    
    def _SetCursor(self) -> Optional[sqlite3.Cursor]:
        return self._connection.cursor()
    
    def __SetConnection(self) -> Optional[sqlite3.Connection]:
        try:
            if self._dbPath is not None:
                return sqlite3.connect(self._dbPath)
            else:
                # Ошибка задания параметров подключения к БД
                message = 'Имя файла БД задано неверно!'
                self._log.Error('DatabaseInterface.SQLiteDatabaseInterfaceReader.__SetConnection',message)
                return None
        except sqlite3.OperationalError:
                # Ошибка задания параметров подключения к БД
                message = 'Ошибка создания подключения к БД SQLite!'
                self._log.Error('DatabaseInterface.SQLiteDatabaseInterfaceReader.__SetConnection',message)
                return None
   
    def _SwitchOnForeignKeys(self) -> NoReturn:
        self.ExecCommit('PRAGMA foreign_keys=on;','')
        
    def __SwitchOnReadOnlyMode(self) -> NoReturn:
        self.ExecCommit('PRAGMA query_only=ON;','')
        
    def _SwitchOnCaseInsensitiveLike(self) -> NoReturn:
        self.ExecCommit('PRAGMA case_sensitive_like=off;','')
        
    def _SwitchOnJournalModeMemory(self) -> NoReturn:
        self.ExecCommit('PRAGMA journal_mode=MEMORY;','')    
                
    def GetInfo(self) -> Dict:
        info = {}
        query = str('SELECT Key,Value FROM Info;')
        result = self.Fetch(query)
        for item in result:
            info.update({item[0]:item[1]})        
        return info
    
    def GetHeaders(self) -> List:
        query = 'SELECT Name,Label,Width FROM Headers;'
        return self.Fetch(query)
               
    def GetAmountOfRecords(self) -> int:
        return self.Fetch('SELECT count(ID) FROM Data;')[0][0]
    
    def GetRecordIdCache(self) -> List:
        return self.Fetch('SELECT ID FROM Data ORDER BY ID ASC;') 
        
    def IsRecords(self) -> bool:
        query = 'SELECT count(*) FROM Data;'
        try:
            rows = self.Fetch(query,'')[0][0]
            # Если есть данные
            if rows > 0:
                return True
            else:
                return False
        except IndexError:
            return False
        
    def CloseConnection(self) -> NoReturn:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

#----------------------------------------------------------------
# Интерфейс для работы с новыми SQLite
class SQLiteDatabaseInterface(SQLiteDatabaseInterfaceReader):
    def __init__(self,dbPath:str,log:Any,moduleName:str,moduleRAMProcessing:bool): 
        super().__init__(dbPath,log)
        self.__moduleName:str = moduleName
        
        self._RAMProcessing:bool = moduleRAMProcessing
        # Установить соединение из настроек и курсор        
        self._connection = self.__SetConnection()
        
        if self._connection is not None:
            self._cursor = self._SetCursor()
            self._SwitchOnForeignKeys()
            self._AddRegExpSearch()
            self._AddLowerFunction()
            self.__SwitchOnAutoVacuum()
            self._SwitchOnCaseInsensitiveLike()

        
    def RemoveTempTables(self,tempTables:list) -> NoReturn:
        for table in tempTables:
            self.ExecCommit(f'DROP TABLE {table};')
    
    def IsRAMAllocated(self):
        return self._RAMProcessing
    
    def __SetConnection(self) -> Optional[sqlite3.Connection]:
        # Установить соединение в зависимости от потребностей модуля в RAM
        if self._RAMProcessing:
            return sqlite3.connect(':memory:')
      
        else: 
            if self._dbPath is not None:
                try:
                    conn = sqlite3.connect(self._dbPath)
                except sqlite3.OperationalError: # ошибка подключения, проверить наличие каталога
                    try:
                        self._CheckCreateFolders()
                        conn = sqlite3.connect(database=self._dbPath,
                                                   timeout=3.0)  
                    except sqlite3.OperationalError: # нет БД      
                        conn = None
                    return conn
            else:
                # Ошибка задания параметров подключения к файлу БД
                message = 'Ошибка создания подключения к БД SQLite: Имя файла для сохранения БД задано неверно!'
                self._log.Error('DatabaseInterface.SQLiteDatabaseInterface.__SetConnection',message)
                return None

    def __SwitchOnAutoVacuum(self) -> NoReturn:
        self.ExecCommit('PRAGMA auto_vacuum=1;','')
               
    def IsDatabaseDumpAllowed(self) -> bool:
        # Заглушка 
        return True  
      
    def SaveSQLiteDatabaseFromRamToFile(self) -> NoReturn:
        if not self._RAMProcessing:
            # Если и так не в памяти обрабатывает данные
            return

        if self._connection is not None:
            self._CheckCreateFolders()
            fileDBConnection = sqlite3.connect(self._dbPath)
            self._connection.backup(fileDBConnection)
            fileDBConnection.close()
 
