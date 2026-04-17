@echo off
setlocal

echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet

echo [2/3] Generating icon...
python -c "from killswitch import make_icon_image; make_icon_image().save('icon.ico')"
if errorlevel 1 (
    echo ERROR: Could not generate icon. Make sure killswitch.py is in this folder.
    pause
    exit /b 1
)

echo [3/3] Building KillSwitch.exe...
pyinstaller ^
    --onefile ^
    --windowed ^
    --icon=icon.ico ^
    --name=KillSwitch ^
    --add-data "icon.ico;." ^
    --version-file version.txt ^
    killswitch.py 2>nul || ^
pyinstaller ^
    --onefile ^
    --windowed ^
    --icon=icon.ico ^
    --name=KillSwitch ^
    killswitch.py

if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo Done! Executable is at: dist\KillSwitch.exe
echo.
echo To install: copy dist\KillSwitch.exe anywhere and run it.
echo It will auto-register itself to start with Windows on first launch.
echo.
pause
