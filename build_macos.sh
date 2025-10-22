#!/bin/bash

echo "============================================"
echo "   Building SnapFlow for macOS"
echo "   (Optimized for security and distribution)"
echo "============================================"
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "ERROR: main.py not found. Please run this script from the project root."
    exit 1
fi

echo "[1/6] Installing dependencies..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "[2/6] Installing PyInstaller..."
pip3 install pyinstaller
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install PyInstaller"
    exit 1
fi

echo ""
echo "[3/6] Cleaning previous builds..."
rm -rf build dist *.spec

echo ""
echo "[4/6] Building application with optimized settings..."
pyinstaller --clean \
    --onefile \
    --windowed \
    --name "SnapFlow" \
    --icon=uploadericon.png \
    --hidden-import=cryptography \
    --hidden-import=cryptography.fernet \
    --hidden-import=dropbox \
    --hidden-import=requests \
    --hidden-import=urllib3 \
    --hidden-import=certifi \
    --exclude-module=pytest \
    --exclude-module=setuptools \
    --exclude-module=pip \
    --osx-bundle-identifier "com.snapflow.app" \
    main.py

if [ $? -ne 0 ]; then
    echo "ERROR: Build failed"
    exit 1
fi

echo ""
echo "[5/6] Setting permissions..."
chmod +x "dist/SnapFlow.app/Contents/MacOS/SnapFlow"

echo ""
echo "[6/6] Creating DMG installer..."

# Check if create-dmg is installed
if command -v create-dmg &> /dev/null; then
    echo "Creating DMG with create-dmg..."
    
    # Create DMG
    create-dmg \
        --volname "SnapFlow" \
        --volicon "uploadericon.png" \
        --background "_dmgbackground.png" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "SnapFlow.app" 175 190 \
        --hide-extension "SnapFlow.app" \
        --app-drop-link 425 190 \
        --format UDZO \
        "dist/SnapFlow.dmg" \
        "dist/SnapFlow.app"
    
    if [ $? -eq 0 ]; then
        echo "✓ DMG created successfully: dist/PhotoUploader.dmg"
    else
        echo "⚠ DMG creation had issues, but app bundle is available"
    fi
else
    echo "⚠ create-dmg not installed. Install with: brew install create-dmg"
    echo "  App bundle is available at: dist/PhotoUploader.app"
    echo ""
    echo "Alternative: Creating simple DMG with hdiutil..."
    
    # Fallback: Create a simple DMG without fancy background
    rm -rf dist/dmg_temp
    mkdir -p dist/dmg_temp
    cp -R dist/SnapFlow.app dist/dmg_temp/
    ln -s /Applications dist/dmg_temp/Applications
    
    hdiutil create -volname "SnapFlow" \
        -srcfolder dist/dmg_temp \
        -ov -format UDZO \
        dist/SnapFlow.dmg
    
    rm -rf dist/dmg_temp
    
    if [ $? -eq 0 ]; then
        echo "✓ Simple DMG created: dist/PhotoUploader.dmg"
    fi
fi

echo ""
echo "============================================"
echo "   BUILD COMPLETE!"
echo "============================================"
echo ""
echo "📦 Outputs:"
echo "   - App Bundle: dist/SnapFlow.app"
if [ -f "dist/SnapFlow.dmg" ]; then
    echo "   - DMG Installer: dist/SnapFlow.dmg"
fi
echo ""
echo "🧪 Testing locally:"
echo "   open dist/SnapFlow.app"
echo ""
echo "📤 Distribution options:"
echo ""
echo "1. RECOMMENDED: Distribute the DMG file"
echo "   - Users drag app to Applications folder"
echo "   - First run: Right-click → Open (bypasses Gatekeeper)"
echo ""
echo "2. For development/testing: Use the .app bundle directly"
echo ""
echo "🔐 For production distribution:"
echo ""
echo "A. Code sign (requires Apple Developer account - \$99/year):"
echo "   codesign --deep --force --verify --verbose \\"
echo "     --sign \"Developer ID Application: Your Name\" \\"
echo "     --options runtime \\"
echo "     dist/SnapFlow.app"
echo ""
echo "B. Notarize with Apple (after code signing):"
echo "   xcrun notarytool submit dist/SnapFlow.dmg \\"
echo "     --apple-id your@email.com \\"
echo "     --team-id YOUR_TEAM_ID \\"
echo "     --wait"
echo ""
echo "   Then staple the notarization:"
echo "   xcrun stapler staple dist/SnapFlow.dmg"
echo ""
echo "Without code signing, users will see a warning and must:"
echo "   Right-click → Open → Open (first time only)"
echo ""
