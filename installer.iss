; Instalador de tiddl by ElVigilante (GUI binario unico + ffmpeg).
; Compilar con: ISCC.exe installer.iss
; Requiere haber corrido antes:
;   1. build_windows.ps1               -> C:\tiddl-gui\build\windows\  (GUI con tiddl embebido)
;   2. ffmpeg en C:\ffmpeg\bin\ffmpeg.exe
; Ya NO se compila un tiddl.exe aparte: tiddl viaja dentro del app (ver requirements.txt).

#define MyAppName "tiddl by ElVigilante"
; La version es OBLIGATORIA por linea de comandos: nunca un valor por defecto
; silencioso (antes caia a 1.0.16 y producia un instalable con version erronea).
; release.ps1 lee APP_VERSION desde main.py y pasa MyAppVersion automaticamente.
; Compilacion manual: ISCC.exe /DMyAppVersion=X.Y.Z installer.iss
; (X.Y.Z debe coincidir exactamente con APP_VERSION en main.py.)
#ifndef MyAppVersion
  #error MyAppVersion no fue definido. Compila con: ISCC /DMyAppVersion=X.Y.Z installer.iss
#endif
#define MyAppPublisher "ElVigilante"
#define MyAppURL "https://github.com/np3ir/tiddl-elvigilante"
#define MyAppExeName "tiddl-gui.exe"

[Setup]
AppId={{8F3E2D71-5A4B-4C9E-B1D2-tiddlElVigi}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\tiddl-ElVigilante
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=C:\tiddl-release\installer
OutputBaseFilename=tiddl-ElVigilante-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=assets\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Clean the app-managed payload BEFORE [Files] copies the new one, so an in-place
; upgrade can never leave orphaned files from a previous version (e.g. stale
; tiddl_elvigilante-*.dist-info that shadow the bundled engine's metadata, or an
; old tiddl.exe / dartjni.dll at the root). Scoped to ONLY what this app installs
; — never {app}\* — so the Inno uninstaller (unins000.exe / unins000.dat) and any
; unrelated file are preserved. flet build lays the payload out as these five
; directories plus root-level DLLs, the tiddl launcher(s) and ffmpeg.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\DLLs"
Type: filesandordirs; Name: "{app}\Lib"
Type: filesandordirs; Name: "{app}\site-packages"
Type: files; Name: "{app}\*.dll"
Type: files; Name: "{app}\tiddl*.exe"
Type: files; Name: "{app}\ffmpeg.exe"

[Files]
; GUI binario unico (carpeta completa de flet build - tiddl va embebido)
Source: "C:\tiddl-gui\build\windows\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; ffmpeg (requerido por tiddl para el remux; la GUI antepone {app} al PATH)
Source: "C:\ffmpeg\bin\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
