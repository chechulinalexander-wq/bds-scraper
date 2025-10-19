Set-Location "c:\CURSOR\BDS - Scraper"

Write-Host ""
Write-Host "======================================================================"
Write-Host "BDS Scraper Server"
Write-Host "======================================================================"
Write-Host "Сервер запускается..."
Write-Host ""
Write-Host "Откройте в браузере: http://localhost:8000"
Write-Host ""
Write-Host "Для остановки нажмите Ctrl+C"
Write-Host "======================================================================"
Write-Host ""

python server.py

Read-Host "Нажмите Enter для выхода"

