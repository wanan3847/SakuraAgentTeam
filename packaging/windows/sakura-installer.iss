; 🌸 樱花小队 — Inno Setup 安装脚本
;
; 用法: 用 Inno Setup Compiler 打开此文件并编译
; 下载: https://jrsoftware.org/isdl.php
;
; 编译前请先运行 build.ps1 生成 dist/SakuraAgentTeam/ 目录

#define MyAppName "SakuraAgentTeam"
#define MyAppDisplayName "樱花小队"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "wanan3847"
#define MyAppURL "https://github.com/wanan3847/SakuraAgentTeam"
#define MyAppExeName "sakura-launch.bat"

[Setup]
AppId={{B7F3A2E1-5C8D-4A6F-9E2B-1D3C4E5F6A7B}
AppName={#MyAppDisplayName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppDisplayName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppDisplayName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=sakura-agent-team-0.2.0-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\sakura-backend.exe

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: checked

[Files]
Source: "dist\SakuraAgentTeam\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\sakura-backend.exe"
Name: "{group}\卸载 {#MyAppDisplayName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\sakura-backend.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppDisplayName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 停止可能运行中的后端进程
Filename: "{cmd}"; Parameters: "/c taskkill /f /im sakura-backend.exe"; Flags: runhidden; RunOnceId: "KillBackend"
