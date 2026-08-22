; Aura - Windows Kurulum Scripti (Inno Setup)
; Bu script, Aura masaustu uygulamasini "Program Files" altina kurar,
; Baslat Menusu kisayolu ekler ve istege bagli masaustu kisayolu sunar.

#define MyAppName "Aura"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Aura"
#define MyAppExeName "ibrhm_app.exe"
; Bu klasoru kendi makinende asagidaki gibi ayarla:
#define SourceDir "C:\AuraProject\ibrhm_app\build\windows\x64\runner\Release"
#define IconFile "C:\AuraProject\ibrhm_app\windows\runner\resources\app_icon.ico"

[Setup]
AppId={{A17A0000-1111-4AURA-9999-AURAPROJECT01}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=C:\AuraProject\ibrhm_app\installer_output
OutputBaseFilename=AuraKurulum
SetupIconFile={#IconFile}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableDirPage=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{#IconFile}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{#IconFile}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent