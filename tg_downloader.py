#!/usr/bin/env python3
"""
Telegram Channel File Downloader

This script downloads files from a Telegram channel and tracks downloaded files
to avoid duplicates. It supports filtering by file type, size, and keywords.
"""

import os
import sys
import json
import re
import argparse
import asyncio
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Set, Optional, Union

try:
    from telethon import TelegramClient
    from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto, DocumentAttributeVideo, PeerChannel
except ImportError:
    print("Error: Required packages not installed.")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)


class TelegramDownloader:
    """Main class for downloading files from Telegram channels"""
    
    # Maximum allowed length for file extensions
    MAX_EXTENSION_LENGTH = 10
    
    # ffmpeg encoding constants
    FFMPEG_CRF = 23  # Constant Rate Factor for video quality (lower = better quality, 18-28 is reasonable range)
    FFMPEG_TIMEOUT = 300  # Timeout in seconds for ffmpeg processing (5 minutes)
    FFMPEG_ERROR_MSG_LENGTH = 200  # Maximum length for error message display
    
    # Common MIME type to extension mapping (for validation)
    MIME_TO_EXT = {
        'video/mp4': '.mp4',
        'video/mpeg': '.mpeg',
        'video/quicktime': '.mov',
        'video/x-msvideo': '.avi',
        'video/x-matroska': '.mkv',
        'video/webm': '.webm',
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/bmp': '.bmp',
        'application/pdf': '.pdf',
        'application/zip': '.zip',
        'application/x-rar-compressed': '.rar',
        'application/x-7z-compressed': '.7z',
        'application/msword': '.doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'audio/mpeg': '.mp3',
        'audio/ogg': '.ogg',
        'audio/wav': '.wav',
        'text/plain': '.txt',
    }
    
    def __init__(self, api_id: str, api_hash: str, phone: str, 
                 download_path: str = "./downloads",
                 history_file: str = "download_history.json",
                 keywords: Optional[List[str]] = None,
                 output_quality: Optional[str] = None):
        """
        Initialize the Telegram downloader
        
        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            phone: Phone number associated with Telegram account
            download_path: Root directory to save downloaded files (channel subdirectories will be created)
            history_file: JSON file to track downloaded files
            keywords: List of keywords to filter files (case-insensitive)
            output_quality: Target video quality for downsizing after download (e.g., '720p', '480p', '360p')
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.root_download_path = Path(download_path)
        self.history_file = Path(history_file)
        self.downloaded_files: Set[int] = set()
        self.client = None
        self.keywords = [k.lower() for k in keywords] if keywords else None
        self.output_quality = output_quality.lower() if output_quality else None
        self.current_channel_path = None  # Will be set when downloading from a specific channel
        
        # Create root download directory if it doesn't exist
        self.root_download_path.mkdir(parents=True, exist_ok=True)
        
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
    
    def _sanitize_channel_name(self, channel_name: str) -> str:
        """
        Convert channel name to a safe directory name
        
        Args:
            channel_name: Channel name or title to convert
        
        Returns:
            Sanitized directory name
        """
        if not channel_name or not channel_name.strip():
            return "unknown_channel"
        
        # Remove @ prefix if present
        name = channel_name.strip().lstrip('@')
        
        # Replace invalid filesystem characters with underscores
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\n', '\r']
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # Remove path traversal components
        name = name.replace('..', '_')
        name = name.lstrip('.')
        
        # Replace multiple spaces/underscores with single underscore
        name = re.sub(r'[ _]+', '_', name)
        
        # Ensure it's not empty after sanitization
        if not name or not name.strip():
            return "unknown_channel"
        
        # Limit length to 100 characters for directory names
        if len(name) > 100:
            name = name[:100].strip('_')
        
        return name
    
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
        
        # Remove path traversal components and dots at start
        text = text.replace('..', '_')
        text = text.lstrip('.')
        
        # Replace multiple spaces with single space using regex
        text = re.sub(r' +', ' ', text)
        
        # Trim to max length (accounting for extension)
        # Use encode/decode to handle multi-byte characters properly
        max_text_length = max_length - len(extension)
        
        # Ensure we have positive length for text
        if max_text_length < 1:
            return None
        
        if len(text) > max_text_length:
            # Truncate and ensure we don't break multi-byte characters
            text = text[:max_text_length].strip()
            # Encode to bytes and back to ensure valid UTF-8
            try:
                text = text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
            except UnicodeError:
                # If we can't encode/decode properly, just strip and hope for the best
                text = text.strip()
        
        # Ensure the result is not empty after sanitization
        if not text or not text.strip():
            return None
        
        # Add extension
        filename = text + extension
        return filename
    
    def _get_safe_extension(self, mime_type: Optional[str], fallback: str = '.bin') -> str:
        """
        Get a safe file extension from mime type
        
        Args:
            mime_type: MIME type string
            fallback: Fallback extension if mime type is unknown
        
        Returns:
            Safe file extension with dot prefix
        """
        if not mime_type:
            return fallback
        
        # Check if we have a known mapping
        if mime_type in self.MIME_TO_EXT:
            return self.MIME_TO_EXT[mime_type]
        
        # Try extracting the subtype as extension
        if '/' in mime_type:
            ext = mime_type.split('/')[-1]
            # Validate extension length and characters
            if len(ext) <= self.MAX_EXTENSION_LENGTH and ext.isalnum():
                return f'.{ext}'
        
        return fallback
    
    def _validate_and_secure_path(self, filename: str) -> Optional[Path]:
        """
        Validate that the filename is safe and construct a secure path
        
        Args:
            filename: The filename to validate
        
        Returns:
            Secure Path object within channel's download directory, or None if unsafe
        """
        # Ensure we have a channel path set
        if not self.current_channel_path:
            print(f"Error: Channel path not set")
            return None
        
        # Get just the filename component (remove any path separators)
        safe_name = os.path.basename(filename)
        
        # Additional check: ensure no path separators remain
        if os.sep in safe_name or (os.altsep and os.altsep in safe_name):
            print(f"Security Warning: Path separator in filename blocked: {filename}")
            return None
        
        # Construct the full path within the channel's directory
        file_path = self.current_channel_path / safe_name
        
        # Resolve the path and ensure it's within the channel's download directory
        try:
            resolved_path = file_path.resolve()
            resolved_channel = self.current_channel_path.resolve()
            
            # Use is_relative_to if available (Python 3.9+), otherwise use commonpath
            try:
                # Python 3.9+ method
                if not resolved_path.is_relative_to(resolved_channel):
                    print(f"Security Warning: Path traversal attempt blocked: {filename}")
                    return None
            except AttributeError:
                # Fallback for Python 3.7-3.8
                try:
                    common = os.path.commonpath([str(resolved_path), str(resolved_channel)])
                    if common != str(resolved_channel):
                        print(f"Security Warning: Path traversal attempt blocked: {filename}")
                        return None
                except ValueError:
                    # Paths are on different drives (Windows)
                    print(f"Security Warning: Path on different drive blocked: {filename}")
                    return None
            
            return resolved_path
        except Exception as e:
            print(f"Error validating path for {filename}: {e}")
            return None
    
    def _is_video(self, doc) -> bool:
        """
        Check if a document is a video
        
        Args:
            doc: Document object from MessageMediaDocument
        
        Returns:
            True if document is a video, False otherwise
        """
        # Check mime type
        if doc.mime_type and doc.mime_type.startswith('video/'):
            return True
        
        # Check for video attribute
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                return True
        
        return False
    
    def _downsize_video_with_ffmpeg(self, file_path: Path, target_quality: str) -> bool:
        """
        Downsize a video file using ffmpeg
        
        Args:
            file_path: Path to the video file
            target_quality: Target quality (e.g., '720p', '480p', '360p')
        
        Returns:
            True if successful, False otherwise
        """
        # Check if ffmpeg is available
        if not shutil.which('ffmpeg'):
            print(f"Warning: ffmpeg not found. Skipping video downsizing for {file_path.name}")
            return False
        
        # Map quality to height
        quality_map = {
            '4k': 2160,
            '2160p': 2160,
            '1440p': 1440,
            '1080p': 1080,
            '720p': 720,
            '480p': 480,
            '360p': 360,
            '240p': 240
        }
        
        target_height = quality_map.get(target_quality)
        if not target_height:
            print(f"Warning: Invalid target quality '{target_quality}'. Skipping downsizing.")
            return False
        
        # Create temporary output file
        output_path = file_path.parent / f"{file_path.stem}_temp{file_path.suffix}"
        
        try:
            # Build ffmpeg command
            # -i: input file
            # -vf scale: scale video to target height (width=-2 maintains aspect ratio with even number)
            # -c:v libx264: use H.264 codec
            # -crf: constant rate factor (quality)
            # -preset medium: encoding speed/compression trade-off
            # -c:a copy: copy audio without re-encoding
            cmd = [
                'ffmpeg',
                '-i', str(file_path),
                '-vf', f'scale=-2:{target_height}',
                '-c:v', 'libx264',
                '-crf', str(self.FFMPEG_CRF),
                '-preset', 'medium',
                '-c:a', 'copy',
                '-y',  # Overwrite output file without asking
                str(output_path)
            ]
            
            print(f"  Downsizing video to {target_quality}...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.FFMPEG_TIMEOUT
            )
            
            if result.returncode == 0:
                # Replace original with downsized version
                output_path.replace(file_path)
                print(f"  ✓ Video downsized to {target_quality}")
                return True
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')[:self.FFMPEG_ERROR_MSG_LENGTH]
                print(f"  ✗ ffmpeg failed: {error_msg}")
                # Clean up temp file if it exists
                if output_path.exists():
                    output_path.unlink()
                return False
                
        except subprocess.TimeoutExpired:
            print(f"  ✗ ffmpeg timeout while processing {file_path.name}")
            if output_path.exists():
                output_path.unlink()
            return False
        except Exception as e:
            print(f"  ✗ Error during video downsizing: {e}")
            if output_path.exists():
                output_path.unlink()
            return False
    
    async def connect(self):
        """Connect to Telegram"""
        session_name = f"session_{self.phone}"
        self.client = TelegramClient(session_name, self.api_id, self.api_hash)
        
        print("Connecting to Telegram...")
        await self.client.start(phone=self.phone)
        print("Connected successfully!")
    
    async def download_from_channel(self, channel: Union[str, int], 
                                    file_types: Optional[List[str]] = None,
                                    max_size_mb: Optional[float] = None,
                                    limit: int = 200):
        """
        Download files from a Telegram channel
        
        Args:
            channel: Channel username (str) or channel ID (int)
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
        print(f"Output quality: {self.output_quality if self.output_quality else 'None'}")
        print(f"Checking last {limit} messages...\n")
        
        downloaded_count = 0
        skipped_count = 0
        
        try:
            # Get channel entity
            # If channel is an integer ID, wrap it with PeerChannel for proper handling
            print(f"Attempting to get channel entity for: {channel}")
            if isinstance(channel, int):
                print(f"Channel is an integer ID, using PeerChannel wrapper")
                entity_input = PeerChannel(channel_id=channel)
            else:
                entity_input = channel
            
            entity = await self.client.get_entity(entity_input)
            print(f"Successfully retrieved channel entity: {entity.title if hasattr(entity, 'title') else channel}")
            
            # Extract channel name for directory
            if hasattr(entity, 'title') and entity.title:
                channel_name = entity.title
            elif hasattr(entity, 'username') and entity.username:
                channel_name = entity.username
            else:
                # Fallback to using the input channel identifier
                channel_name = str(channel).lstrip('@')
            
            print(f"Using channel name for directory: {channel_name}")
            
            # Create channel-specific subdirectory
            safe_channel_name = self._sanitize_channel_name(channel_name)
            self.current_channel_path = self.root_download_path / safe_channel_name
            self.current_channel_path.mkdir(parents=True, exist_ok=True)
            print(f"Files will be downloaded to: {self.current_channel_path}\n")
            
            # Iterate through messages
            print(f"Starting to iterate through messages (limit: {limit})...")
            async for message in self.client.iter_messages(entity, limit=limit):
                # Skip if message has no media
                if not message.media:
                    continue
                
                # Skip if already downloaded
                if message.id in self.downloaded_files:
                    skipped_count += 1
                    print(f"Skipping message {message.id} - already downloaded")
                    continue
                
                # Handle documents (files)
                if isinstance(message.media, MessageMediaDocument):
                    print(f"Processing document from message {message.id}")
                    doc = message.media.document
                    filename = None
                    original_filename = None
                    
                    # Get original filename from attributes
                    for attr in doc.attributes:
                        if hasattr(attr, 'file_name'):
                            original_filename = attr.file_name
                            print(f"Found original filename in attributes: {original_filename}")
                            break
                    
                    # Try to use message text as filename
                    if message.text:
                        print(f"Attempting to create filename from message text: {message.text[:50]}...")
                        # Get extension from original filename or mime type
                        if original_filename:
                            ext = Path(original_filename).suffix
                        else:
                            ext = self._get_safe_extension(doc.mime_type)
                        
                        # Create filename from message text
                        filename = self._sanitize_filename(message.text, ext)
                        if filename:
                            print(f"Created filename from message text: {filename}")
                        else:
                            print(f"Message text sanitization returned None")
                    
                    # Fall back to original filename or generated name
                    if not filename:
                        print(f"Falling back to alternative filename generation")
                        if original_filename:
                            # Sanitize original filename to prevent path traversal
                            ext = Path(original_filename).suffix
                            base = Path(original_filename).stem
                            filename = self._sanitize_filename(base, ext)
                            # If sanitization fails, use a safe generated name
                            if not filename:
                                ext = Path(original_filename).suffix or '.bin'
                                filename = f"file_{message.id}{ext}"
                                print(f"Sanitization failed, using generated name: {filename}")
                            else:
                                print(f"Using sanitized original filename: {filename}")
                        else:
                            # Use mime type for extension, with fallback to 'bin'
                            ext = self._get_safe_extension(doc.mime_type)
                            filename = f"file_{message.id}{ext}"
                            print(f"No original filename, using generated name: {filename}")
                    
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
                    file_info = f"{filename} ({doc.size / (1024 * 1024):.2f} MB)"
                    print(f"Downloading: {file_info}")
                    
                    # Validate path security
                    file_path = self._validate_and_secure_path(filename)
                    if not file_path:
                        print(f"✗ Skipping {filename} (invalid or unsafe path)")
                        continue
                    
                    try:
                        print(f"Attempting to download document to: {file_path}")
                        await message.download_media(file=str(file_path))
                        self.downloaded_files.add(message.id)
                        downloaded_count += 1
                        print(f"✓ Downloaded: {filename}")
                        
                        # Downsize video if output_quality is specified and file is a video
                        if self.output_quality and self._is_video(doc):
                            self._downsize_video_with_ffmpeg(file_path, self.output_quality)
                    except Exception as e:
                        print(f"✗ Error downloading {filename if filename else f'file from message {message.id}'}: {e}")
                
                # Handle photos
                elif isinstance(message.media, MessageMediaPhoto):
                    print(f"Processing photo from message {message.id}")
                    filename = None  # Initialize filename before use
                    # Try to use message text as filename
                    if message.text:
                        print(f"Attempting to create filename from message text for photo")
                        filename = self._sanitize_filename(message.text, '.jpg')
                    
                    # Fall back to default photo naming
                    if not filename:
                        filename = f"photo_{message.id}.jpg"
                        print(f"Using default photo filename: {filename}")
                    
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
                    
                    # Validate path security
                    file_path = self._validate_and_secure_path(filename)
                    if not file_path:
                        print(f"✗ Skipping {filename} (invalid or unsafe path)")
                        continue
                    
                    try:
                        print(f"Attempting to download photo to: {file_path}")
                        await message.download_media(file=str(file_path))
                        self.downloaded_files.add(message.id)
                        downloaded_count += 1
                        print(f"✓ Downloaded: {filename}")
                    except Exception as e:
                        print(f"✗ Error downloading {filename if filename else f'photo from message {message.id}'}: {e}")
            
            # Save history after downloading
            self._save_history()
            print(f"Download history saved to {self.history_file}")
            
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
  
  # Downsize videos after download
  python tg_downloader.py --channel @mychannel --output-quality 720p
  python tg_downloader.py --channel @mychannel --output-quality 480p
  
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
    parser.add_argument('--output-quality',
                       help='Target quality for video downsizing after download: 720p, 480p, 360p, etc. (overrides config)')
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
    
    # Convert numeric string to integer for channel ID support
    # Supports both positive IDs and negative IDs (like -1001234567890)
    # Uses regex to safely match valid integer format: optional minus followed by digits
    if isinstance(channel, str) and not channel.startswith('@') and re.match(r'^-?\d+$', channel):
        channel = int(channel)
        print(f"Detected numeric channel ID: {channel}")
    
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
    
    # Get output quality
    output_quality = args.output_quality or config.get('output_quality')
    
    # Create downloader instance
    downloader = TelegramDownloader(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        download_path=download_path,
        keywords=keywords,
        output_quality=output_quality
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
