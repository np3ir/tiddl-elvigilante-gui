# Pruebas (positivas y NEGATIVAS) de release_lib.ps1 — sin Pester.
#   pwsh -File tests\release_lib.Tests.ps1
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\release_lib.ps1"

$script:fail = 0
function Assert-Throws([scriptblock]$Body, [string]$Name) {
    try { & $Body; Write-Host "FAIL  $Name (no lanzo excepcion)" -ForegroundColor Red; $script:fail++ }
    catch { Write-Host "PASS  $Name" -ForegroundColor Green }
}
function Assert-True([bool]$Cond, [string]$Name) {
    if ($Cond) { Write-Host "PASS  $Name" -ForegroundColor Green }
    else { Write-Host "FAIL  $Name" -ForegroundColor Red; $script:fail++ }
}
function Assert-NoThrow([scriptblock]$Body, [string]$Name) {
    try { & $Body; Write-Host "PASS  $Name" -ForegroundColor Green }
    catch { Write-Host "FAIL  $Name ($_)" -ForegroundColor Red; $script:fail++ }
}

Write-Host "-- 1. rutas contenidas (fuente == o dentro del staging) --"
Assert-Throws { Assert-SourceNotUnderStaging -Source 'C:\tiddl-gui'          -Staging 'C:\tiddl-gui' } "fuente == staging -> rechazado"
Assert-Throws { Assert-SourceNotUnderStaging -Source 'C:\tiddl-gui\repo'      -Staging 'C:\tiddl-gui' } "fuente dentro del staging -> rechazado"
Assert-Throws { Assert-SourceNotUnderStaging -Source 'C:\tiddl-gui\a\..\repo' -Staging 'C:\tiddl-gui' } "fuente dentro (con ..) -> rechazado"
Assert-Throws { Assert-SourceNotUnderStaging -Source 'C:\tiddl-gui\'          -Staging 'C:\tiddl-gui' } "fuente == staging (barra final) -> rechazado"
Assert-NoThrow { Assert-SourceNotUnderStaging -Source 'G:\repo'              -Staging 'C:\tiddl-gui' } "fuente en otra unidad -> permitido"
Assert-True (-not (Test-PathContained -Child 'C:\tiddl-gui-extra' -Parent 'C:\tiddl-gui')) "prefijo hermano NO contenido"

Write-Host "-- 2. limpieza fallida (la ruta sigue existiendo) --"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("rl_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $tmp | Out-Null
Assert-Throws { Assert-PathAbsent -Path $tmp -What 'el staging' } "Assert-PathAbsent sobre dir existente -> lanza"
Assert-NoThrow { Remove-DirStrict -Path $tmp } "Remove-DirStrict elimina y verifica"
Assert-True (-not (Test-Path $tmp)) "el dir quedo ausente tras Remove-DirStrict"

Write-Host "-- 3. versiones incorrectas --"
Assert-True (-not (Test-VersionMatch -Exe '1.0.2'    -Want '1.0.22')) "1.0.2 != 1.0.22"
Assert-True (-not (Test-VersionMatch -Exe '1.0.20'   -Want '1.0.2'))  "1.0.20 != 1.0.2"
Assert-True (-not (Test-VersionMatch -Exe '1.0.22.5' -Want '1.0.22')) "1.0.22.5 (build!=0) != 1.0.22"
Assert-True (-not (Test-VersionMatch -Exe '1.0.16'   -Want '1.0.22')) "1.0.16 != 1.0.22"
Assert-True (Test-VersionMatch -Exe '1.0.22'   -Want '1.0.22') "1.0.22 == 1.0.22"
Assert-True (Test-VersionMatch -Exe '1.0.22.0' -Want '1.0.22') "1.0.22.0 == 1.0.22"

Write-Host "-- 4. procedencia vinculada por SHA-256 (-SkipGui) --"
$pdir = Join-Path ([System.IO.Path]::GetTempPath()) ("prov_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $pdir | Out-Null
$exe = Join-Path $pdir 'tiddl-gui.exe';    Set-Content -LiteralPath $exe -Value 'BINARIO-v1' -NoNewline
$mpy = Join-Path $pdir 'main.py';          Set-Content -LiteralPath $mpy -Value 'APP_VERSION = "1.0.22"' -NoNewline
$req = Join-Path $pdir 'requirements.txt'; Set-Content -LiteralPath $req -Value 'tiddl-elvigilante @ ...git@849105e' -NoNewline
$man = Join-Path $pdir 'provenance.json'
Write-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin '849105e' -ExePath $exe -MainPyPath $mpy -RequirementsPath $req -SourceCommit 'abc123'

Assert-NoThrow { Assert-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin '849105e' -ExePath $exe -MainPyPath $mpy -RequirementsPath $req } "procedencia compatible -> aceptada"
Assert-Throws  { Assert-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin 'deadbee' -ExePath $exe -MainPyPath $mpy -RequirementsPath $req } "pin de motor distinto -> rechazado"
Assert-Throws  { Assert-Provenance -ManifestPath $man -Version '1.0.23' -EnginePin '849105e' -ExePath $exe -MainPyPath $mpy -RequirementsPath $req } "version distinta -> rechazada"
Assert-Throws  { Assert-Provenance -ManifestPath (Join-Path $pdir 'nope.json') -Version '1.0.22' -EnginePin '849105e' -ExePath $exe -MainPyPath $mpy -RequirementsPath $req } "manifiesto ausente -> rechazado"
Set-Content -LiteralPath $exe -Value 'BINARIO-v2-CAMBIADO' -NoNewline
Assert-Throws  { Assert-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin '849105e' -ExePath $exe -MainPyPath $mpy -RequirementsPath $req } "exe con SHA-256 distinto -> rechazado"
Set-Content -LiteralPath $exe -Value 'BINARIO-v1' -NoNewline
Set-Content -LiteralPath $mpy -Value 'APP_VERSION = "1.0.22"  # editado' -NoNewline
Assert-Throws  { Assert-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin '849105e' -ExePath $exe -MainPyPath $mpy -RequirementsPath $req } "main.py con SHA-256 distinto -> rechazado"
Set-Content -LiteralPath $mpy -Value 'APP_VERSION = "1.0.22"' -NoNewline
Set-Content -LiteralPath $req -Value 'tiddl-elvigilante @ ...git@OTROPIN' -NoNewline
Assert-Throws  { Assert-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin '849105e' -ExePath $exe -MainPyPath $mpy -RequirementsPath $req } "requirements.txt con SHA-256 distinto -> rechazado"
Remove-Item -Recurse -Force $pdir

Write-Host "-- 5. version externa vs interna (release.ps1 -Version == APP_VERSION) --"
$vdir = Join-Path ([System.IO.Path]::GetTempPath()) ("ver_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $vdir | Out-Null
$mp = Join-Path $vdir 'main.py'; Set-Content -LiteralPath $mp -Value 'APP_VERSION = "1.0.22"'
Assert-True ((Get-AppVersion -MainPyPath $mp) -eq '1.0.22') "Get-AppVersion lee APP_VERSION"
Assert-Throws { Get-AppVersion -MainPyPath (Join-Path $vdir 'nope.py') } "main.py ausente -> lanza"
Assert-True ((Resolve-ReleaseVersion -Requested '' -AppVersion '1.0.22') -eq '1.0.22') "sin -Version -> usa APP_VERSION"
Assert-True ((Resolve-ReleaseVersion -Requested '1.0.22' -AppVersion '1.0.22') -eq '1.0.22') "-Version == APP_VERSION -> ok"
Assert-Throws { Resolve-ReleaseVersion -Requested '1.0.99' -AppVersion '1.0.22' } "-Version != APP_VERSION -> rechazado (externa contradice interna)"
Remove-Item -Recurse -Force $vdir

Write-Host ""
if ($script:fail -gt 0) { Write-Host "$($script:fail) prueba(s) FAIL" -ForegroundColor Red; exit 1 }
else { Write-Host "TODAS LAS PRUEBAS OK" -ForegroundColor Green; exit 0 }
