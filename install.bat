@echo off
setlocal

set "EXE=%~dp0dist\KillSwitch.exe"

if not exist "%EXE%" (
    echo ERROR: KillSwitch.exe not found at:
    echo   %EXE%
    echo Run build.bat first to compile the executable.
    pause
    exit /b 1
)

echo Registering KillSwitch to start with Windows...
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" ^
    /v "KillSwitch" /t REG_SZ /d "\"%EXE%\"" /f >nul

if errorlevel 1 (
    echo ERROR: Failed to add registry entry.
    pause
    exit /b 1
)

echo Done! KillSwitch will now start automatically with Windows.

echo Creating desktop shortcut...
set "SHORTCUT=%USERPROFILE%\Desktop\KillSwitch.lnk"
set "ICON=%~dp0icon.ico"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%EXE%'; $s.IconLocation = '%ICON%'; $s.Description = 'KillSwitch - Kill messaging and screen-sharing apps'; $s.Save()"

if errorlevel 1 (
    echo WARNING: Could not create desktop shortcut.
) else (
    echo Desktop shortcut created.
)

echo.
echo Starting KillSwitch now...
start "" "%EXE%"
