# PC Check - avvio con un comando su Windows (PowerShell):
#   irm https://raw.githubusercontent.com/pezzaliapp/pc-check/main/run.ps1 | iex
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Raw = if ($env:PC_CHECK_RAW) { $env:PC_CHECK_RAW } else { "https://raw.githubusercontent.com/pezzaliapp/pc-check/main" }
$Dir = Join-Path $env:USERPROFILE ".pc-check"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null

function Find-Python {
    foreach ($c in @("py", "python", "python3")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        # esclude il finto python.exe di WindowsApps che apre solo lo Store
        if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { return $cmd.Source }
    }
    $local = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
             Sort-Object FullName -Descending | Select-Object -First 1
    if ($local) { return $local.FullName }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "Python non e' installato. E' gratuito e serve per far funzionare PC Check." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $ans = Read-Host "Vuoi installarlo ora con winget (solo per il tuo utente)? [S/N]"
        if ($ans -match '^[sSyY]') {
            winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
            $py = Find-Python
        }
    }
    if (-not $py) {
        Write-Host "Installa Python da https://www.python.org/downloads/ (spunta 'Add python.exe to PATH') e riprova." -ForegroundColor Red
        return
    }
}

Write-Host "Scarico l'ultima versione di PC Check..."
Invoke-WebRequest -UseBasicParsing "$Raw/pc_check.py" -OutFile "$Dir\pc_check.py"

$venvPy = "$Dir\venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    & $py -m venv "$Dir\venv"
}
& $venvPy -m pip install -q --disable-pip-version-check --upgrade psutil
& $venvPy "$Dir\pc_check.py" @args
