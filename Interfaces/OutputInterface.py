# -*- coding: utf-8 -*-
"""
Модуль вывода информации

"""

from abc import ABCMeta, abstractmethod
import itertools,sqlite3
from typing import Any,AnyStr,List,Tuple,Dict,NoReturn,Optional

#------------------------------------------------------------------------------
class _AbstractOutputWriter():
    __metaclass__ = ABCMeta
    def __init__(self,paths:dict):
        
        self._caseName:str = paths.get('CASENAME','')
        self._caseFolder:str = paths.get('CASEFOLDER','')
        self._moduleName:str = paths.get('MODULENAME','')
        
        self._fieldsDescription:dict = None
        self._recordFields:dict = None
        self._fieldsStr:str = ''
        self._fields:tuple = None
        
        self._info:dict = None
        
    def SetFields(self,fieldsDescription:dict,recordFields:dict) -> NoReturn:
        self._fieldsDescription = fieldsDescription
        self._recordFields = recordFields
        self._fieldsStr = ','.join(tuple(recordFields.keys()))
        self._fields = tuple(recordFields.keys())
        
    def SetInfo(self,info:dict) -> NoReturn:
        self._info = info
     
    @abstractmethod
    def WriteMeta(self) -> NoReturn:
        pass
        
#------------------------------------------------------------------------------
class SQLiteDBOutputWriter(_AbstractOutputWriter):
    def __init__(self,paths:dict):  
        super().__init__(paths)
        self._dbConnection:sqlite3.Connection = None
        self._dbName:str = paths.get('DBNAME','')
        self._tempTables:list = []
        
    def SetDBConnection(self,conn:sqlite3.Connection) -> NoReturn:
        self._dbConnection = conn
    
    def GetDBName(self) -> AnyStr:
        return self._dbName
    
    def GetDBConnection(self) -> Optional[sqlite3.Connection]:
        return self._dbConnection
    
    def AddTempTable(self,tableName:str) -> NoReturn:
        self._tempTables.append(tableName)
    
    def RemoveTempTables(self) -> NoReturn:
        for table in self._tempTables:
            query = str('DROP TABLE ' + str(table) + ';')
            self._dbConnection.ExecCommit(query)
        self._tempTables.clear()
        
    def CommitRecords(self) -> NoReturn:
        self._dbConnection.Commit()

    def CreateDatabaseTables(self) -> NoReturn:
        # Cоздать таблицы в БД
        if self._dbConnection is None:
            return

        # Таблица данных
        query = 'CREATE TABLE IF NOT EXISTS Data (ID INTEGER PRIMARY KEY AUTOINCREMENT, '
        for k,v in self._recordFields.items():
            query = f'{query}{k} {v},'
        
        query = query.rstrip(',')
        query = f'{query});'

        self._dbConnection.ExecCommit(query,'') 
        
        # Таблица заголовков полей Headers
        self._dbConnection.ExecCommit(
                    'CREATE TABLE IF NOT EXISTS Headers ('
                    'ID INTEGER PRIMARY KEY AUTOINCREMENT, '
                    'Name TEXT NOT NULL, '
                    'Label TEXT, '
                    'Width INTEGER, '
                    'DataType TEXT, '
                    'Comment TEXT)','')
        
        # Таблица с информацией о массиве данных Info
        self._dbConnection.ExecCommit(
                    'CREATE TABLE IF NOT EXISTS Info ('
                    'ID INTEGER PRIMARY KEY AUTOINCREMENT, '
                    'Key TEXT NOT NULL, '
                    'Value TEXT)','')
        

    async def CreateDatabaseIndexes(self,moduleName:str) -> NoReturn:   #!!!! Д.б. async coroutine
        if self._dbConnection is None:
            return
        
        # Создать индексы
        lenKeys = len(tuple(self._recordFields.keys()))
        if self._dbConnection.IsRecords():
            for i,key in enumerate(self._recordFields.keys()):
                self._dbConnection.ExecCommit(f'CREATE INDEX idx_{key.lower()} ON Data({key});')

            
    def UpdateDataSource(self,prevDS:str,checkResult:Any,autoCommit:bool=False) -> NoReturn: 
        if self._dbConnection is None:
            return

        if checkResult is not None:
            idx = checkResult[0]
            source = checkResult[1]
            newSource = ',\n'.join(set(list(itertools.chain.from_iterable([prevDS.split(',\n'),source.split(',\n')])))) # убрать дубли

            updQuery = f'UPDATE Data Set DataSource = "{newSource}" WHERE ID = {idx};'
    
            if autoCommit is False:
                self._dbConnection.Exec(updQuery)
            else:
                self._dbConnection.ExecCommit(updQuery)
        
                
    def WriteRecord(self,recordInfo:tuple,autoCommit:bool=False) -> NoReturn: 
        if self._dbConnection is None:
            return

        query = str('INSERT INTO Data('
                    f'{self._fieldsStr}'
                    ') VALUES (' +
                    str('?,'*len(self._recordFields.keys())).rstrip(',') + 
                    ');')

        if autoCommit is False:
            self._dbConnection.Exec(query,recordInfo)
        else:
            self._dbConnection.ExecCommit(query,recordInfo)
       
    def WriteMeta(self) -> NoReturn:
        if self._dbConnection is None:
            return
        
        # Заполнить таблицы Headers и Info
        for key in self._fieldsDescription.keys():
            headersQuery = str('INSERT INTO Headers('
                           'Name,Label,Width,DataType,Comment) '
                           f'VALUES("{str(key)}",'
                           f'"{self._fieldsDescription[key][0]}",'
                           f'{self._fieldsDescription[key][1]},'
                           f'"{self._fieldsDescription[key][2]}",'
                           f'"{self._fieldsDescription[key][3]}");')

            self._dbConnection.ExecCommit(headersQuery)

        for key in self._info.keys():
            infoQuery = str('INSERT INTO Info(Key,Value) VALUES('
                            f'"{str(key)}",'
                            f'"{str(self._info.get(key))}");')

            self._dbConnection.ExecCommit(infoQuery)
           
            
    async def CloseOutput(self) -> NoReturn:   #!!!! Д.б. async coroutine
        # Закрыть соединение с БД с учетом, что она могла быть в памяти
        if self._dbConnection.IsConnected():
            self.CommitRecords()
            if self._dbConnection.IsDatabaseDumpAllowed():  
                if self._dbConnection.IsRecords():
                    if self._dbConnection.IsRAMAllocated():
                        self._dbConnection.SaveSQLiteDatabaseFromRamToFile()
                    self._dbConnection.CloseConnection()
                else:
                    self._dbConnection.CloseConnection()
