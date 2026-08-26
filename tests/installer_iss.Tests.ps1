# Static checks on installer.iss's [InstallDelete] section. A clean in-place
# upgrade must remove the app-managed payload (so stale engine dist-info / old
# binaries cannot linger and shadow the bundled engine's metadata) WITHOUT a
# destructive {app}\* wildcard and WITHOUT touching the Inno uninstaller.
#   pwsh -File tests\installer_iss.Tests.ps1
$ErrorActionPreference = 'Stop'
$iss = Get-Content "$PSScriptRoot\..\installer.iss" -Raw

$script:fail = 0
function Assert-True([bool]$Cond, [string]$Name) {
    if ($Cond) { Write-Host "PASS  $Name" -ForegroundColor Green }
    else { Write-Host "FAIL  $Name" -ForegroundColor Red; $script:fail++ }
}

Write-Host "-- installer.iss [InstallDelete] (clean in-place upgrade) --"

# The section must exist and come BEFORE [Files] (delete old payload, then copy new).
$idxDel   = $iss.IndexOf("[InstallDelete]")
$idxFiles = $iss.IndexOf("[Files]")
Assert-True ($idxDel -ge 0) "installer.iss tiene una seccion [InstallDelete]"
Assert-True ($idxDel -ge 0 -and $idxFiles -ge 0 -and $idxDel -lt $idxFiles) "[InstallDelete] aparece antes de [Files]"

# Body of [InstallDelete] only (up to the next [Section] header), reduced to the
# actual delete DIRECTIVES (Type:... lines) — comments (;) are excluded so the
# negative checks below cannot be fooled by explanatory text.
$m = [regex]::Match($iss, '(?ms)^\[InstallDelete\]\s*(.*?)(?=^\[)')
$body = if ($m.Success) { $m.Groups[1].Value } else { '' }
$del = ($body -split "`r?`n" | Where-Object { $_ -match '^\s*Type\s*:' }) -join "`n"

# 1) Limpieza de los CINCO directorios administrados (filesandordirs).
foreach ($d in 'app','data','DLLs','Lib','site-packages') {
    $rx = 'Type:\s*filesandordirs;\s*Name:\s*"\{app\}\\' + [regex]::Escape($d) + '"'
    Assert-True ($del -match $rx) "limpia directorio administrado {app}\$d (filesandordirs)"
}

# 2) Eliminacion de DLL / ejecutables antiguos en la raiz de {app}.
Assert-True ($del -match 'Type:\s*files;\s*Name:\s*"\{app\}\\\*\.dll"')      "elimina {app}\*.dll"
Assert-True ($del -match 'Type:\s*files;\s*Name:\s*"\{app\}\\tiddl\*\.exe"') "elimina {app}\tiddl*.exe"
Assert-True ($del -match 'Type:\s*files;\s*Name:\s*"\{app\}\\ffmpeg\.exe"')  "elimina {app}\ffmpeg.exe"

# 3) Preservacion EXPLICITA del desinstalador: no se borra unins000.exe/.dat.
Assert-True ($del -notmatch '(?i)unins')  "NO borra el desinstalador (unins000.exe/.dat)"

# 4) Ausencia de un wildcard destructivo sobre TODO {app}.
Assert-True ($del -notmatch '\{app\}\\\*"') 'NO usa el wildcard destructivo "{app}\*"'
Assert-True ($del -notmatch '\{app\}"')     'NO borra "{app}" entero'

Write-Host ""
if ($script:fail -gt 0) { Write-Host "$($script:fail) fallo(s)" -ForegroundColor Red; exit 1 }
else { Write-Host "Todos los checks de installer.iss OK" -ForegroundColor Green }
