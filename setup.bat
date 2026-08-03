@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Is Basvuru Otomasyonu - Kurulum
echo ============================================

if not exist ".venv" (
  echo [1/4] Python sanal ortam olusturuluyor...
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [2/4] Bagimliliklar yukleniyor...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [3/4] Playwright Chromium kuruluyor (yedek tarayici)...
python -m playwright install chromium

if not exist "config.json" (
  echo [4/4] Varsayilan config olusturuluyor...
  python -c "from browser import save_config, default_config; save_config(default_config())"
) else (
  echo [4/4] config.json zaten var.
)

echo.
echo ============================================
echo  Kurulum tamam.
echo  (1) JOBAGENT komutunu PATH'e eklemek icin:  kur.bat
echo      Sonra yeni terminalde:  JOBAGENT   (tam ekran arayuz)  |  JOBAGENT web
echo  (2) Web arayuzu dogrudan:  .venv\Scripts\python app.py  -^>  http://127.0.0.1:5000
echo ============================================
pause
