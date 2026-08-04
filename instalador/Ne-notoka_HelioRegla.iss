#define MyAppName "Ne-notoka HelioRegla"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "David Olivos S. / Ne-notoka Cofame"
#define MyAppExeName "Ne-notoka HelioRegla.exe"

[Setup]
AppId={{A6FBA926-9D12-48E2-A7EA-E450037C5C47}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion=1.2.0.0
VersionInfoCompany=Ne-notoka Cofame
VersionInfoDescription=Instalador de Ne-notoka HelioRegla
VersionInfoCopyright=Copyright (c) 2026 David Olivos S.
DefaultDirName={localappdata}\Programs\Ne-notoka HelioRegla
DefaultGroupName=Ne-notoka HelioRegla
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist_instalador
OutputBaseFilename=Ne-notoka_HelioRegla_1.2.0_Setup
SetupIconFile=..\assets\icono_ne_notoka.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=no
CloseApplications=yes
RestartApplications=no
UsePreviousLanguage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.CreateDesktopIcon=Crear un acceso directo en el escritorio
english.CreateDesktopIcon=Create a desktop shortcut
spanish.LaunchProgram=Abrir Ne-notoka HelioRegla
english.LaunchProgram=Launch Ne-notoka HelioRegla

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\Ne-notoka HelioRegla\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Ne-notoka HelioRegla"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userdesktop}\Ne-notoka HelioRegla"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram}"; Flags: nowait postinstall skipifsilent
