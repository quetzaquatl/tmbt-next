$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

Write-Host ''
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host 'TMBT NEXT - UPDATE + START' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host 'FEHLER: Git wurde nicht gefunden.' -ForegroundColor Red
    Write-Host 'Installiere Git for Windows und starte danach erneut.'
    Read-Host 'Enter zum Schliessen'
    exit 1
}

if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
    Write-Host 'FEHLER: Dieser Ordner ist kein Git-Clone von tmbt-next.' -ForegroundColor Red
    Write-Host 'Nutze einmalig den Installationsbefehl aus dem Chat; danach funktioniert dieser Launcher dauerhaft.'
    Read-Host 'Enter zum Schliessen'
    exit 2
}

$dirty = @(git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw 'git status fehlgeschlagen.' }
if ($dirty.Count -gt 0) {
    Write-Host ''
    Write-Host 'Lokale Aenderungen gefunden. Aus Sicherheitsgruenden wird NICHT automatisch ueberschrieben:' -ForegroundColor Yellow
    git status --short
    Write-Host ''
    Write-Host 'Schick diese Ausgabe in den Chat; wir mergen die Aenderungen sauber.' -ForegroundColor Yellow
    Read-Host 'Enter zum Schliessen'
    exit 3
}

Write-Host ''
Write-Host 'Hole aktuellen GitHub-Stand ...' -ForegroundColor DarkCyan
git fetch origin main
if ($LASTEXITCODE -ne 0) { throw 'git fetch origin main fehlgeschlagen.' }

git merge --ff-only origin/main
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Fast-forward Update war nicht moeglich. Es wurde nichts erzwungen.' -ForegroundColor Red
    Read-Host 'Enter zum Schliessen'
    exit 4
}

$commit = (git rev-parse --short HEAD).Trim()
Write-Host "Aktuell: $commit" -ForegroundColor Green

$StartBat = Join-Path $RepoRoot 'TMBT_NEXT_BETA\START_TMBT_NEXT.bat'
if (-not (Test-Path $StartBat)) {
    Write-Host "FEHLER: Startdatei fehlt: $StartBat" -ForegroundColor Red
    Read-Host 'Enter zum Schliessen'
    exit 5
}

Write-Host 'Starte TMBT Next ...' -ForegroundColor Green
Start-Process -FilePath $StartBat -WorkingDirectory (Split-Path -Parent $StartBat)
