; Inno Setup script: builds yWorkspace-Setup.exe from the PyInstaller folder (dist\yworkspace).
; Build: iscc installer\windows\yworkspace.iss
[Setup]
AppName=yWorkspace
AppVersion=0.1.0
AppPublisher=YunUSlu (Yunus Emre USLU)
DefaultDirName={autopf}\yWorkspace
DefaultGroupName=yWorkspace
OutputBaseFilename=yWorkspace-Setup
OutputDir=..\..\dist
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\..\..\LICENSE

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\..\dist\yworkspace\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\yWorkspace"; Filename: "{app}\yworkspace.exe"
Name: "{autodesktop}\yWorkspace"; Filename: "{app}\yworkspace.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"

[Registry]
; Put yworkspace.exe on PATH as "yw" users can type in a terminal
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}')

[Run]
Filename: "{app}\yworkspace.exe"; Parameters: "setup"; Description: "Kurulum sihirbazını başlat / start the setup wizard"; Flags: postinstall nowait

[Code]
function NeedsAddPath(Param: string): boolean;
var OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then begin Result := True; exit; end;
  Result := Pos(';' + ExpandConstant(Param) + ';', ';' + OrigPath + ';') = 0;
end;
