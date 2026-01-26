@echo off
echo ========================================
echo io_net Backend API Baslatiliyor...
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

echo Backend baslatiliyor (Port 5002)...
echo API Provider: io_net
echo.
python backend_api_ionet.py

pause
