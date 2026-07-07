; Inno Setup script — Smyshnikov Preset Downloader
; Requires PyInstaller output in desktop\dist\SmyshnikovPresetDownloader\

#define MyAppName "Smyshnikov ComfyUI Hub"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Smyshnikov"
#define MyAppURL "https://github.com/somb1/ComfyUI-Docker"
#define MyAppExeName "SmyshnikovHub.exe"

[Setup]
AppId={{A7B3C9D1-4E2F-4A8B-9C1D-2F3E4A5B6C7D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\SmyshnikovPresetDownloader
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=SmyshnikovComfyUIHub-setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\SmyshnikovComfyUIHub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\config.example.json"; DestDir: "{app}\desktop"; DestName: "config.json"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ComfyPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  ComfyPage := CreateInputDirPage(wpSelectDir,
    'Путь к ComfyUI', 'Укажите папку установки ComfyUI (с подпапкой models)',
    'Выберите корневую папку ComfyUI. Модели будут скачиваться в models\.',
    False, '');
  ComfyPage.Add('');
  ComfyPage.Values[0] := ExpandConstant('{userdocs}\ComfyUI');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, ConfigContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigPath := ExpandConstant('{app}\desktop\config.json');
    if FileExists(ConfigPath) then
    begin
      ConfigContent := '{' + #13#10 +
        '  "comfyui_path": "' + ComfyPage.Values[0] + '",' + #13#10 +
        '  "port": 8081,' + #13#10 +
        '  "host": "127.0.0.1",' + #13#10 +
        '  "open_browser": true' + #13#10 +
        '}';
      SaveStringToFile(ConfigPath, ConfigContent, False);
    end;
  end;
end;
