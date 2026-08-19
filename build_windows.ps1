# Build del instalable de Windows para tiddl GUI.
# Flutter rechaza rutas con caracteres especiales o espacios (el "!" de C:\!z y
# el espacio de "G:\My Drive"), asi que el build corre desde C:\tiddl-gui: este
# script sincroniza el codigo alli y ejecuta flet build. El resultado queda en
# C:\tiddl-gui\build\windows\.
#
# Ejecutar desde PowerShell 7 (pwsh) — flet build necesita pwsh en el PATH para
# validar Flutter; NO funciona desde Git Bash.

$src = "G:\My Drive\Backups\zhome-2026-07-25\tiddl-gui"
$dst = "C:\tiddl-gui"
$expectedDst = [System.IO.Path]::GetFullPath("C:\tiddl-gui")
$resolvedDst = [System.IO.Path]::GetFullPath($dst)
if ($resolvedDst -ne $expectedDst) {
    throw "Destino de build inesperado: $resolvedDst"
}
$versionMatch = Select-String -Path "$src\main.py" -Pattern '^APP_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$'
if (-not $versionMatch) { throw "No se pudo leer APP_VERSION desde main.py" }
$appVersion = $versionMatch.Matches[0].Groups[1].Value

New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "$src\main.py", "$src\requirements.txt" $dst -Force

# Limpia el build anterior para que reempaquete el main.py nuevo (y el tiddl
# fijado en requirements.txt) desde cero.
Remove-Item -Recurse -Force "$dst\build" -ErrorAction SilentlyContinue

# Flutter y el pub-cache (con serious_python parcheado) viven bajo C:\fb.
# No se sobrescriben HOME/USERPROFILE: el código fuente ya se copia a una ruta
# sin espacios y las cachés que necesitan ruta corta tienen variables propias.
$env:PUB_CACHE = "C:\fb\pubcache"
$env:PATH = "C:\fb\flutter\3.44.4\bin;$env:PATH"

Set-Location $dst
"y" | flet build windows --project tiddl-gui --product "tiddl by ElVigilante" --company ElVigilante --build-version $appVersion
