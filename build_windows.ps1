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

New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "$src\main.py", "$src\requirements.txt" $dst -Force

# Limpia el build anterior para que reempaquete el main.py nuevo (y el tiddl
# fijado en requirements.txt) desde cero.
Remove-Item -Recurse -Force "$dst\build" -ErrorAction SilentlyContinue

# Entorno de build: el usuario "DJ Elvigilante" lleva espacio y rompe los hooks
# de Flutter, por eso HOME/USERPROFILE apuntan a C:\fb. Flutter y el pub-cache
# (con el serious_python parcheado) viven bajo C:\fb.
$env:HOME = "C:\fb"
$env:USERPROFILE = "C:\fb"
$env:PUB_CACHE = "C:\fb\pubcache"
$env:PATH = "C:\fb\flutter\3.44.4\bin;$env:PATH"

Set-Location $dst
"y" | flet build windows --project tiddl-gui --product "tiddl by ElVigilante" --company ElVigilante --build-version 1.0.0
