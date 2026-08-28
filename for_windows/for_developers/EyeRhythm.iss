; EyesRhythm Inno Setup script
; Compile with:  ISCC.exe EyeRhythm.iss
; Or simply run build_installer.bat
;
; Per-user install (no admin): %LOCALAPPDATA%\EyesRhythm
; Same freeze as the portable zip (dist\EyesRhythm).

#define MyAppName "EyesRhythm"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "EyesRhythm Contributors"
#define MyAppURL "https://github.com/pranaycv/EyeRhythm"
#define MyAppExeName "EyesRhythm.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; No admin: install next to other per-user apps.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output (relative to this .iss file)
OutputDir=Output
OutputBaseFilename=EyesRhythm-Setup
SetupIconFile=..\..\assets\EyeRhythm.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole PyInstaller folder
Source: "..\..\dist\EyesRhythm\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Windows will prompt for camera permission on first use.
  end;
end;
