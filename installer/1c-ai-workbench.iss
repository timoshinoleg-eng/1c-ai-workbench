#define AppName "1C AI Workbench"
#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "0.1.0"
#endif
#define AppVersionNumeric GetEnv("APP_VERSION_NUMERIC")
#if AppVersionNumeric == ""
  #define AppVersionNumeric "0.1.0.0"
#endif
#define SourceRoot GetEnv("WORKBENCH_ROOT")
#if SourceRoot == ""
  #define SourceRoot ".."
#endif
#define OutputRoot GetEnv("INSTALLER_OUTPUT_DIR")
#if OutputRoot == ""
  #define OutputRoot "..\dist\installer"
#endif

[Setup]
AppId={{8F3E09B8-5D2F-4B98-8EA4-1C0A1F0B1C01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=1C AI Workbench
DefaultDirName={localappdata}\1c-ai-workbench
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
OutputDir={#OutputRoot}
OutputBaseFilename=1c-ai-workbench-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupLogging=yes
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersionNumeric}
VersionInfoCompany=1C AI Workbench
VersionInfoDescription=Local read-only AI workbench for 1C configuration analysis
VersionInfoProductName={#AppName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceRoot}\.gitignore"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\AI_RULES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\AUTHORS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\CODE_OF_CONDUCT.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\opencode.jsonc"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\SECURITY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\START_HERE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\START_HERE.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\installer\1c-ai-workbench.iss"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#SourceRoot}\configs\*"; DestDir: "{app}\configs"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,.env.*,*.env,*.db,*.sqlite,*.sqlite3,__pycache__,*.pyc,*.log,tmp_*,dist,generated,logs,.opencode,.qoder,.codegraph,.agents,.claude"
Source: "{#SourceRoot}\demo-answers\*"; DestDir: "{app}\demo-answers"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,.env.*,*.env,*.db,*.sqlite,*.sqlite3,__pycache__,*.pyc,*.log,tmp_*,dist,generated,logs"
Source: "{#SourceRoot}\demo-questions\*"; DestDir: "{app}\demo-questions"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,.env.*,*.env,*.db,*.sqlite,*.sqlite3,__pycache__,*.pyc,*.log,tmp_*,dist,generated,logs"
Source: "{#SourceRoot}\demo-showcase\*"; DestDir: "{app}\demo-showcase"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,.env.*,*.env,*.db,*.sqlite,*.sqlite3,__pycache__,*.pyc,*.log,tmp_*,dist,generated,logs"
Source: "{#SourceRoot}\docs\*"; DestDir: "{app}\docs"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,.env.*,*.env,*.db,*.sqlite,*.sqlite3,__pycache__,*.pyc,*.log,*.log.err,tmp_*,dist,generated,logs"
Source: "{#SourceRoot}\prompts\*"; DestDir: "{app}\prompts"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,.env.*,*.env,*.db,*.sqlite,*.sqlite3,__pycache__,*.pyc,*.log,tmp_*,dist,generated,logs"
Source: "{#SourceRoot}\rules\*"; DestDir: "{app}\rules"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,.env.*,*.env,*.db,*.sqlite,*.sqlite3,__pycache__,*.pyc,*.log,tmp_*,dist,generated,logs"
Source: "{#SourceRoot}\scripts\*"; DestDir: "{app}\scripts"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,.env.*,*.env,*.db,*.sqlite,*.sqlite3,__pycache__,*.pyc,*.log,tmp_*,dist,generated,logs,test_*.ps1"
Source: "{#SourceRoot}\tools\code-index-mcp\target\release\bsl-indexer.exe"; DestDir: "{app}\tools\code-index-mcp\target\release"; Flags: ignoreversion
Source: "{#SourceRoot}\tools\ibcmd-bridge\*"; DestDir: "{app}\tools\ibcmd-bridge"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,*.env,*.db,__pycache__,*.pyc,*.log,tmp_*,.venv"
Source: "{#SourceRoot}\tools\prompt-gallery\*"; DestDir: "{app}\tools\prompt-gallery"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,*.env,*.db,__pycache__,*.pyc,*.log,tmp_*,.venv"
Source: "{#SourceRoot}\tools\help-index-mcp\*"; DestDir: "{app}\tools\help-index-mcp"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,*.env,*.db,__pycache__,*.pyc,*.log,tmp_*,.venv"
Source: "{#SourceRoot}\tools\skills-bridge\*"; DestDir: "{app}\tools\skills-bridge"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: ".git,.env,*.env,*.db,__pycache__,*.pyc,*.log,tmp_*,.venv"
Source: "{#SourceRoot}\tools\cc-1c-skills\.claude\skills\cf-info\*"; DestDir: "{app}\tools\cc-1c-skills\.claude\skills\cf-info"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourceRoot}\tools\cc-1c-skills\.claude\skills\cfe-diff\*"; DestDir: "{app}\tools\cc-1c-skills\.claude\skills\cfe-diff"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourceRoot}\tools\cc-1c-skills\.claude\skills\form-validate\*"; DestDir: "{app}\tools\cc-1c-skills\.claude\skills\form-validate"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourceRoot}\tools\cc-1c-skills\.claude\skills\meta-validate\*"; DestDir: "{app}\tools\cc-1c-skills\.claude\skills\meta-validate"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourceRoot}\tools\cc-1c-skills\.claude\skills\mxl-info\*"; DestDir: "{app}\tools\cc-1c-skills\.claude\skills\mxl-info"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourceRoot}\tools\cc-1c-skills\.claude\skills\subsystem-info\*"; DestDir: "{app}\tools\cc-1c-skills\.claude\skills\subsystem-info"; Flags: recursesubdirs createallsubdirs ignoreversion

[Dirs]
Name: "{app}\generated"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Icons]
Name: "{group}\1C AI Workbench"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\START_HERE.ps1"" -WorkbenchRoot ""{app}"""; WorkingDir: "{app}"
Name: "{group}\Open Workbench Folder"; Filename: "{app}"
Name: "{group}\Uninstall 1C AI Workbench"; Filename: "{uninstallexe}"
Name: "{autodesktop}\1C AI Workbench"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\START_HERE.ps1"" -WorkbenchRoot ""{app}"""; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\START_HERE.ps1"" -WorkbenchRoot ""{app}"""; WorkingDir: "{app}"; Description: "Launch 1C AI Workbench"; Flags: postinstall nowait skipifsilent unchecked
