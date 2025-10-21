@echo off
chcp 65001 >nul
echo.
echo Проверка статуса сервера...
echo.

REM Проверяем файл статуса
if exist .server_status (
    echo [✓] Файл статуса найден:
    type .server_status
    echo.
) else (
    echo [✗] Файл статуса не найден
)

REM Проверяем порт 8000
echo Проверка порта 8000...
netstat -ano | findstr ":8000" | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo [✓] Порт 8000 слушается
) else (
    echo [✗] Порт 8000 НЕ слушается
    echo.
    echo Сервер НЕ запущен. Запустите: start_server.bat
)

echo.
pause


