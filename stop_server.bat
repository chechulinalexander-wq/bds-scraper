@echo off
chcp 65001 >nul
echo.
echo Остановка сервера...
echo.

REM Проверяем файл статуса
if exist .server_status (
    for /f "tokens=3 delims=|" %%a in (.server_status) do (
        echo Останавливаем процесс %%a...
        taskkill /F /PID %%a 2>nul
        if %errorlevel% equ 0 (
            echo [✓] Сервер остановлен
            del .server_status
        ) else (
            echo [✗] Не удалось остановить процесс
        )
    )
) else (
    echo Ищем процессы Python на порту 8000...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
        echo Останавливаем процесс %%a...
        taskkill /F /PID %%a 2>nul
        if %errorlevel% equ 0 (
            echo [✓] Процесс остановлен
        )
    )
)

echo.
pause


