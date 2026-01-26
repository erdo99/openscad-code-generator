@echo off
echo ========================================
echo requests Paketi Yukleniyor...
echo ========================================
echo.

REM Sanal ortamı aktif et
call venv\Scripts\activate.bat

echo pip upgrade ediliyor...
python -m pip install --upgrade pip

echo.
echo requests paketi yukleniyor...
python -m pip install requests

echo.
echo Kontrol ediliyor...
python -c "import requests; print('✅ requests yuklendi:', requests.__version__)"

echo.
echo ========================================
echo Tamamlandi!
echo ========================================
pause
