[Setup]
AppName=Interview App (React+FastAPI)
AppVersion={#APP_VERSION}
DefaultDirName={pf}\InterviewAppFastAPI
OutputDir=output
OutputBaseFilename=InterviewAppSetupFastAPI
Compression=lzma
SolidCompression=yes
SetupIconFile={srcdir}\..\..\streamlit\app.ico

[Files]
Source: "dist\launch_fastapi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Interview App (React+FastAPI)"; Filename: "{app}\launch_fastapi.exe"; IconFilename: "{app}\app.ico"
Name: "{commondesktop}\Interview App (React+FastAPI)"; Filename: "{app}\launch_fastapi.exe"; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\launch_fastapi.exe"; Description: "Interview App (React+FastAPI) を起動する"; Flags: postinstall nowait skipifsilent shellexec
