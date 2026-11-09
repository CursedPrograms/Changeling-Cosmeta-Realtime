# Changeling Cosmetics Realtime runs in Changeling CopyCat Realtime's environment with Changeling Cosmetics' code:
# both next to this folder (as in Changeling Studio). Missing ones are fetched here.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Studio = Split-Path $PSScriptRoot -Parent
foreach ($a in @("Cosmetics", "CopyCat-Realtime")) {
    $dir = Join-Path $Studio "Changeling-$a"
    if (-not (Test-Path $dir)) {
        Write-Host "Getting Changeling $a ..."
        git clone "https://github.com/CursedPrograms/Changeling-$a" $dir
    }
}
$Py = Join-Path $Studio "Changeling-CopyCat-Realtime\venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "Setting up Changeling CopyCat Realtime first, once: its environment and its models. Close its window when it opens."
    & (Join-Path $Studio "Changeling-CopyCat-Realtime\run.ps1") --no-virtual
}
& $Py cosmetics_live.py @args
