#!/usr/bin/env python3
"""
Final test runner
"""
import sys
import os
import subprocess

def run_with_unittest():
    """Запуск через unittest"""
    print("Running tests with unittest...")
    
    result = subprocess.run(
        [sys.executable, '-m', 'unittest', 'test_parser.TestParserReal.test_parser_initialization'],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Basic test passed!")
        
        # Запускаем все тесты
        print("\nRunning all tests...")
        result = subprocess.run(
            [sys.executable, '-m', 'unittest', 'test_parser', '-v'],
            capture_output=True,
            text=True
        )
    
    return result

def main():
    """Основная функция"""
    print("=" * 70)
    print("TEST RUNNER FOR Parser.py")
    print("=" * 70)
    
    # Проверяем файлы
    files = os.listdir('.')
    print(f"Files in directory: {files}")
    
    if 'Parser.py' not in files:
        print("❌ Parser.py not found!")
        return 1
    
    if 'test_parser.py' not in files:
        print("❌ test_parser.py not found!")
        return 1
    
    # Запускаем тесты
    result = run_with_unittest()
    
    print("\n" + "=" * 70)
    print("OUTPUT:")
    print(result.stdout)
    
    if result.stderr:
        print("\nERRORS:")
        print(result.stderr)
    
    print(f"\nReturn code: {result.returncode}")
    
    if result.returncode == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("💥 SOME TESTS FAILED")
    
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())