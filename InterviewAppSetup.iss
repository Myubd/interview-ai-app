[Setup]
AppName=Interview App
AppVersion={#APP_VERSION}
DefaultDirName={pf}\InterviewApp
OutputDir=output
OutputBaseFilename=InterviewAppSetup
Compression=lzma
SolidCompression=yes
SetupIconFile=app.ico

[Files]
Source: "dist\launch.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Interview App"; Filename: "{app}\launch.exe"; IconFilename: "{app}\app.ico"
Name: "{commondesktop}\Interview App"; Filename: "{app}\launch.exe"; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\launch.exe"; Flags: nowait postinstall skipifsilent
