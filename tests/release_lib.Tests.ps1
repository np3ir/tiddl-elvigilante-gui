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

Write-Host "-- 4. procedencia incompatible (-SkipGui) --"
$pdir = Join-Path ([System.IO.Path]::GetTempPath()) ("prov_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $pdir | Out-Null
$man = Join-Path $pdir 'provenance.json'
Write-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin '849105e'
Assert-Throws { Assert-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin 'deadbee' } "pin de motor distinto -> rechazado"
Assert-Throws { Assert-Provenance -ManifestPath $man -Version '1.0.23' -EnginePin '849105e' } "version de manifiesto distinta -> rechazada"
Assert-Throws { Assert-Provenance -ManifestPath (Join-Path $pdir 'nope.json') -Version '1.0.22' -EnginePin '849105e' } "manifiesto ausente -> rechazado"
Assert-NoThrow { Assert-Provenance -ManifestPath $man -Version '1.0.22' -EnginePin '849105e' } "procedencia compatible -> aceptada"
Remove-Item -Recurse -Force $pdir

Write-Host ""
if ($script:fail -gt 0) { Write-Host "$($script:fail) prueba(s) FAIL" -ForegroundColor Red; exit 1 }
else { Write-Host "TODAS LAS PRUEBAS OK" -ForegroundColor Green; exit 0 }
