#!/bin/bash
# Script to pull the latest version of tg_downloader.py from GitHub
# This can be used as part of a scheduled task to ensure you always have the latest version

REPO_URL="https://raw.githubusercontent.com/idMdev/tg-downloader/main/tg_downloader.py"
SCRIPT_NAME="tg_downloader.py"
BACKUP_NAME="tg_downloader.py.backup"

echo "Telegram Downloader Auto-Update Script"
echo "========================================"

# Check if script exists and create backup
if [ -f "$SCRIPT_NAME" ]; then
    echo "Creating backup of existing script..."
    cp "$SCRIPT_NAME" "$BACKUP_NAME"
fi

# Download the latest version
echo "Downloading latest version from GitHub..."
if curl -sSL "$REPO_URL" -o "$SCRIPT_NAME"; then
    echo "✓ Successfully updated $SCRIPT_NAME"
    
    # Show version info if available
    if command -v python3 &> /dev/null; then
        echo ""
        echo "Script updated successfully!"
    fi
else
    echo "✗ Failed to download latest version"
    
    # Restore backup if download failed
    if [ -f "$BACKUP_NAME" ]; then
        echo "Restoring backup..."
        mv "$BACKUP_NAME" "$SCRIPT_NAME"
    fi
    exit 1
fi

echo ""
echo "You can now run: python3 $SCRIPT_NAME --channel @yourchannel"
