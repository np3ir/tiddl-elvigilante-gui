; Instalador de tiddl by ElVigilante (GUI binario unico + ffmpeg).
; Compilar con: ISCC.exe installer.iss
; Requiere haber corrido antes:
;   1. build_windows.ps1               -> C:\tiddl-gui\build\windows\  (GUI con tiddl embebido)
;   2. ffmpeg en C:\ffmpeg\bin\ffmpeg.exe
; Ya NO se compila un tiddl.exe aparte: tiddl viaja dentro del app (ver requirements.txt).

#define MyAppName "tiddl by ElVigilante"
; La version es OBLIGATORIA por linea de comandos: nunca un valor por defecto
; silencioso (antes caia a 1.0.16 y producia un instalable con version erronea).
;   ISCC.exe /DMyAppVersion=1.0.22 installer.iss
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
