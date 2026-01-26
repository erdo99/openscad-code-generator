@echo off
echo ========================================
echo io_net API Test Calistiriliyor...
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

REM requests paketinin yüklü olduğundan emin ol
pip install requests --quiet

echo.
echo Test baslatiliyor...
echo NOT: Backend'in calisiyor olmasi gerekiyor (start_backend_ionet.bat)
echo.
python test_ionet_api.py

echo.
pause
