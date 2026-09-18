$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $RepoRoot 'TMBT_NEXT_BETA\START_TMBT_NEXT.bat'
if (-not (Test-Path $Launcher)) { throw "Launcher fehlt: $Launcher" }

$Startup = [Environment]::GetFolderPath('Startup')
if (-not (Test-Path $Startup)) { throw "Windows Startup-Ordner nicht gefunden." }

$AutoCmd = Join-Path $Startup 'TMBT_NEXT_AUTOSTART.cmd'
$Content = @"
@echo off
timeout /t 30 /nobreak >nul
start "" "$Launcher"
"@
Set-Content -Path $AutoCmd -Value $Content -Encoding ASCII

Write-Host ''
Write-Host 'TMBT Next Autostart ist eingerichtet.' -ForegroundColor Green
Write-Host "Startup-Datei: $AutoCmd"
Write-Host 'Nach Windows-Login: 30 Sekunden warten -> TMBT Next + Feed Guardian starten automatisch.'
Write-Host 'Kein Administratorrecht und kein taegliches manuelles Starten noetig.'
Write-Host ''
Read-Host 'Enter zum Schliessen'
