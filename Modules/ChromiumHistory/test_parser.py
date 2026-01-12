# -*- coding: utf-8 -*-
"""
Unit tests for Chromium history parser module
"""
import unittest
import tempfile
import os
import sqlite3
from unittest.mock import Mock, patch, MagicMock
import asyncio

# Импортируем классы из вашего модуля
from Parser import (
    TimeConverter,
    DatabaseManager,
    HistoryParser,
    BrowserFinder,
    OutputConfigurator,
    MainParser
)


class TestTimeConverter(unittest.TestCase):
    """Тесты для класса TimeConverter"""
    
    def test_convert_chrome_time_valid(self):
        """Тест конвертации валидного времени Chromium"""
        # Пример времени Chromium (примерно 2023 год)
        chrome_timestamp = 13318267369295313
        result = TimeConverter.convert_chrome_time(chrome_timestamp)
        
        # Проверяем, что результат не пустой и имеет правильный формат
        self.assertNotEqual(result, '')
        self.assertRegex(result, r'\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}')
    
    def test_convert_chrome_time_zero(self):
        """Тест конвертации нулевого времени"""
        result = TimeConverter.convert_chrome_time(0)
        self.assertEqual(result, '')
    
    def test_convert_chrome_time_none(self):
        """Тест конвертации None времени"""
        result = TimeConverter.convert_chrome_time(None)
        self.assertEqual(result, '')
    
    def test_convert_chrome_time_invalid(self):
        """Тест конвертации некорректного времени"""
        result = TimeConverter.convert_chrome_time(-1)
        self.assertEqual(result, '')


class TestDatabaseManager(unittest.TestCase):
    """Тесты для класса DatabaseManager"""
    
    def setUp(self):
        """Создание временного файла БД для тестов"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, 'test_history.db')
        
        # Создаем тестовую БД
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE urls (
                id INTEGER PRIMARY KEY,
                url TEXT,
                title TEXT,
                visit_count INTEGER,
                typed_count INTEGER,
                last_visit_time INTEGER
            )
        ''')
        
        # Добавляем тестовые данные
        cursor.execute('''
            INSERT INTO urls (url, title, visit_count, typed_count, last_visit_time)
            VALUES (?, ?, ?, ?, ?)
        ''', ('https://example.com', 'Example', 5, 2, 13318267369295313))
        
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Очистка временных файлов"""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_context_manager(self):
        """Тест работы контекстного менеджера"""
        with DatabaseManager(self.temp_dir, self.test_db_path) as db:
            self.assertIsNotNone(db.temp_path)
            self.assertIsNotNone(db.conn)
            
            # Проверяем, что можем выполнить запрос
            cursor = db.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM urls")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)
        
        # Проверяем, что временный файл удален
        self.assertFalse(os.path.exists(db.temp_path))
    
    def test_get_cursor_without_connection(self):
        """Тест получения курсора без подключения"""
        db = DatabaseManager(self.temp_dir, self.test_db_path)
        with self.assertRaises(sqlite3.Error):
            db.get_cursor()


class TestHistoryParser(unittest.TestCase):
    """Тесты для класса HistoryParser"""
    
    def setUp(self):
        """Настройка тестового окружения"""
        self.logger = Mock()
        self.logger.Warn = Mock()
        self.logger.Error = Mock()
        
        self.parser = HistoryParser(logger=self.logger, username='test_user')
    
    @patch('Parser.DatabaseManager')
    def test_parse_history_success(self, mock_db_manager):
        """Тест успешного парсинга истории"""
        # Мокаем DatabaseManager и курсор
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('urls',)
        mock_cursor.fetchall.return_value = [
            ('https://example.com', 'Example', 5, 2, 13318267369295313)
        ]
        
        mock_db = Mock()
        mock_db.get_cursor.return_value = mock_cursor
        mock_db_manager.return_value.__enter__.return_value = mock_db
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_path = f.name
        
        try:
            result = self.parser.parse_history(test_path, 'TestBrowser')
            
            # Проверяем результаты
            self.assertEqual(len(result), 1)
            record = result[0]
            self.assertEqual(record[0], 'test_user')  # Username
            self.assertEqual(record[1], 'TestBrowser')  # Browser
            self.assertEqual(record[2], 'https://example.com')  # URL
            self.assertEqual(record[4], 5)  # VisitCount
        
        finally:
            os.remove(test_path)
    
    @patch('Parser.DatabaseManager')
    def test_parse_history_no_table(self, mock_db_manager):
        """Тест парсинга при отсутствии таблицы urls"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # Таблица не найдена
        
        mock_db = Mock()
        mock_db.get_cursor.return_value = mock_cursor
        mock_db_manager.return_value.__enter__.return_value = mock_db
        
        with tempfile.NamedTemporaryFile(suffix='.db') as f:
            result = self.parser.parse_history(f.name, 'TestBrowser')
            self.assertEqual(len(result), 0)
    
    def test_parse_history_file_not_exists(self):
        """Тест парсинга при отсутствии файла"""
        result = self.parser.parse_history('/non/existent/path', 'TestBrowser')
        self.assertEqual(len(result), 0)
    
    def test_process_rows(self):
        """Тест обработки строк результата"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ('https://example.com', 'Example', 5, 2, 13318267369295313),
            ('https://google.com', None, None, None, None)  # Проверка обработки None
        ]
        
        result = self.parser._process_rows(mock_cursor, 'TestBrowser')
        
        self.assertEqual(len(result), 2)
        
        # Проверяем первую запись
        record1 = result[0]
        self.assertEqual(record1[0], 'test_user')
        self.assertEqual(record1[1], 'TestBrowser')
        self.assertEqual(record1[2], 'https://example.com')
        self.assertEqual(record1[3], 'Example')
        self.assertEqual(record1[4], 5)
        self.assertEqual(record1[5], 2)
        
        # Проверяем вторую запись с None значениями
        record2 = result[1]
        self.assertEqual(record2[3], '')  # Title должен быть пустой строкой
        self.assertEqual(record2[4], 0)   # VisitCount должен быть 0


class TestBrowserFinder(unittest.TestCase):
    """Тесты для класса BrowserFinder"""
    
    @patch('Parser.os.path.exists')
    def test_find_browser_history_paths(self, mock_exists):
        """Тест поиска путей к истории браузеров"""
        # Настраиваем мок, чтобы один браузер был найден
        def side_effect(path):
            return 'google-chrome' in path
        
        mock_exists.side_effect = side_effect
        
        found_browsers = BrowserFinder.find_browser_history_paths()
        
        # Проверяем, что найден только google-chrome
        self.assertEqual(len(found_browsers), 1)
        self.assertIn('Google Chrome', found_browsers[0][2])
    
    @patch('Parser.os.path.exists')
    def test_find_browser_history_paths_none(self, mock_exists):
        """Тест поиска, когда браузеры не найдены"""
        mock_exists.return_value = False
        
        found_browsers = BrowserFinder.find_browser_history_paths()
        self.assertEqual(len(found_browsers), 0)


class TestOutputConfigurator(unittest.TestCase):
    """Тесты для класса OutputConfigurator"""
    
    def setUp(self):
        self.config = OutputConfigurator()
    
    def test_get_record_fields(self):
        """Тест получения структуры полей"""
        fields = self.config.get_record_fields()
        
        self.assertIsInstance(fields, dict)
        self.assertIn('UserName', fields)
        self.assertIn('Browser', fields)
        self.assertIn('URL', fields)
        self.assertEqual(fields['VisitCount'], 'INTEGER')
    
    def test_get_fields_description(self):
        """Тест получения описания полей"""
        fields_desc = self.config.get_fields_description()
        
        self.assertIsInstance(fields_desc, dict)
        self.assertIn('UserName', fields_desc)
        self.assertIn('URL', fields_desc)
        
        # Проверяем структуру описания
        desc = fields_desc['UserName']
        self.assertEqual(desc[0], 'Имя пользователя')
        self.assertEqual(desc[1], 120)
        self.assertEqual(desc[2], 'string')
    
    def test_get_help_text(self):
        """Тест получения текста помощи"""
        help_text = self.config.get_help_text()
        
        self.assertIsInstance(help_text, str)
        self.assertIn('Chromium History Parser', help_text)
        self.assertIn('URL посещенных страниц', help_text)


class TestMainParser(unittest.TestCase):
    """Тесты для класса MainParser"""
    
    def setUp(self):
        """Настройка тестовых параметров"""
        self.parameters = {
            'STORAGE': Mock(),
            'OUTPUTWRITER': Mock(),
            'DBCONNECTION': Mock(),
            'UIREDRAW': Mock(),
            'LOG': Mock(),
            'USERNAME': 'test_user',
            'MODULENAME': 'ChromiumHistory',
            'CASENAME': 'test_case_2024'
        }
        
        # Настраиваем моки
        self.parameters['DBCONNECTION'].IsConnected.return_value = True
        self.parameters['OUTPUTWRITER'].GetDBName.return_value = 'test_db.db'
        self.parameters['OUTPUTWRITER'].SetInfo = Mock()
        self.parameters['OUTPUTWRITER'].WriteMeta = Mock()
        self.parameters['OUTPUTWRITER'].CloseOutput = Mock()
        self.parameters['OUTPUTWRITER'].SetFields = Mock()
        self.parameters['OUTPUTWRITER'].CreateDatabaseTables = Mock()
        self.parameters['OUTPUTWRITER'].WriteRecord = Mock()
        self.parameters['OUTPUTWRITER'].RemoveTempTables = Mock()
        self.parameters['OUTPUTWRITER'].CreateDatabaseIndexes = Mock()
        
        # Делаем асинхронный мок
        async def async_mock(*args, **kwargs):
            return None
        self.parameters['UIREDRAW'] = async_mock
    
    @patch('Parser.BrowserFinder')
    @patch('Parser.HistoryParser')
    def test_start_success(self, mock_history_parser, mock_browser_finder):
        """Тест успешного запуска основного парсера"""
        # Настраиваем моки
        mock_browser_finder.return_value.find_browser_history_paths.return_value = [
            ('/path/to/history', 'chrome', 'Google Chrome')
        ]
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_history.return_value = [
            ('user', 'Chrome', 'url', 'title', 1, 1, 123, '2024.01.01 10:00:00', 'source')
        ]
        mock_history_parser.return_value = mock_parser_instance
        
        # Создаем и запускаем парсер
        main_parser = MainParser(self.parameters)
        
        # Запускаем асинхронный метод
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(main_parser.Start())
        
        # Проверяем вызовы
        self.parameters['OUTPUTWRITER'].SetFields.assert_called_once()
        self.parameters['OUTPUTWRITER'].CreateDatabaseTables.assert_called_once()
        self.parameters['OUTPUTWRITER'].WriteRecord.assert_called()
        self.parameters['OUTPUTWRITER'].SetInfo.assert_called_once()
        
        # Проверяем результат
        self.assertIn('ChromiumHistory', result)
        self.assertEqual(result['ChromiumHistory'], 'test_db.db')
    
    def test_start_no_db_connection(self):
        """Тест запуска без подключения к БД"""
        self.parameters['DBCONNECTION'].IsConnected.return_value = False
        
        main_parser = MainParser(self.parameters)
        
        # Запускаем асинхронный метод
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(main_parser.Start())
        
        self.assertEqual(result, {})
    
    @patch('Parser.BrowserFinder')
    def test_start_no_browsers_found(self, mock_browser_finder):
        """Тест запуска, когда браузеры не найдены"""
        mock_browser_finder.return_value.find_browser_history_paths.return_value = []
        
        main_parser = MainParser(self.parameters)
        
        # Запускаем асинхронный метод
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(main_parser.Start())
        
        # Проверяем, что метаданные все равно записываются
        self.parameters['OUTPUTWRITER'].SetInfo.assert_called_once()
        self.assertIn('ChromiumHistory', result)


class IntegrationTests(unittest.TestCase):
    """Интеграционные тесты"""
    
    def test_end_to_end_flow(self):
        """Сквозной тест всего процесса"""
        # Создаем временную БД с тестовыми данными
        with tempfile.TemporaryDirectory() as temp_dir:
            test_db_path = os.path.join(temp_dir, 'History')
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            # Создаем таблицу urls
            cursor.execute('''
                CREATE TABLE urls (
                    id INTEGER PRIMARY KEY,
                    url TEXT,
                    title TEXT,
                    visit_count INTEGER,
                    typed_count INTEGER,
                    last_visit_time INTEGER
                )
            ''')
            
            # Добавляем тестовые данные
            cursor.execute('''
                INSERT INTO urls (url, title, visit_count, typed_count, last_visit_time)
                VALUES (?, ?, ?, ?, ?)
            ''', ('https://test.com', 'Test Page', 10, 5, 13318267369295313))
            
            conn.commit()
            conn.close()
            
            # Создаем парсер и парсим историю
            logger = Mock()
            logger.Warn = Mock()
            logger.Error = Mock()
            
            parser = HistoryParser(logger=logger, username='integration_user')
            results = parser.parse_history(test_db_path, 'IntegrationBrowser')
            
            # Проверяем результаты
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][0], 'integration_user')
            self.assertEqual(results[0][1], 'IntegrationBrowser')
            self.assertEqual(results[0][2], 'https://test.com')
            self.assertEqual(results[0][4], 10)  # VisitCount


if __name__ == '__main__':
    unittest.main(verbosity=2)