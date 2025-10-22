#!/bin/bash

echo "============================================"
echo "   Building Photo Uploader for macOS"
echo "   Universal Binary (Intel + ARM)"
echo "============================================"
echo ""

# Detect current architecture
CURRENT_ARCH=$(uname -m)
echo "Current architecture: $CURRENT_ARCH"
echo ""

# Check if running on Apple Silicon
if [[ "$CURRENT_ARCH" == "arm64" ]]; then
    echo "✓ Running on Apple Silicon (M1/M2/M3)"
    IS_ARM=true
else
    echo "✓ Running on Intel Mac"
    IS_ARM=false
fi

echo ""
echo "[1/5] Installing dependencies..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "[2/5] Installing PyInstaller..."
pip3 install pyinstaller
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install PyInstaller"
    exit 1
fi

echo ""
echo "[3/5] Building for current architecture ($CURRENT_ARCH)..."
pyinstaller --onefile \
    --windowed \
    --name "PhotoUploader" \
    --hidden-import=cryptography \
    --hidden-import=dropbox \
    --hidden-import=requests \
    --hidden-import=PIL \
    --hidden-import=PIL.Image \
    --hidden-import=PIL.ImageTk \
    --hidden-import=PIL.ImageEnhance \
    --osx-bundle-identifier "com.photouploader.app" \
    --icon uploadericon.png \
    src/main.py

if [ $? -ne 0 ]; then
    echo "ERROR: Build failed"
    exit 1
fi

# Rename the build for current architecture
mv dist/PhotoUploader.app "dist/PhotoUploader_${CURRENT_ARCH}.app"

echo ""
echo "[4/5] Creating Universal Binary instructions..."

# Create info file about building for both architectures
cat > dist/BUILD_UNIVERSAL.txt << 'HEREDOC'
╔══════════════════════════════════════════════════════════════╗
║           Building Universal Binary (Intel + ARM)            ║
╚══════════════════════════════════════════════════════════════╝

You have built for your current architecture. To create a truly
Universal Binary that works on BOTH Intel and Apple Silicon:

OPTION 1: Use GitHub Actions (Recommended)
─────────────────────────────────────────────
Build automatically on both architectures using CI/CD.
See: GITHUB_ACTIONS_BUILD.yml

OPTION 2: Build on Both Machines
─────────────────────────────────────────────
1. Build on Intel Mac → PhotoUploader_x86_64.app
2. Build on Apple Silicon Mac → PhotoUploader_arm64.app
3. Use 'lipo' to combine:
   
   lipo -create -output PhotoUploader_universal \
       PhotoUploader_x86_64.app/Contents/MacOS/PhotoUploader \
       PhotoUploader_arm64.app/Contents/MacOS/PhotoUploader

OPTION 3: Cross-Compile (Advanced)
─────────────────────────────────────────────
Use --target-arch flag in PyInstaller (requires setup)

CURRENT BUILD:
─────────────────────────────────────────────
Architecture: $(uname -m)
Location: dist/PhotoUploader_$(uname -m).app

This build will work on:
HEREDOC

if [[ "$CURRENT_ARCH" == "arm64" ]]; then
    echo "  ✓ Apple Silicon (M1/M2/M3) Macs" >> dist/BUILD_UNIVERSAL.txt
    echo "  ✗ Intel Macs (need separate build)" >> dist/BUILD_UNIVERSAL.txt
else
    echo "  ✓ Intel Macs" >> dist/BUILD_UNIVERSAL.txt
    echo "  ✗ Apple Silicon (need separate build)" >> dist/BUILD_UNIVERSAL.txt
fi

echo ""
echo "[5/5] Build complete!"
echo "============================================"
echo "   Application: dist/PhotoUploader_${CURRENT_ARCH}.app"
echo "============================================"
echo ""
echo "✓ Built for: $CURRENT_ARCH"
echo ""
if [[ "$CURRENT_ARCH" == "arm64" ]]; then
    echo "✓ This build works on: Apple Silicon (M1/M2/M3)"
    echo "⚠️  For Intel Macs: Build on an Intel Mac or use GitHub Actions"
else
    echo "✓ This build works on: Intel Macs"
    echo "⚠️  For Apple Silicon: Build on an M1/M2/M3 Mac or use GitHub Actions"
fi
echo ""
echo "📖 See dist/BUILD_UNIVERSAL.txt for Universal Binary instructions"
echo ""
echo "Note: First-time users may need to right-click"
echo "      and select 'Open' to bypass Gatekeeper"
echo ""
