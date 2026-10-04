; Installer of the HYPER-OCR desktop app (Inno Setup 6). Built by tools/build_desktop.py --installer:
;   ISCC /DAppVersion=1.3.0 /DSourceDir=dist\HYPER-OCR /DOutputDir=dist packaging\windows\HYPER-OCR.iss
;
; It installs for the current user, in %LOCALAPPDATA%\Programs\HYPER-OCR: no administrator rights,
; and the app can update itself and add languages. (IT can install for all users with /ALLUSERS.)
; The app's Update button runs a newer installer with /SILENT /CLOSEAPPLICATIONS: it closes the
; app, replaces it and opens the new version.

#ifndef AppVersion
  #error Pass the version: /DAppVersion=x.y.z
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\HYPER-OCR"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{6F1C2A57-3B4E-4D2B-9C1A-8E5F0B7D9A31}
AppName=HYPER-OCR
AppVersion={#AppVersion}
AppVerName=HYPER-OCR {#AppVersion}
AppPublisher=HYPER-OCR
AppPublisherURL=https://github.com/omar-184/HYPER-OCR
AppSupportURL=https://github.com/omar-184/HYPER-OCR/issues
AppUpdatesURL=https://github.com/omar-184/HYPER-OCR/releases
DefaultDirName={autopf}\HYPER-OCR
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
OutputDir={#OutputDir}
OutputBaseFilename=HYPER-OCR-Setup-{#AppVersion}
SetupIconFile=HYPER-OCR.ico
UninstallDisplayIcon={app}\HYPER-OCR.exe
UninstallDisplayName=HYPER-OCR
VersionInfoVersion={#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#if FileExists(CompilerPath + "Languages\Arabic.isl")
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; A clean copy of the program each time. Languages added in {app}\tessdata stay.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\tesseract"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\HYPER-OCR"; Filename: "{app}\HYPER-OCR.exe"
Name: "{autodesktop}\HYPER-OCR"; Filename: "{app}\HYPER-OCR.exe"; Tasks: desktopicon

[Run]
; Also after a silent update: the app opens again by itself.
Filename: "{app}\HYPER-OCR.exe"; Description: "{cm:LaunchProgram,HYPER-OCR}"; Flags: nowait postinstall
