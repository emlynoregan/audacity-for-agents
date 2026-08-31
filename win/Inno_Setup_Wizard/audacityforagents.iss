; Audacity for Agents — Inno Setup script (English)
; Sibling to stock Audacity; does NOT associate .aup3.

#define AppExe "Package\AudacityForAgents.exe"
#define AppMajor ""
#define AppMinor ""
#define AppRev ""
#define AppBuild ""
#define FullVersion ParseVersion(AppExe, AppMajor, AppMinor, AppRev, AppBuild)
#define AppVersion Str(AppMajor) + "." + Str(AppMinor) + "." + Str(AppRev)
#define AppName "Audacity for Agents"
; Product version for the download site (override via /DAgentsVersion=… on iscc)
#ifndef AgentsVersion
  #define AgentsVersion AppVersion + "-agents.1"
#endif

[Setup]
AppId={{A7F3C2E1-9B4D-4E8A-A1C0-5D6F8E9B0A2C}
AppName={#AppName}
AppVerName={#AppName} {#AgentsVersion}
AppVersion={#AgentsVersion}
AppPublisher="Emlyn O'Regan"
AppPublisherURL=https://github.com/emlynoregan/audacity-for-agents
AppSupportURL=https://github.com/emlynoregan/audacity-for-agents
AppUpdatesURL=https://github.com/emlynoregan/audacity-for-agents
DefaultDirName={localappdata}\Audacity for Agents
DefaultGroupName=Audacity for Agents
DisableProgramGroupPage=yes
LicenseFile=Additional\LICENSE.txt
OutputDir=Output
OutputBaseFilename=AudacityForAgents-Setup-{#AgentsVersion}-x64
SetupIconFile=Additional\audacity.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=no
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\AudacityForAgents.exe
InfoBeforeFile=audacityforagents_InfoBefore.rtf
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
VersionInfoVersion={#GetFileVersion(AppExe)}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addpath"; Description: "Add install folder to user PATH"; GroupDescription: "Agent discoverability:"; Flags: checkedonce
Name: "setenv"; Description: "Set AUDACITY_FOR_AGENTS_EXE user environment variable"; GroupDescription: "Agent discoverability:"; Flags: checkedonce

[Files]
Source: "Additional\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "Package\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Portable Settings next to the exe (isolated from stock Audacity %APPDATA%)
Name: "{app}\Portable Settings"; Permissions: users-modify

[Icons]
Name: "{group}\Audacity for Agents"; Filename: "{app}\AudacityForAgents.exe"; Parameters: "--batch"
Name: "{group}\Uninstall Audacity for Agents"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Audacity for Agents"; Filename: "{app}\AudacityForAgents.exe"; Parameters: "--batch"; Tasks: desktopicon

[Registry]
; User PATH append (optional task)
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};{app}"; Tasks: addpath; Check: NeedsAddPath(ExpandConstant('{app}'))
; Explicit exe path for the Python client
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "AUDACITY_FOR_AGENTS_EXE"; \
  ValueData: "{app}\AudacityForAgents.exe"; Tasks: setenv; Flags: uninsdeletevalue

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;
