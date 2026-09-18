$ErrorActionPreference = 'Stop'
$Startup = [Environment]::GetFolderPath('Startup')
$AutoCmd = Join-Path $Startup 'TMBT_NEXT_AUTOSTART.cmd'
if (Test-Path $AutoCmd) {
    Remove-Item $AutoCmd -Force
    Write-Host 'TMBT Next Autostart entfernt.' -ForegroundColor Green
} else {
    Write-Host 'Kein TMBT Next Autostart vorhanden.'
}
Read-Host 'Enter zum Schliessen'
