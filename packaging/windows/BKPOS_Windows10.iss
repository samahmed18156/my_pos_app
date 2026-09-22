#define MyAppName "BKPOS"
#define MyAppVersion "10.0.0"
#define MyAppPublisher "BKPOS"
#define MyAppExeName "BKPOS.exe"

[Setup]
AppId={{A3B2C1D0-6F54-4E21-9A87-100000000001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\BKPOS
DefaultGroupName=BKPOS
PrivilegesRequired=lowest
ArchitecturesAllowed=x86 x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=BKPOS_Setup_Windows10
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\BKPOS.exe
UninstallDisplayName=BKPOS
CloseApplications=yes
RestartApplications=no
AllowNoIcons=no
MinVersion=10.0

[Files]
Source: "..\..\dist\BKPOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a BKPOS desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Icons]
Name: "{autodesktop}\BKPOS"; Filename: "{app}\BKPOS.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\BKPOS"; Filename: "{app}\BKPOS.exe"; WorkingDir: "{app}"
Name: "{group}\BKPOS Data Folder"; Filename: "{userappdata}\BKPOS"; WorkingDir: "{userappdata}\BKPOS"; IconFilename: "{app}\BKPOS.exe"
Name: "{group}\Uninstall BKPOS"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\BKPOS.exe"; Description: "Launch BKPOS"; Flags: nowait postinstall skipifsilent
