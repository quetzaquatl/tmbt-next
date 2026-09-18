$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $RepoRoot 'TMBT_NEXT_BETA\START_TMBT_NEXT.bat'
if (-not (Test-Path $Launcher)) { throw "Launcher fehlt: $Launcher" }

$TaskName = 'TMBT Next AutoStart'
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c ""{0}""' -f $Launcher) -WorkingDirectory (Split-Path -Parent $Launcher)
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Trigger.Delay = 'PT30S'
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Starts TMBT Next and its feed guardian automatically after Windows logon.' -Force | Out-Null

Write-Host ''
Write-Host 'TMBT Next Autostart ist eingerichtet.' -ForegroundColor Green
Write-Host 'Windows-Login -> 30 Sekunden warten -> TMBT Next + Feed Guardian starten automatisch.'
Write-Host 'Der Feed Guardian startet/restartet den vorhandenen Twelve-Collector, wenn er ihn im Workspace findet.'
Write-Host ''
Read-Host 'Enter zum Schliessen'
