@echo off
cd /d "%~dp0"

REM Очищаем любые переменные окружения OPENAI_API_KEY
set OPENAI_API_KEY=

echo.
echo ======================================================================
echo BDS Scraper Server (Clean Start)
echo ======================================================================
echo Переменная OPENAI_API_KEY очищена
echo API ключ будет загружен из .env файла
echo Сервер запускается...
echo.
echo Откройте в браузере: http://localhost:8000
echo.
echo Для остановки нажмите Ctrl+C
echo ======================================================================
echo.

python -u server.py

pause

