"""
Utility functions.
"""

import os
import sys
import logging
from typing import List, Tuple
from pathlib import Path
from config import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)

def setup_logging(log_file: str = None):
    """Configure logging for the application."""
    
    # If no log file specified, determine proper location based on platform
    if log_file is None:
        if sys.platform == 'win32':  # Windows
            log_dir = Path(os.environ.get('APPDATA', Path.home())) / 'PhotoUploader'
        elif sys.platform == 'darwin':  # macOS
            log_dir = Path.home() / 'Library' / 'Logs' / 'PhotoUploader'
        else:  # Linux and others
            log_dir = Path.home() / '.photouploader'
        
        # Create log directory if it doesn't exist
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / 'uploader.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger.info(f"Logging initialized. Log file: {log_file}")

def format_bytes(bytes_value: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} TB"

def format_time(seconds: int) -> str:
    """Convert seconds to human-readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def scan_folder(folder_path: str) -> Tuple[List[str], int]:
    """
    Scan folder for uploadable files.
    
    Returns:
        Tuple of (list of file paths, total size in bytes)
    """
    files = []
    total_size = 0
    
    folder_path_obj = Path(folder_path)
    
    if not folder_path_obj.exists():
        raise ValueError(f"Folder does not exist: {folder_path}")
    
    if not folder_path_obj.is_dir():
        raise ValueError(f"Path is not a folder: {folder_path}")
    
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            file_ext = Path(filename).suffix.lower()
            
            if file_ext in ALLOWED_EXTENSIONS:
                file_size = os.path.getsize(file_path)
                
                # Skip suspiciously small files (< 100KB) - likely corrupted
                if file_size > 100 * 1024:
                    files.append(file_path)
                    total_size += file_size
                else:
                    logger.warning(f"Skipping small file (possibly corrupted): {filename} ({file_size} bytes)")
    
    logger.info(f"Found {len(files)} valid files, total size: {format_bytes(total_size)}")
    return files, total_size

def extract_site_id_from_folder(folder_name: str) -> str:
    """
    Attempt to extract site ID from folder name.
    Examples:
      - "408 N 13th St" -> "408N13"
      - "408N13" -> "408N13"
      - "408-N-13" -> "408N13"
    """
    import re
    # Remove common separators and extract alphanumeric characters
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', folder_name)
    return cleaned.upper()

def validate_site_id(site_id: str) -> bool:
    """Validate site ID format (basic check)."""
    if not site_id:
        return False
    if len(site_id) < 2 or len(site_id) > 20:
        return False
    return True