@echo off
echo ========================================
echo Unit Tests Calistiriliyor...
echo ========================================
echo.

REM Sanal ortamı aktif et
call venv\Scripts\activate.bat

REM Testleri çalıştır
python test_backend_improved.py

echo.
echo ========================================
echo Testler tamamlandi!
echo ========================================
pause
