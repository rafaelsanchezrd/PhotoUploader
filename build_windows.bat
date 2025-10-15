@echo off
echo ========================================
echo   Building Photo Uploader for Windows
echo ========================================
echo.

:: Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/3] Building executable...
pyinstaller --onefile ^
    --windowed ^
    --name "PhotoUploader" ^
    --add-data "src;src" ^
    --hidden-import="tkinter" ^
    --hidden-import="dropbox" ^
    --hidden-import="requests" ^
    --hidden-import="cryptography" ^
    src/main.py

echo.
echo [3/3] Cleaning up...
:: Optional: Remove build artifacts
:: rmdir /s /q build
:: del PhotoUploader.spec

echo.
echo ========================================
echo   BUILD COMPLETE!
echo ========================================
echo.
echo Executable location: dist\PhotoUploader.exe
echo.
echo You can now distribute dist\PhotoUploader.exe
echo to photographers. No Python installation needed!
echo.
pause