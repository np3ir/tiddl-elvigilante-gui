# Release de tiddl by ElVigilante: GUI binario unico + instalador.
#
#   .\release.ps1                      # release completo (fuente = carpeta del script)
#   .\release.ps1 -Version 1.1.0       # forzar version
#   .\release.ps1 -Src D:\repos\tiddl-gui   # otra copia del repo
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

[CmdletBinding()]
param(
    [string]$Version = "",
    [string]$Src = $PSScriptRoot,
    [switch]$SkipGui
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\release_lib.ps1"

# $Src = carpeta con main.py + requirements.txt + assets (fuente real de la GUI).
# Por defecto es la carpeta de este script; validada para no depender de una
# ruta hardcodeada que ya no existe.
if (-not $Src) { throw "No se pudo determinar la carpeta fuente. Pasa -Src <repo tiddl-gui>." }
$Src = [System.IO.Path]::GetFullPath($Src)
foreach ($f in @("main.py", "requirements.txt")) {
    if (-not (Test-Path (Join-Path $Src $f) -PathType Leaf)) {
        throw "Fuente invalida: falta '$f' en '$Src'. Pasa -Src <carpeta del repo tiddl-gui>."
    }
}
# Validacion anticipada del icono del instalador (installer.iss lo exige).
if (-not (Test-Path (Join-Path $Src "assets\icon.ico") -PathType Leaf)) {
    throw "Falta 'assets\icon.ico' en '$Src' (requerido por installer.iss)."
}

$work = "C:\tiddl-gui"
$rel  = "C:\tiddl-release"
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"

if (-not $Version) {
    $versionMatch = Select-String -Path (Join-Path $Src "main.py") -Pattern '^APP_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$'
    if (-not $versionMatch) { throw "No se pudo leer APP_VERSION desde main.py" }
    $Version = $versionMatch.Matches[0].Groups[1].Value
}
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { throw "Version invalida: '$Version' (esperado X.Y.Z)." }

# ---------- 1. GUI (flet build) ----------
if (-not $SkipGui) {
    Write-Host "[1/2] Compilando GUI (flet build windows)..." -ForegroundColor Cyan

    # Guard: validar la identidad de $work ANTES de cualquier limpieza destructiva.
    $expectedWork = [System.IO.Path]::GetFullPath("C:\tiddl-gui")
    $resolvedWork = [System.IO.Path]::GetFullPath($work)
    if ($resolvedWork -ne $expectedWork) { throw "Staging inesperado: '$resolvedWork'. Abortado por seguridad." }
    # Canonico: rechazar que la fuente sea igual o descendiente del staging.
    Assert-SourceNotUnderStaging -Source $Src -Staging $work
    New-Item -ItemType Directory -Force $work | Out-Null

    # La carpeta del proyecto debe quedar limpia: flet build empaqueta todo lo
    # que encuentre en ella (excepto build\). Fallo explicito si algo no se borra.
    Get-ChildItem $work -Force -Exclude build | Where-Object { $_.Name -notin "main.py", "requirements.txt", "assets" } |
        Remove-Item -Recurse -Force -ErrorAction Stop

    # Sincronizacion explicita de fuentes + assets. Se borra SIEMPRE el assets
    # del staging antes de decidir (y se ABORTA si el borrado falla) para no
    # arrastrar assets viejos cuando la fuente actual no tiene assets.
    Copy-Item (Join-Path $Src "main.py"), (Join-Path $Src "requirements.txt") $work -Force
    $srcAssets = Join-Path $Src "assets"
    $dstAssets = Join-Path $work "assets"
    if (Test-Path $dstAssets) { Remove-Item -Recurse -Force $dstAssets -ErrorAction Stop }
    if (Test-Path $srcAssets) {
        Copy-Item $srcAssets $work -Recurse -Force
    } else {
        Write-Warning "No hay carpeta assets/ en '$Src' — el instalador espera assets\icon.ico."
    }

    # Elimina el build anterior OBLIGATORIAMENTE antes de Flet (falla si no puede).
    Remove-DirStrict -Path (Join-Path $work "build") -What 'el build anterior'

    Set-Location $work
    "y" | flet build windows --project tiddl-gui --product "tiddl by ElVigilante" `
        --company ElVigilante --build-version $Version

    # Manifiesto de procedencia (version + pin del motor) para validar en -SkipGui.
    Write-Provenance -ManifestPath (Join-Path $work "build\provenance.json") `
        -Version $Version -EnginePin (Get-EnginePin -RequirementsPath (Join-Path $work "requirements.txt"))
} else { Write-Host "[1/2] GUI: reusando build existente" -ForegroundColor Yellow }

# Con -SkipGui: validar la procedencia del build reutilizado contra el pin actual
# de requirements.txt (evita empaquetar un binario 1.0.22 con OTRO motor).
if ($SkipGui) {
    Assert-Provenance -ManifestPath (Join-Path $work "build\provenance.json") `
        -Version $Version -EnginePin (Get-EnginePin -RequirementsPath (Join-Path $Src "requirements.txt"))
}

# Verificacion del ejecutable — SIEMPRE, incluso con -SkipGui: un instalador
# etiquetado $Version no debe empaquetar un binario viejo que quedo en el staging.
$exe = "$work\build\windows\tiddl-gui.exe"
if (-not (Test-Path $exe -PathType Leaf)) { throw "No existe el ejecutable de la GUI: $exe" }
$exeVersion = (Get-Item $exe).VersionInfo.ProductVersion
if (-not $exeVersion) { $exeVersion = (Get-Item $exe).VersionInfo.FileVersion }
if (-not $exeVersion) { throw "El exe '$exe' no expone metadatos de version; no se puede verificar contra '$Version'." }
if (-not (Test-VersionMatch -Exe $exeVersion -Want $Version)) {
    throw "Version del exe ('$exeVersion') no coincide con la pedida ('$Version')."
}

# ---------- 2. Instalador (Inno Setup) ----------
# (tiddl ya no se compila aparte: flet build lo embebio via requirements.txt)
Write-Host "[2/2] Compilando instalador (Inno Setup)..." -ForegroundColor Cyan
if (-not (Test-Path "C:\ffmpeg\bin\ffmpeg.exe")) { throw "ffmpeg no encontrado en C:\ffmpeg\bin" }
if (-not (Test-Path $iscc)) { throw "ISCC.exe no encontrado en $iscc" }
# /DMyAppVersion es obligatorio: installer.iss ahora ABORTA si no se define
# (ya no cae silenciosamente a una version por defecto).
& $iscc "/DMyAppVersion=$Version" (Join-Path $Src "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC fallo (exit $LASTEXITCODE)" }

$setup = "$rel\installer\tiddl-ElVigilante-Setup-$Version.exe"
if (-not (Test-Path $setup -PathType Leaf)) { throw "El instalador esperado no existe (o no es un archivo): $setup" }
$mb = [math]::Round((Get-Item $setup).Length / 1MB)
Write-Host ""
Write-Host "RELEASE OK -> $setup ($mb MB)" -ForegroundColor Green
