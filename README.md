# Telegram Downloader

A smart Telegram channel file downloader that automatically downloads files from Telegram channels and tracks downloaded files to avoid duplicates. Perfect for running as a scheduled task on your local workstation.

## Features

- 🚀 **Automatic Updates**: Pull the latest script version from GitHub before each run
- 📁 **Smart Duplicate Detection**: Tracks downloaded files to avoid re-downloading
- 🎯 **File Type Filtering**: Download only specific file types (e.g., PDF, images, videos)
- 📏 **Size Filtering**: Limit downloads by maximum file size
- 🔍 **Keyword Filtering**: Filter files by keywords in filename or message text
- 🔒 **Secure Credentials**: Store API keys in GitHub Secrets or environment variables
- 📊 **Download History**: Maintains a JSON history of all downloaded files
- 🔄 **Scheduled Execution**: Can be run as a cron job or Windows Task Scheduler task
- ☁️ **GitHub Actions Support**: Optional cloud-based scheduled downloads

## Prerequisites

1. **Telegram API Credentials**
   - Go to https://my.telegram.org/auth
   - Log in with your phone number
   - Go to "API development tools"
   - Create an application to get your `api_id` and `api_hash`

2. **Python 3.7+** installed on your system

## Installation

### Quick Start (Linux/Mac)

```bash
# Clone the repository
git clone https://github.com/idMdev/tg-downloader.git
cd tg-downloader

# Install dependencies
pip install -r requirements.txt

# Create configuration file
cp config.example.json config.json
# Edit config.json with your credentials
```

### Quick Start (Windows)

```cmd
# Clone the repository
git clone https://github.com/idMdev/tg-downloader.git
cd tg-downloader

# Install dependencies
pip install -r requirements.txt

# Create configuration file
copy config.example.json config.json
# Edit config.json with your credentials
```

## Configuration

### Method 1: Configuration File (config.json)

Create a `config.json` file based on `config.example.json`:

```json
{
  "api_id": "YOUR_API_ID",
  "api_hash": "YOUR_API_HASH",
  "phone": "YOUR_PHONE_NUMBER",
  "channel": "CHANNEL_USERNAME_OR_ID",
  "download_path": "./downloads",
  "file_types": ["jpg", "png", "pdf", "mp4", "zip"],
  "max_file_size_mb": 100,
  "keywords": ["report", "document"]
}
```

**Configuration Options:**
- `keywords` (optional): Array of keywords to filter files. Files will only be downloaded if their filename or the message text contains at least one of these keywords (case-insensitive). Leave empty or omit to download all files.

### Method 2: Environment Variables (Recommended for Security)

Set these environment variables:

```bash
export TG_API_ID="your_api_id"
export TG_API_HASH="your_api_hash"
export TG_PHONE="your_phone_number"
```

Environment variables take precedence over config file values.

## Usage

### Basic Usage

```bash
# Download from channel specified in config.json
python tg_downloader.py

# Download from a specific channel
python tg_downloader.py --channel @channelname

# Download specific file types
python tg_downloader.py --channel @channelname --types pdf,jpg,png

# Filter by keywords (searches filename and message text)
python tg_downloader.py --channel @channelname --keywords report,summary,document

# Specify custom download directory
python tg_downloader.py --channel @channelname --dest ./my_downloads

# Set maximum file size (in MB)
python tg_downloader.py --channel @channelname --max-size 50

# Check more messages (default is 100)
python tg_downloader.py --channel @channelname --limit 500

# Combine multiple filters
python tg_downloader.py --channel @channelname --types pdf --keywords report,annual --max-size 20
```

### Auto-Update from GitHub

Before running the downloader, pull the latest version:

**Linux/Mac:**
```bash
./update_script.sh
python tg_downloader.py --channel @channelname
```

**Windows:**
```cmd
update_script.bat
python tg_downloader.py --channel @channelname
```

## Scheduled Execution

### Linux/Mac (Cron)

Add to your crontab (`crontab -e`):

```bash
# Run every 6 hours
0 */6 * * * cd /path/to/tg-downloader && ./update_script.sh && python3 tg_downloader.py --channel @yourchannel

# Run daily at 2 AM
0 2 * * * cd /path/to/tg-downloader && ./update_script.sh && python3 tg_downloader.py --channel @yourchannel
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create a new task
3. Set the trigger (e.g., daily, every 6 hours)
4. Add two actions in sequence:
   - Action 1: Run `update_script.bat`
   - Action 2: Run `python tg_downloader.py --channel @yourchannel`

### Example Batch Script for Windows (run_downloader.bat)

```batch
@echo off
cd /d %~dp0
call update_script.bat
python tg_downloader.py --channel @yourchannel --types pdf,jpg --dest C:\Downloads\Telegram
```

## GitHub Actions (Cloud Scheduling)

You can run the downloader in GitHub Actions (cloud-based) instead of locally.

### Setup GitHub Secrets

1. Go to your repository on GitHub
2. Navigate to Settings → Secrets and variables → Actions
3. Add the following secrets:
   - `TG_API_ID`: Your Telegram API ID
   - `TG_API_HASH`: Your Telegram API hash
   - `TG_PHONE`: Your phone number
   - `TG_CHANNEL`: Default channel to download from (optional)

### Manual Trigger

1. Go to Actions tab in your repository
2. Select "Telegram Downloader - Scheduled Run"
3. Click "Run workflow"
4. Enter the channel name and options
5. Downloaded files will be available as artifacts

### Automatic Schedule

Edit `.github/workflows/download.yml` and uncomment the schedule section:

```yaml
schedule:
  - cron: '0 */6 * * *'  # Run every 6 hours
```

## How It Works

1. **First Run**: 
   - Connects to Telegram using your credentials
   - Creates a session file for future authentication
   - Downloads files from the specified channel
   - Saves message IDs to `download_history.json`

2. **Subsequent Runs**:
   - Checks `download_history.json` for previously downloaded files
   - Only downloads new files (skips duplicates)
   - Updates the history file

3. **File Tracking**:
   - Each message ID is tracked, not filenames
   - Even if a file is deleted locally, it won't be re-downloaded
   - To force re-download, delete or edit `download_history.json`

## File Structure

```
tg-downloader/
├── tg_downloader.py          # Main script
├── requirements.txt           # Python dependencies
├── config.example.json        # Configuration template
├── config.json               # Your configuration (not tracked in git)
├── update_script.sh          # Auto-update script (Linux/Mac)
├── update_script.bat         # Auto-update script (Windows)
├── download_history.json     # Downloaded files tracking (auto-generated)
├── downloads/                # Default download directory (not tracked in git)
└── .github/
    └── workflows/
        └── download.yml      # GitHub Actions workflow
```

## Troubleshooting

### "Error: Required packages not installed"
```bash
pip install -r requirements.txt
```

### "Error: Missing required credentials"
- Ensure `config.json` has valid `api_id`, `api_hash`, and `phone`
- Or set environment variables `TG_API_ID`, `TG_API_HASH`, `TG_PHONE`

### "Error accessing channel"
- Make sure you're a member of the channel
- Verify the channel username starts with `@` or use the numeric channel ID
- For private channels, ensure you have access

### "Phone number verification required"
- On first run, you'll receive a code on Telegram
- Enter the code when prompted
- A session file will be created for future runs

### Clear download history to re-download files
```bash
rm download_history.json
```

## Security Best Practices

1. **Never commit credentials** to git
   - `config.json` is already in `.gitignore`
   - Use environment variables for sensitive data

2. **Use GitHub Secrets** for Actions workflows
   - Store `TG_API_ID`, `TG_API_HASH`, `TG_PHONE` as secrets
   - Never hardcode credentials in workflow files

3. **Protect session files**
   - Session files contain authentication tokens
   - They're excluded by `.gitignore`
   - Don't share them publicly

## Advanced Usage

### Download from multiple channels

Create a wrapper script:

```bash
#!/bin/bash
python tg_downloader.py --channel @channel1 --types pdf --dest ./downloads/channel1
python tg_downloader.py --channel @channel2 --types jpg,png --dest ./downloads/channel2
python tg_downloader.py --channel @channel3 --dest ./downloads/channel3
```

### Filter by file type and size

```bash
# Only PDFs under 10MB
python tg_downloader.py --channel @docs --types pdf --max-size 10

# Only images
python tg_downloader.py --channel @photos --types jpg,png,jpeg,gif

# Only videos under 100MB
python tg_downloader.py --channel @videos --types mp4,mkv,avi --max-size 100
```

### Filter by keywords

```bash
# Download files containing "invoice" or "receipt" in filename or message text
python tg_downloader.py --channel @business --keywords invoice,receipt

# Download reports (case-insensitive matching)
python tg_downloader.py --channel @reports --keywords report,quarterly,annual

# Combine keyword and type filters
python tg_downloader.py --channel @docs --types pdf --keywords important,urgent
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is provided as-is for personal use. Make sure to comply with Telegram's Terms of Service when using this tool.

## Disclaimer

This tool is for personal use only. Ensure you have the right to download content from the channels you access. Respect copyright and content ownership.