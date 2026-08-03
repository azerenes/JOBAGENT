# JOBAGENT komutunu Windows PATH'e ekleyen kurulum betiği
$ErrorActionPreference = 'Stop'
$proj = (Get-Item -LiteralPath $PSScriptRoot).FullName

$bat = @"
@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "$proj"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tui.py %*
) else (
  python tui.py %*
)
"@

$target = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
$targetFile = Join-Path $target 'JOBAGENT.bat'
$ok = $false

try {
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }
    Set-Content -LiteralPath $targetFile -Value $bat -Encoding Ascii
    $ok = $true
} catch {
    $target = Join-Path $env:USERPROFILE 'JOBAGENT'
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    $targetFile = Join-Path $target 'JOBAGENT.bat'
    Set-Content -LiteralPath $targetFile -Value $bat -Encoding Ascii
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($userPath -notlike "*$target*") {
        [Environment]::SetEnvironmentVariable('Path', $userPath + ';' + $target, 'User')
    }
}

if ($env:Path -notlike "*$target*") {
    [Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + $target, 'User')
}

Write-Host ""
Write-Host "JOBAGENT kuruldu: $targetFile"
Write-Host "Kullanmak icin YENI bir cmd / PowerShell penceresi acin ve su komutu calistirin:"
Write-Host "    JOBAGENT           (tam ekran terminal arayuzu acilir)"
Write-Host "    JOBAGENT web       (web arayuzu: http://127.0.0.1:5000)"
Write-Host "    JOBAGENT --cli     (satir tabanli terminal arayuzu)"
Write-Host ""
