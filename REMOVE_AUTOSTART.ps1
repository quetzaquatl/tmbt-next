$ErrorActionPreference = 'Stop'
$TaskName = 'TMBT Next AutoStart'
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host 'TMBT Next Autostart entfernt.' -ForegroundColor Green
} else {
    Write-Host 'Kein TMBT Next Autostart-Task vorhanden.'
}
Read-Host 'Enter zum Schliessen'
