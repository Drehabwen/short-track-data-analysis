#define AppName "SpeedTrack Pro"
#define AppVersion "1.1.0"
#define ReleaseDir "D:\DEV\blood\blood_reports_package_20260726-141357\release\SpeedTrackPro-CoachTrial-20260907"

[Setup]
AppId={{7F9F8A4B-2A75-4AA8-9F8F-6A3B9E0B7D51}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=SpeedTrack Pro
AppPublisherURL=https://localhost
DefaultDirName={localappdata}\Programs\SpeedTrackPro
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=D:\DEV\blood
OutputBaseFilename=SpeedTrackPro-Setup-20260907
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
Uninstallable=yes
ChangesAssociations=no
; 数据库由程序自身管理，安装/升级均不覆盖用户已录入的数据。

[Files]
Source: "{#ReleaseDir}\SpeedTrackPro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\blood.db"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall ignoreversion
Source: "{#ReleaseDir}\blood.db"; DestName: "SpeedTrackPro-data.db"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall ignoreversion
Source: "{#ReleaseDir}\README-教练试用.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\SpeedTrackPro-教练端使用手册.pdf"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\SpeedTrackPro-教练端使用手册.docx"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\启动教练端.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\停止教练端.bat"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\data\uploads"

[Icons]
Name: "{autodesktop}\SpeedTrack Pro"; Filename: "{app}\SpeedTrackPro.exe"; WorkingDir: "{app}"; Comment: "短道速滑训练监测·教练端"
Name: "{group}\SpeedTrack Pro"; Filename: "{app}\SpeedTrackPro.exe"; WorkingDir: "{app}"; Comment: "短道速滑训练监测·教练端"
Name: "{group}\使用手册"; Filename: "{app}\SpeedTrackPro-教练端使用手册.pdf"
Name: "{group}\卸载 SpeedTrack Pro"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\SpeedTrackPro.exe"; Description: "启动 SpeedTrack Pro 教练端"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{app}\data\uploads"
