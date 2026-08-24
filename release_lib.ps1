# release_lib.ps1 — helpers puros compartidos por build_windows.ps1 y release.ps1.
# Dot-source:  . "$PSScriptRoot\release_lib.ps1"
#
# No fija Set-StrictMode a proposito: se dot-sourcea en el scope del llamador y
# no debe cambiar el comportamiento de los scripts que lo usan.

# Ruta canonica: absoluta, con symlinks y '..' resueltos. Resolve-Path falla en
# rutas inexistentes, asi que se canonicaliza el ancestro existente mas profundo
# y se re-anexa el resto. Sin barra final salvo la raiz de unidad ("C:\").
function Get-CanonicalPath {
    param([Parameter(Mandatory)][string]$Path)
    # Absoluto y con '..'/'.' normalizados de entrada.
    $existing = [System.IO.Path]::GetFullPath($Path)
    $tail = ''
    while ($existing -and -not (Test-Path -LiteralPath $existing)) {
        $leaf = Split-Path -Leaf $existing
        $parent = Split-Path -Parent $existing
        if ([string]::IsNullOrEmpty($parent) -or $parent -eq $existing) { break }
        $tail = if ($tail) { Join-Path $leaf $tail } else { $leaf }
        $existing = $parent
    }
    if ($existing -and (Test-Path -LiteralPath $existing)) {
        $resolved = (Resolve-Path -LiteralPath $existing).ProviderPath
    } else {
        $resolved = [System.IO.Path]::GetFullPath($Path); $tail = ''
    }
    $full = if ($tail) { Join-Path $resolved $tail } else { $resolved }
    $full = [System.IO.Path]::GetFullPath($full)
    $trimmed = $full.TrimEnd('\', '/')
    if ($trimmed -match '^[A-Za-z]:$') { $trimmed += '\' }
    return $trimmed
}

# True si $Child es igual a, o descendiente de, $Parent (canonicos, sin distinguir
# mayus/minus en Windows). No cae en la trampa del prefijo hermano
# (C:\tiddl-gui-x NO esta dentro de C:\tiddl-gui).
function Test-PathContained {
    param([Parameter(Mandatory)][string]$Child, [Parameter(Mandatory)][string]$Parent)
    $c = Get-CanonicalPath $Child
    $p = Get-CanonicalPath $Parent
    if ($c -eq $p) { return $true }
    $pSep = if ($p.EndsWith('\')) { $p } else { $p + '\' }
    return $c.StartsWith($pSep, [System.StringComparison]::OrdinalIgnoreCase)
}

# Aborta si la fuente es igual a, o descendiente de, el staging: limpiar el
# staging borraria el repo.
function Assert-SourceNotUnderStaging {
    param([Parameter(Mandatory)][string]$Source, [Parameter(Mandatory)][string]$Staging)
    if (Test-PathContained -Child $Source -Parent $Staging) {
        throw "La fuente ('$Source') es igual o esta dentro del staging ('$Staging'): la limpieza del staging borraria el repo. Abortado."
    }
}

# Aborta si la ruta sigue existiendo (limpieza fallida = fallo explicito).
function Assert-PathAbsent {
    param([Parameter(Mandatory)][string]$Path, [string]$What = 'la ruta')
    if (Test-Path -LiteralPath $Path) { throw "$What no se pudo eliminar: '$Path' aun existe." }
}

# Elimina un directorio de forma estricta: falla si Remove-Item falla Y verifica
# que quedo ausente.
function Remove-DirStrict {
    param([Parameter(Mandatory)][string]$Path, [string]$What = 'el directorio')
    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop }
    Assert-PathAbsent -Path $Path -What $What
}

# Coincidencia EXACTA por componente (no por prefijo): '1.0.2' NO coincide con
# '1.0.22'. Se admite un 4o componente de build solo si es 0.
function Test-VersionMatch {
    param([Parameter(Mandatory)][string]$Exe, [Parameter(Mandatory)][string]$Want)
    $e = (($Exe -replace '[^0-9.]', '').Trim('.')) -split '\.'
    $w = $Want -split '\.'
    if ($w.Count -lt 3) { return $false }
    for ($i = 0; $i -lt 3; $i++) {
        if ($i -ge $e.Count -or $e[$i] -ne $w[$i]) { return $false }
    }
    if ($e.Count -ge 4 -and $e[3] -ne '0') { return $false }
    return $true
}

# Extrae el pin del motor (la ref tras '.git@') de requirements.txt.
function Get-EnginePin {
    param([Parameter(Mandatory)][string]$RequirementsPath)
    if (-not (Test-Path -LiteralPath $RequirementsPath -PathType Leaf)) {
        throw "No existe requirements.txt: '$RequirementsPath'."
    }
    $m = Select-String -Path $RequirementsPath -Pattern 'tiddl-elvigilante\s*@\s*git\+.*\.git@([0-9A-Za-z._-]+)'
    if (-not $m) { throw "No se pudo leer el pin del motor (tiddl-elvigilante @ ...git@<ref>) en '$RequirementsPath'." }
    return $m.Matches[0].Groups[1].Value
}

# Escribe el manifiesto de procedencia junto al build (version + pin del motor).
function Write-Provenance {
    param([Parameter(Mandatory)][string]$ManifestPath,
          [Parameter(Mandatory)][string]$Version,
          [Parameter(Mandatory)][string]$EnginePin)
    [ordered]@{ version = $Version; engine_pin = $EnginePin } | ConvertTo-Json |
        Set-Content -LiteralPath $ManifestPath -Encoding UTF8
}

# Valida (para -SkipGui) que el build reutilizado corresponde a la version pedida
# Y al pin del motor actual; si no, aborta (evita empaquetar un binario viejo con
# otro motor).
function Assert-Provenance {
    param([Parameter(Mandatory)][string]$ManifestPath,
          [Parameter(Mandatory)][string]$Version,
          [Parameter(Mandatory)][string]$EnginePin)
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "Sin manifiesto de procedencia ('$ManifestPath'): no se puede validar el build reutilizado. Rehaz el build (sin -SkipGui)."
    }
    $m = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($m.version -ne $Version) {
        throw "El build reutilizado es version '$($m.version)', se pidio '$Version'. Rehaz el build."
    }
    if ($m.engine_pin -ne $EnginePin) {
        throw "El build reutilizado embebe el motor '$($m.engine_pin)', requirements.txt pide '$EnginePin'. Rehaz el build."
    }
}
