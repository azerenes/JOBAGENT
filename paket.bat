@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Kaynak paketi olusturuluyor: JOBAGENT_paket.zip
echo ============================================
if exist "JOBAGENT_paket.zip" del "JOBAGENT_paket.zip"
tar -a -c -f JOBAGENT_paket.zip ^
  --exclude=.venv --exclude=data --exclude=dist --exclude=build ^
  --exclude=.git --exclude=__pycache__ --exclude="*.spec" --exclude="*.pyc" ^
  --exclude="*.log" --exclude=config.json ^
  . 
if errorlevel 1 (
  echo Paketleme hatasi.
  pause
  exit /b 1
)
echo.
echo  Hazir: JOBAGENT_paket.zip
echo  Kullanici bu zip'i acip setup.bat calistirir, sonra JOBAGENT yazar.
pause
