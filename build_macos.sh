#!/bin/bash

echo "============================================"
echo "   Building Photo Uploader for macOS"
echo "============================================"
echo ""

echo "[1/4] Installing dependencies..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "[2/4] Installing PyInstaller..."
pip3 install pyinstaller
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install PyInstaller"
    exit 1
fi

echo ""
echo "[3/4] Building application..."
pyinstaller --onefile \
    --windowed \
    --name "PhotoUploader" \
    --hidden-import=cryptography \
    --hidden-import=dropbox \
    --hidden-import=requests \
    --osx-bundle-identifier "com.photouploader.app" \
    src/main.py

if [ $? -ne 0 ]; then
    echo "ERROR: Build failed"
    exit 1
fi

echo ""
echo "[4/4] Build complete!"
echo "============================================"
echo "   Application location: dist/PhotoUploader.app"
echo "============================================"
echo ""
echo "You can now distribute the PhotoUploader.app"
echo ""
echo "Note: First-time users may need to right-click"
echo "      and select 'Open' to bypass Gatekeeper"
echo ""