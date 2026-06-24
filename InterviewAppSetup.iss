[Setup]
AppName=Interview App
AppVersion=1.0
DefaultDirName={pf}\InterviewApp
DefaultGroupName=Interview App
OutputDir=output
OutputBaseFilename=InterviewAppSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "C:\Users\myubd\Desktop\interview_app\dist\launch.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Interview App"; Filename: "{app}\launch.exe"
Name: "{commondesktop}\Interview App"; Filename: "{app}\launch.exe"

[Run]
Filename: "{app}\launch.exe"; Description: "Launch app"; Flags: nowait postinstall skipifsilent