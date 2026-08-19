# Release de tiddl by ElVigilante: GUI binario unico + instalador.
#
#   .\release.ps1                      # release completo
#   .\release.ps1 -Version 1.1.0       # nueva version
#   .\release.ps1 -SkipGui             # reusar el build de GUI existente
#
# Resultado: C:\tiddl-release\installer\tiddl-ElVigilante-Setup-<version>.exe
#
# Notas (aprendidas a golpes):
# - flet build NO funciona desde rutas con "!" (C:\!z) -> se trabaja en C:\tiddl-gui
# - flet build EMPAQUETA TODO lo que haya en la carpeta del proyecto -> C:\tiddl-gui
#   debe contener SOLO main.py, requirements.txt y assets (si no, el setup crece)
# - flet 0.86 pregunta por su Flutter SDK propio -> se auto-responde "y"
# - tiddl ya NO se compila aparte con PyInstaller: viaja embebido en el app
#   porque requirements.txt lo declara como dependencia git (binario unico).

param(
    [string]$Version = "",
    [switch]$SkipGui
)

$ErrorActionPreference = "Stop"
# $src = carpeta con main.py + requirements.txt + assets (fuente de la GUI).
$src  = "C:\!z\home\tiddl-flet"
$work = "C:\tiddl-gui"
$rel  = "C:\tiddl-release"
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"

if (-not $Version) {
    $versionMatch = Select-String -Path "$src\main.py" -Pattern '^APP_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$'
    if (-not $versionMatch) { throw "No se pudo leer APP_VERSION desde main.py" }
    $Version = $versionMatch.Matches[0].Groups[1].Value
}

# ---------- 1. GUI (flet build) ----------
if (-not $SkipGui) {
    Write-Host "[1/2] Compilando GUI (flet build windows)..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force $work | Out-Null
    # La carpeta del proyecto debe quedar limpia: flet build empaqueta todo lo
    # que encuentre en ella (excepto build\).
    Get-ChildItem $work -Exclude build | Where-Object { $_.Name -notin "main.py", "requirements.txt", "assets" } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item "$src\main.py", "$src\requirements.txt" $work -Force
    Copy-Item "$src\assets" $work -Recurse -Force
    Set-Location $work
    "y" | flet build windows --project tiddl-gui --product "tiddl by ElVigilante" `
        --company ElVigilante --build-version $Version
    if (-not (Test-Path "$work\build\windows\tiddl-gui.exe")) {
        throw "flet build fallo: no existe $work\build\windows\tiddl-gui.exe"
    }
} else { Write-Host "[1/2] GUI: reusando build existente" -ForegroundColor Yellow }

# ---------- 2. Instalador (Inno Setup) ----------
# (tiddl ya no se compila aparte: flet build lo embebio via requirements.txt)
Write-Host "[2/2] Compilando instalador (Inno Setup)..." -ForegroundColor Cyan
if (-not (Test-Path "C:\ffmpeg\bin\ffmpeg.exe")) { throw "ffmpeg no encontrado en C:\ffmpeg\bin" }
if (-not (Test-Path $iscc)) { throw "ISCC.exe no encontrado en $iscc" }
& $iscc "/DMyAppVersion=$Version" "$src\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "ISCC fallo (exit $LASTEXITCODE)" }

$setup = "$rel\installer\tiddl-ElVigilante-Setup-$Version.exe"
$mb = [math]::Round((Get-Item $setup).Length / 1MB)
Write-Host ""
Write-Host "RELEASE OK -> $setup ($mb MB)" -ForegroundColor Green
