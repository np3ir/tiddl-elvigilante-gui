# Build del instalable de Windows para tiddl GUI.
# Flutter rechaza rutas con caracteres especiales o espacios (el "!" de C:\!z y
# el espacio de "G:\My Drive"), asi que el build corre desde C:\tiddl-gui: este
# script sincroniza el codigo alli y ejecuta flet build. El resultado queda en
# C:\tiddl-gui\build\windows\.
#
# Fuente (-Src): por defecto la carpeta de ESTE script (el workspace real del
# repo). Se puede sobreescribir para builds desde otra copia:
#   pwsh -File build_windows.ps1                 # usa $PSScriptRoot
#   pwsh -File build_windows.ps1 -Src D:\repos\tiddl-gui
#
# Ejecutar desde PowerShell 7 (pwsh) — flet build necesita pwsh en el PATH para
# validar Flutter; NO funciona desde Git Bash.

[CmdletBinding()]
param(
    [string]$Src = $PSScriptRoot,
    [string]$Dst = "C:\tiddl-gui"
)

$ErrorActionPreference = "Stop"

# ---- Fuente: el workspace real, validado (no una ruta hardcodeada/stale) ----
if (-not $Src) { throw "No se pudo determinar la carpeta fuente. Pasa -Src <repo tiddl-gui>." }
$Src = [System.IO.Path]::GetFullPath($Src)
foreach ($f in @("main.py", "requirements.txt")) {
    if (-not (Test-Path (Join-Path $Src $f))) {
        throw "Fuente invalida: falta '$f' en '$Src'. Pasa -Src <carpeta del repo tiddl-gui>."
    }
}

# ---- Version: obligatoria, leida de main.py (nunca un valor por defecto) ----
$versionMatch = Select-String -Path (Join-Path $Src "main.py") -Pattern '^APP_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$'
if (-not $versionMatch) { throw "No se pudo leer APP_VERSION (X.Y.Z) desde main.py" }
$appVersion = $versionMatch.Matches[0].Groups[1].Value

# ---- Destino de build: validar identidad ANTES de cualquier limpieza ----
$expectedDst = [System.IO.Path]::GetFullPath("C:\tiddl-gui")
$resolvedDst = [System.IO.Path]::GetFullPath($Dst)
if ($resolvedDst -ne $expectedDst) {
    throw "Destino de build inesperado: '$resolvedDst' (esperado '$expectedDst'). Abortado por seguridad."
}
if ($resolvedDst -eq $Src) {
    throw "El destino de build no puede ser la carpeta fuente ('$Src')."
}
New-Item -ItemType Directory -Force $Dst | Out-Null

# ---- Staging limpio: flet EMPAQUETA todo lo que haya en la carpeta del ----
# proyecto, asi que $Dst debe contener SOLO main.py, requirements.txt y assets.
# Se borra cualquier otro resto de builds anteriores (menos build\, que se
# regenera abajo) para no arrastrarlo al instalable.
Get-ChildItem $Dst -Force | Where-Object {
    $_.Name -ne "build" -and $_.Name -notin @("main.py", "requirements.txt", "assets")
} | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# ---- Sincronizacion explicita de fuentes + assets ----
Copy-Item (Join-Path $Src "main.py") $Dst -Force
Copy-Item (Join-Path $Src "requirements.txt") $Dst -Force
$srcAssets = Join-Path $Src "assets"
$dstAssets = Join-Path $Dst "assets"
# Borrar SIEMPRE el assets del staging antes de decidir (y ABORTAR si el borrado
# falla): asi un build cuya fuente no tiene assets no arrastra los de otra fuente.
if (Test-Path $dstAssets) { Remove-Item -Recurse -Force $dstAssets -ErrorAction Stop }
if (Test-Path $srcAssets) {
    Copy-Item $srcAssets $Dst -Recurse -Force
    Write-Host "assets/ sincronizado a $dstAssets" -ForegroundColor DarkGray
} else {
    Write-Warning "No hay carpeta assets/ en '$Src' — el icono de la app puede faltar."
}

# ---- Limpia el build anterior para reempaquetar desde cero ----
Remove-Item -Recurse -Force (Join-Path $Dst "build") -ErrorAction SilentlyContinue

# Flutter y el pub-cache (con serious_python parcheado) viven bajo C:\fb.
# No se sobrescriben HOME/USERPROFILE: el código fuente ya se copia a una ruta
# sin espacios y las cachés que necesitan ruta corta tienen variables propias.
$env:PUB_CACHE = "C:\fb\pubcache"
$env:PATH = "C:\fb\flutter\3.44.4\bin;$env:PATH"

Set-Location $Dst
"y" | flet build windows --project tiddl-gui --product "tiddl by ElVigilante" --company ElVigilante --build-version $appVersion

# ---- Verificacion posterior: existe el exe y su version coincide ----
$exe = Join-Path $Dst "build\windows\tiddl-gui.exe"
if (-not (Test-Path $exe -PathType Leaf)) { throw "flet build fallo: no existe el ejecutable '$exe'." }
$exeVersion = (Get-Item $exe).VersionInfo.ProductVersion
if (-not $exeVersion) { $exeVersion = (Get-Item $exe).VersionInfo.FileVersion }
if ($exeVersion) {
    # Comparacion EXACTA por componente (no por prefijo): '1.0.2' no debe pasar
    # por '1.0.22'. Se admite un 4o componente de build solo si es 0.
    $exeParts = (($exeVersion -replace '[^0-9.]', '').Trim('.')) -split '\.'
    $wantParts = $appVersion -split '\.'
    $mismatch = $false
    for ($i = 0; $i -lt 3; $i++) { if ($exeParts[$i] -ne $wantParts[$i]) { $mismatch = $true } }
    if ($exeParts.Count -ge 4 -and $exeParts[3] -ne '0') { $mismatch = $true }
    if ($mismatch) { throw "Version del exe ('$exeVersion') no coincide con APP_VERSION ('$appVersion')." }
} else {
    Write-Warning "El exe no expone version — no se pudo verificar contra APP_VERSION ('$appVersion')."
}
Write-Host ""
Write-Host "BUILD OK -> $exe  (exe='$exeVersion', APP_VERSION=$appVersion)" -ForegroundColor Green
