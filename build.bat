@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  JOBAGENT.exe derleme (Python gerektirmez)
echo ============================================

if not exist ".venv\Scripts\python.exe" (
  echo Sanal ortam yok. Once setup.bat calistirin.
  pause
  exit /b 1
)

echo [1/2] PyInstaller kuruluyor...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check pyinstaller
if errorlevel 1 (
  echo PyInstaller kurulamadi.
  pause
  exit /b 1
)

echo [2/2] JOBAGENT.exe derleniyor (birkaç dakika surebilir)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --name JOBAGENT ^
  --collect-all playwright ^
  --hidden-import pypdf ^
  --hidden-import docx ^
  --hidden-import cli ^
  --hidden-import app ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  tui.py
if errorlevel 1 (
  echo Derleme hatasi.
  pause
  exit /b 1
)

echo.
echo ============================================
echo  Hazir: dist\JOBAGENT.exe
echo  Kullanicilara bu tek dosyayi verebilirsiniz.
echo  Not: Chrome veya Edge kurulu olmali; data ve
echo  config.json exe'nin yaninda olusur.
echo ============================================
pause
