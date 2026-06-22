@echo off
chcp 65001 >nul
title AHK Terminal
cd /d "%~dp0backend"
echo.
echo   ============================================
echo      AHK Terminal baslatiliyor...
echo   ============================================
echo.
echo   Bu bilgisayar:        http://localhost:8077
echo   Ayni WiFi (telefon):  http://192.168.1.102:8077
echo                         (IP degisirse: cmd ^> ipconfig ^> IPv4)
echo.
echo   Kapatmak icin bu pencereyi kapatin (Ctrl+C).
echo.
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8077
pause
