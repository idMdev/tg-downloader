#!/bin/bash
# Example runner script for scheduled execution
# This script updates the downloader and runs it with your preferred settings

# Navigate to script directory
cd "$(dirname "$0")"

# Pull latest version from GitHub
echo "Updating to latest version..."
./update_script.sh

# Check if update was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "Running downloader..."
    
    # Run the downloader with your settings
    # Modify the parameters below according to your needs
    
    python3 tg_downloader.py \
        --channel @yourchannel \
        --types pdf,jpg,png,mp4 \
        --dest ./downloads \
        --max-size 100 \
        --limit 100
    
    # Optional: Add notification or logging
    if [ $? -eq 0 ]; then
        echo "✓ Download completed successfully at $(date)"
    else
        echo "✗ Download failed at $(date)"
        exit 1
    fi
else
    echo "✗ Update failed. Skipping download."
    exit 1
fi
