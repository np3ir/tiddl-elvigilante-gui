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

# Lee APP_VERSION (X.Y.Z) de main.py.
function Get-AppVersion {
    param([Parameter(Mandatory)][string]$MainPyPath)
    if (-not (Test-Path -LiteralPath $MainPyPath -PathType Leaf)) { throw "No existe main.py: '$MainPyPath'." }
    $m = Select-String -Path $MainPyPath -Pattern '^APP_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$'
    if (-not $m) { throw "No se pudo leer APP_VERSION (X.Y.Z) de '$MainPyPath'." }
    return $m.Matches[0].Groups[1].Value
}

# Version a usar en el release: si se pidio una explicita, DEBE coincidir con
# APP_VERSION de main.py (la version externa del exe no puede contradecir la
# interna de la app). Sin pedido -> se usa APP_VERSION.
function Resolve-ReleaseVersion {
    param([string]$Requested, [Parameter(Mandatory)][string]$AppVersion)
    if ($Requested) {
        if ($Requested -ne $AppVersion) {
            throw "La version pedida ('$Requested') no coincide con APP_VERSION de main.py ('$AppVersion'): la version externa del ejecutable no puede contradecir la interna de la app."
        }
        return $Requested
    }
    return $AppVersion
}

# SHA-256 (hex mayus) de un archivo.
function Get-FileSha256 {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "No existe el archivo para hashear: '$Path'." }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
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

# Escribe el manifiesto de procedencia junto al build. Lo VINCULA al artefacto por
# SHA-256 del ejecutable, main.py y requirements.txt, mas version, pin del motor y
# commit fuente.
function Write-Provenance {
    param([Parameter(Mandatory)][string]$ManifestPath,
          [Parameter(Mandatory)][string]$Version,
          [Parameter(Mandatory)][string]$EnginePin,
          [Parameter(Mandatory)][string]$ExePath,
          [Parameter(Mandatory)][string]$MainPyPath,
          [Parameter(Mandatory)][string]$RequirementsPath,
          [string]$SourceCommit = 'unknown')
    [ordered]@{
        version             = $Version
        engine_pin          = $EnginePin
        source_commit       = $SourceCommit
        exe_sha256          = (Get-FileSha256 $ExePath)
        main_py_sha256      = (Get-FileSha256 $MainPyPath)
        requirements_sha256 = (Get-FileSha256 $RequirementsPath)
    } | ConvertTo-Json | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
}

# Valida (para -SkipGui) que el build reutilizado corresponde EXACTAMENTE al
# artefacto y a la fuente actuales: version, pin del motor y SHA-256 del exe en
# disco + del main.py / requirements.txt actuales. Cualquier discrepancia aborta
# (evita empaquetar un binario viejo o construido con otra fuente/motor).
function Assert-Provenance {
    param([Parameter(Mandatory)][string]$ManifestPath,
          [Parameter(Mandatory)][string]$Version,
          [Parameter(Mandatory)][string]$EnginePin,
          [Parameter(Mandatory)][string]$ExePath,
          [Parameter(Mandatory)][string]$MainPyPath,
          [Parameter(Mandatory)][string]$RequirementsPath)
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
    if ($m.exe_sha256 -ne (Get-FileSha256 $ExePath)) {
        throw "El ejecutable reutilizado no coincide con el SHA-256 del manifiesto (binario cambiado/corrupto). Rehaz el build."
    }
    if ($m.main_py_sha256 -ne (Get-FileSha256 $MainPyPath)) {
        throw "main.py cambio desde el build reutilizado (SHA-256 distinto). Rehaz el build."
    }
    if ($m.requirements_sha256 -ne (Get-FileSha256 $RequirementsPath)) {
        throw "requirements.txt cambio desde el build reutilizado (SHA-256 distinto). Rehaz el build."
    }
}
