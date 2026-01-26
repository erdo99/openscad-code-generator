@echo off
echo ========================================
echo Orijinal Backend API Baslatiliyor...
echo ========================================
echo.

REM Sanal ortamı aktif et
if not exist venv (
    echo HATA: Sanal ortam bulunamadi!
    echo Lutfen once setup.bat dosyasini calistirin.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Backend baslatiliyor (Port 5000)...
echo.
python backend_api.py

pause
