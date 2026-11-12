[Setup]
AppId={{A3B8C9D0-1234-5678-9ABC-DEF012345678}
AppName=AncaScanner Pro
AppVersion=1.0
AppPublisher=Ancamedica S.A.
DefaultDirName={autopf}\AncaScanner Pro
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=AncaScannerPro_Setup
SetupIconFile=logo.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copia todos los archivos de tu compilación (ej. carpeta o archivos sueltos)
Source: "dist\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; ¡Importante! Añade esta línea para que logo.ico se copie a la carpeta raíz de instalación
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\AncaScanner Pro"; Filename: "{app}\AncaScannerPro.exe"; IconFilename: "{app}\logo.ico"
Name: "{autodesktop}\AncaScanner Pro"; Filename: "{app}\AncaScannerPro.exe"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\AncaScannerPro.exe"; Description: "{cm:LaunchProgram,AncaScanner Pro}"; Flags: nowait postinstall skipifsilent