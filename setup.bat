@echo off
echo Sanal ortam olusturuluyor...
python -m venv venv

echo.
echo Sanal ortam aktif ediliyor...
call venv\Scripts\activate.bat

echo.
echo Paketler yukleniyor...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Kurulum tamamlandi!
echo.
echo Uygulamayi calistirmak icin:
echo   1. venv\Scripts\activate.bat
echo   2. python app.py
echo.
pause
