#!/usr/bin/env python3
"""
Telegram Channel File Downloader

This script downloads files from a Telegram channel and tracks downloaded files
to avoid duplicates. It supports filtering by file type, size, and keywords.
"""

import os
import sys
import json
import argparse
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Set, Optional

try:
    from telethon import TelegramClient
    from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
except ImportError:
    print("Error: Required packages not installed.")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)


class TelegramDownloader:
    """Main class for downloading files from Telegram channels"""
    
    def __init__(self, api_id: str, api_hash: str, phone: str, 
                 download_path: str = "./downloads",
                 history_file: str = "download_history.json",
                 keywords: Optional[List[str]] = None):
        """
        Initialize the Telegram downloader
        
        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            phone: Phone number associated with Telegram account
            download_path: Directory to save downloaded files
            history_file: JSON file to track downloaded files
            keywords: List of keywords to filter files (case-insensitive)
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.download_path = Path(download_path)
        self.history_file = Path(history_file)
        self.downloaded_files: Set[int] = set()
        self.client = None
        self.keywords = [k.lower() for k in keywords] if keywords else None
        
        # Create download directory if it doesn't exist
        self.download_path.mkdir(parents=True, exist_ok=True)
        
        # Load download history
        self._load_history()
    
    def _load_history(self):
        """Load the history of downloaded files"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.downloaded_files = set(data.get('downloaded_ids', []))
                    print(f"Loaded {len(self.downloaded_files)} previously downloaded file IDs")
            except Exception as e:
                print(f"Warning: Could not load history file: {e}")
                self.downloaded_files = set()
        else:
            print("No download history found. Starting fresh.")
    
    def _save_history(self):
        """Save the history of downloaded files"""
        try:
            data = {
                'downloaded_ids': list(self.downloaded_files),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save history file: {e}")
    
    def _is_allowed_file(self, filename: str, allowed_types: Optional[List[str]]) -> bool:
        """
        Check if file type is allowed
        
        Args:
            filename: Name of the file
            allowed_types: List of allowed file extensions (e.g., ['jpg', 'pdf'])
        
        Returns:
            True if file is allowed or no filter specified, False otherwise
        """
        if not allowed_types:
            return True
        
        ext = Path(filename).suffix.lower().lstrip('.')
        return ext in [t.lower().lstrip('.') for t in allowed_types]
    
    def _is_size_allowed(self, size_bytes: int, max_size_mb: Optional[float]) -> bool:
        """
        Check if file size is within allowed limit
        
        Args:
            size_bytes: File size in bytes
            max_size_mb: Maximum allowed file size in MB
        
        Returns:
            True if file size is allowed or no limit specified, False otherwise
        """
        if max_size_mb is None:
            return True
        
        size_mb = size_bytes / (1024 * 1024)
        return size_mb <= max_size_mb
    
    def _matches_keyword(self, filename: str, message_text: Optional[str]) -> bool:
        """
        Check if filename or message text contains any of the specified keywords
        
        Args:
            filename: Name of the file
            message_text: Text description from the message
        
        Returns:
            True if any keyword matches or no keywords specified, False otherwise
        """
        if not self.keywords:
            return True
        
        # Combine filename and message text for searching (case-insensitive)
        search_text = filename.lower()
        if message_text:
            search_text += " " + message_text.lower()
        
        # Check if any keyword is found in the combined text
        return any(keyword in search_text for keyword in self.keywords)
    
    def _sanitize_filename(self, text: str, extension: str, max_length: int = 150) -> str:
        """
        Convert message text to a safe filename
        
        Args:
            text: Message text to convert to filename
            extension: File extension (including dot, e.g., '.pdf')
            max_length: Maximum filename length (default: 150)
        
        Returns:
            Sanitized filename with extension
        """
        if not text or not text.strip():
            return None
        
        # Replace newlines with spaces and strip whitespace
        text = text.replace('\n', ' ').replace('\r', ' ').strip()
        
        # Remove or replace characters that are invalid in filenames
        # Invalid chars: / \ : * ? " < > |
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            text = text.replace(char, '_')
        
        # Replace multiple spaces with single space
        while '  ' in text:
            text = text.replace('  ', ' ')
        
        # Trim to max length (accounting for extension)
        max_text_length = max_length - len(extension)
        if len(text) > max_text_length:
            text = text[:max_text_length].strip()
        
        # Add extension
        filename = text + extension
        
        return filename
    
    async def connect(self):
        """Connect to Telegram"""
        session_name = f"session_{self.phone}"
        self.client = TelegramClient(session_name, self.api_id, self.api_hash)
        
        print("Connecting to Telegram...")
        await self.client.start(phone=self.phone)
        print("Connected successfully!")
    
    async def download_from_channel(self, channel: str, 
                                    file_types: Optional[List[str]] = None,
                                    max_size_mb: Optional[float] = None,
                                    limit: int = 100):
        """
        Download files from a Telegram channel
        
        Args:
            channel: Channel username or ID
            file_types: List of allowed file extensions (e.g., ['jpg', 'pdf'])
            max_size_mb: Maximum file size in MB
            limit: Maximum number of messages to check
        """
        if not self.client:
            await self.connect()
        
        print(f"\nFetching messages from channel: {channel}")
        print(f"File types filter: {file_types if file_types else 'All'}")
        print(f"Max file size: {max_size_mb if max_size_mb else 'No limit'} MB")
        print(f"Keywords filter: {self.keywords if self.keywords else 'None'}")
        print(f"Checking last {limit} messages...\n")
        
        downloaded_count = 0
        skipped_count = 0
        
        try:
            # Get channel entity
            entity = await self.client.get_entity(channel)
            
            # Iterate through messages
            async for message in self.client.iter_messages(entity, limit=limit):
                # Skip if message has no media
                if not message.media:
                    continue
                
                # Skip if already downloaded
                if message.id in self.downloaded_files:
                    skipped_count += 1
                    continue
                
                # Handle documents (files)
                if isinstance(message.media, MessageMediaDocument):
                    doc = message.media.document
                    filename = None
                    original_filename = None
                    
                    # Get original filename from attributes
                    for attr in doc.attributes:
                        if hasattr(attr, 'file_name'):
                            original_filename = attr.file_name
                            break
                    
                    # Try to use message text as filename
                    if message.text:
                        # Get extension from original filename or mime type
                        if original_filename:
                            ext = Path(original_filename).suffix
                        else:
                            ext_name = doc.mime_type.split('/')[-1] if doc.mime_type else 'bin'
                            ext = f".{ext_name}"
                        
                        # Create filename from message text
                        filename = self._sanitize_filename(message.text, ext)
                    
                    # Fall back to original filename or generated name
                    if not filename:
                        if original_filename:
                            filename = original_filename
                        else:
                            ext = doc.mime_type.split('/')[-1] if doc.mime_type else 'bin'
                            filename = f"file_{message.id}.{ext}"
                    
                    # Check file type filter
                    if not self._is_allowed_file(filename, file_types):
                        print(f"Skipping {filename} (file type not allowed)")
                        continue
                    
                    # Check file size filter
                    if not self._is_size_allowed(doc.size, max_size_mb):
                        size_mb = doc.size / (1024 * 1024)
                        print(f"Skipping {filename} (size {size_mb:.2f} MB exceeds limit)")
                        continue
                    
                    # Check keyword filter
                    if not self._matches_keyword(filename, message.text):
                        print(f"Skipping {filename} (does not match keyword filter)")
                        continue
                    
                    # Download the file
                    print(f"Downloading: {filename} ({doc.size / (1024 * 1024):.2f} MB)")
                    file_path = self.download_path / filename
                    
                    try:
                        await message.download_media(file=str(file_path))
                        self.downloaded_files.add(message.id)
                        downloaded_count += 1
                        print(f"✓ Downloaded: {filename}")
                    except Exception as e:
                        print(f"✗ Error downloading {filename}: {e}")
                
                # Handle photos
                elif isinstance(message.media, MessageMediaPhoto):
                    # Try to use message text as filename
                    if message.text:
                        filename = self._sanitize_filename(message.text, '.jpg')
                    
                    # Fall back to default photo naming
                    if not filename:
                        filename = f"photo_{message.id}.jpg"
                    
                    # Check file type filter
                    if not self._is_allowed_file(filename, file_types):
                        print(f"Skipping {filename} (file type not allowed)")
                        continue
                    
                    # Check keyword filter
                    if not self._matches_keyword(filename, message.text):
                        print(f"Skipping {filename} (does not match keyword filter)")
                        continue
                    
                    # Download the photo
                    print(f"Downloading: {filename}")
                    file_path = self.download_path / filename
                    
                    try:
                        await message.download_media(file=str(file_path))
                        self.downloaded_files.add(message.id)
                        downloaded_count += 1
                        print(f"✓ Downloaded: {filename}")
                    except Exception as e:
                        print(f"✗ Error downloading {filename}: {e}")
            
            # Save history after downloading
            self._save_history()
            
            print(f"\n{'='*50}")
            print(f"Download Summary:")
            print(f"  New downloads: {downloaded_count}")
            print(f"  Previously downloaded (skipped): {skipped_count}")
            print(f"  Total tracked files: {len(self.downloaded_files)}")
            print(f"{'='*50}\n")
        
        except Exception as e:
            print(f"Error accessing channel: {e}")
            print("Make sure you have access to the channel and the channel name/ID is correct")
    
    async def disconnect(self):
        """Disconnect from Telegram"""
        if self.client:
            await self.client.disconnect()
            print("Disconnected from Telegram")


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        print("Please create a config.json file based on config.example.json")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {e}")
        sys.exit(1)


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Download files from a Telegram channel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download using config file
  python tg_downloader.py
  
  # Override channel from command line
  python tg_downloader.py --channel @mychannel
  
  # Specify file types and destination
  python tg_downloader.py --channel @mychannel --types pdf,jpg,png --dest ./my_downloads
  
  # Filter by keywords (searches filename and message text)
  python tg_downloader.py --channel @mychannel --keywords report,summary,document
  
  # Use environment variables for credentials (recommended)
  export TG_API_ID=your_api_id
  export TG_API_HASH=your_api_hash
  export TG_PHONE=your_phone
  python tg_downloader.py --channel @mychannel
        """
    )
    
    parser.add_argument('--config', default='config.json',
                       help='Path to config file (default: config.json)')
    parser.add_argument('--channel',
                       help='Channel username or ID (overrides config)')
    parser.add_argument('--types',
                       help='Comma-separated file types to download (e.g., pdf,jpg,png)')
    parser.add_argument('--keywords',
                       help='Comma-separated keywords to filter files (searches filename and message text)')
    parser.add_argument('--dest',
                       help='Download destination directory (overrides config)')
    parser.add_argument('--max-size', type=float,
                       help='Maximum file size in MB (overrides config)')
    parser.add_argument('--limit', type=int, default=100,
                       help='Maximum number of messages to check (default: 100)')
    
    args = parser.parse_args()
    
    # Load configuration from file
    config = load_config(args.config)
    
    # Get credentials (prioritize environment variables)
    api_id = os.getenv('TG_API_ID', config.get('api_id'))
    api_hash = os.getenv('TG_API_HASH', config.get('api_hash'))
    phone = os.getenv('TG_PHONE', config.get('phone'))
    
    # Validate credentials
    if not all([api_id, api_hash, phone]):
        print("Error: Missing required credentials!")
        print("Please provide TG_API_ID, TG_API_HASH, and TG_PHONE")
        print("Either in config.json or as environment variables")
        sys.exit(1)
    
    # Get channel (command line > config)
    channel = args.channel or config.get('channel')
    if not channel:
        print("Error: No channel specified!")
        print("Use --channel argument or set 'channel' in config.json")
        sys.exit(1)
    
    # Get download path
    download_path = args.dest or config.get('download_path', './downloads')
    
    # Get file types
    file_types = None
    if args.types:
        file_types = [t.strip() for t in args.types.split(',')]
    elif config.get('file_types'):
        file_types = config.get('file_types')
    
    # Get keywords
    keywords = None
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(',')]
    elif config.get('keywords'):
        keywords = config.get('keywords')
    
    # Get max file size
    max_size_mb = args.max_size or config.get('max_file_size_mb')
    
    # Create downloader instance
    downloader = TelegramDownloader(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        download_path=download_path,
        keywords=keywords
    )
    
    try:
        # Connect and download
        await downloader.connect()
        await downloader.download_from_channel(
            channel=channel,
            file_types=file_types,
            max_size_mb=max_size_mb,
            limit=args.limit
        )
    finally:
        # Always disconnect
        await downloader.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDownload interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
