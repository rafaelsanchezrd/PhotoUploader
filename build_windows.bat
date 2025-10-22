@echo off
echo ========================================
echo   Building SnapFlow for Windows
echo   (Optimized to reduce AV false positives)
echo ========================================
echo.

:: Check if src/main.py exists
if not exist src\main.py (
    echo ERROR: src\main.py not found!
    echo Make sure you're running this from the project root.
    pause
    exit /b 1
)

:: Install dependencies
echo [1/5] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [2/5] Installing PyInstaller...
pip install pyinstaller
if %errorlevel% neq 0 (
    echo ERROR: Failed to install PyInstaller
    pause
    exit /b 1
)

echo.
echo [3/5] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist SnapFlow.spec del SnapFlow.spec

echo.
echo [4/5] Building executable with optimized settings...
pyinstaller --clean ^
    --onefile ^
    --windowed ^
    --name "SnapFlow" ^
    --icon=uploadericon.png ^
    --add-data "src/config.py;." ^
    --add-data "src/dropbox_uploader.py;." ^
    --add-data "src/webhook_client.py;." ^
    --add-data "src/utils.py;." ^
    --hidden-import=tkinter ^
    --hidden-import=cryptography ^
    --hidden-import=cryptography.fernet ^
    --hidden-import=dropbox ^
    --hidden-import=requests ^
    --hidden-import=urllib3 ^
    --hidden-import=certifi ^
    --exclude-module=pytest ^
    --exclude-module=setuptools ^
    --exclude-module=pip ^
    --noupx ^
    --version-file=version_info.txt ^
    src/main.py

if %errorlevel% neq 0 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo [5/5] Calculating SHA256 hash...
certutil -hashfile dist\SnapFlow.exe SHA256 > dist\SnapFlow.exe.sha256.txt
if %errorlevel% equ 0 (
    echo Hash saved to dist\SnapFlow.exe.sha256.txt
)

echo.
echo ========================================
echo   BUILD COMPLETE!
echo ========================================
echo.
echo Output: dist\SnapFlow.exe
echo Hash:   dist\SnapFlow.exe.sha256.txt
echo Size:   
dir dist\SnapFlow.exe | find "SnapFlow.exe"
echo.
echo ========================================
echo   TESTING
echo ========================================
echo.
echo To test the application locally:
echo   dist\SnapFlow.exe
echo.
echo ========================================
echo   IMPORTANT - ANTIVIRUS WARNINGS
echo ========================================
echo.
echo Your antivirus MAY flag this executable as suspicious.
echo This is a FALSE POSITIVE (common with PyInstaller).
echo.
echo TO REDUCE FALSE POSITIVES:
echo.
echo 1. Upload to VirusTotal: https://www.virustotal.com/
echo.
echo 2. Submit false positive reports to:
echo    - Microsoft Defender: https://www.microsoft.com/wdsi/filesubmission
echo    - Norton: https://submit.norton.com/
echo.
echo 3. For production: Get a code signing certificate
echo    Cost: $100-400/year (eliminates most warnings)
echo.
echo 4. Users should:
echo    - Click "More info" -^> "Run anyway" in Windows Defender
echo    - Or temporarily disable antivirus during install
echo.
pause