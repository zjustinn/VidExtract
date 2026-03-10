#define MyAppName "VidExtract"
#define MyAppVersion "1.0"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={pf}\VidExtract
DefaultGroupName=VidExtract
OutputBaseFilename=VidExtract_setup
Compression=lzma
SolidCompression=yes
SetupIconFile="..\vidextract.ico"

[Files]

Source: "..\dist\main.exe"; DestDir: "{app}"

Source: "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"; \
DestName: "yt-dlp.exe"; \
DestDir: "{app}"; \
ExternalSize: 5000000; \
Flags: external download ignoreversion

Source: "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"; \
DestName: "ffmpeg.zip"; \
DestDir: "{tmp}"; \
ExternalSize: 100000000; \
Flags: external download ignoreversion

[Run]
Filename: "powershell"; Parameters: "-Command Expand-Archive -Force '{tmp}\ffmpeg.zip' '{app}\ffmpeg'"; Flags: runhidden

[Icons]
Name: "{group}\VidExtract"; Filename: "{app}\main.exe"
Name: "{commondesktop}\VidExtract"; Filename: "{app}\main.exe"