"""
Configuration and credential management.
"""

import os
from cryptography.fernet import Fernet

# ============================================
# ENCRYPTION KEY GENERATION (RUN ONCE)
# ============================================
# To generate a new key, run this in Python:
#   from cryptography.fernet import Fernet
#   print(Fernet.generate_key().decode())
#
# Then replace ENCRYPTION_KEY below with the output
# ============================================

# Encryption key - store this separately in production
ENCRYPTION_KEY = b'NUqnt-OjPHbgK_qD8ZUrUB37IocufEE78d6-C8mZ_XI='  # Replace with generated key

# Initialize cipher
cipher = Fernet(ENCRYPTION_KEY)

# ============================================
# ENCRYPTED CREDENTIALS
# ============================================
# To encrypt your credentials, run this:
#   cipher.encrypt(b"your_actual_credential").decode()
#
# Then replace the values below
# ============================================

# REPLACE THESE WITH YOUR ENCRYPTED VALUES
ENCRYPTED_APP_KEY = "gAAAAABo3vkbR-VrK1UqrcrOSrDiyLTd5og4W2hhk-UDRECrEUhGwsSqtLBfsqYTDCX_wb6Y2nzNbI9n1Q15p8LVFcEl2S9YNQ=="
ENCRYPTED_APP_SECRET = "gAAAAABo3vkbBkDXWKFqG_VpfNHF7HE8nu0l90_N8OQM47jn-Uno2JyJTS-h96hH5FvZN0Gi1Box9mufM6MnlzJA5y6ST_ALng=="
ENCRYPTED_REFRESH_TOKEN = "gAAAAABo6jq0sXRJYepaptBgqnTSN86zbtnEm1oEZCu85b7qsuAQHs_Ezsm8rk5UN4supRN1GvEYEvU7EjicxxI4GTFRBbWxhvTpU6BQ-r-WKh22mNDb1N2DGNsx71Q7G0t9I0jhWuHWkBu0xHbHN-qhHRNDZBc-loDRC2iqHwX7MdQhQog-a1M="

# Webhook URL
WEBHOOK_URL = "https://hook.us1.make.com/mfbx7yn3ltsrpxua6fes2tjpg621aebn"

# Upload settings
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunks
MAX_RETRIES = 3
PARALLEL_UPLOADS = 4  # Number of concurrent file uploads
PROGRESS_UPDATE_THRESHOLD = 25  # Send webhook update every 25%

# Supported file extensions
# ============================================
# PHOTOS - RAW and processed formats
# ============================================
PHOTO_EXTENSIONS = {
    # Canon
    '.cr2', '.cr3',
    # Nikon
    '.nef', '.nrw',
    # Sony
    '.arw', '.srf', '.sr2',
    # Adobe
    '.dng',
    # Olympus
    '.orf',
    # Panasonic
    '.rw2',
    # Pentax
    '.pef', '.ptx',
    # Fujifilm
    '.raf',
    # Standard formats
    '.jpg', '.jpeg',
    '.png',
    '.tif', '.tiff',
    # WebP (modern format)
    '.webp',
}

# ============================================
# VIDEOS - Common formats
# ============================================
VIDEO_EXTENSIONS = {
    # Most common
    '.mp4',      # H.264/H.265 - Universal
    '.mov',      # QuickTime - Apple/Canon/Nikon
    # Professional
    '.avi',      # Legacy but still used
    '.mkv',      # High quality container
    '.mts', '.m2ts',  # AVCHD - Sony/Panasonic
    # Apple
    '.m4v',      # iTunes/Apple
    # Others
    '.wmv',      # Windows Media
    '.flv',      # Flash (legacy)
    '.webm',     # Web format
    '.3gp',      # Mobile
    '.mpg', '.mpeg',  # MPEG
}

# Combine all allowed extensions
ALLOWED_EXTENSIONS = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS

def decrypt_credential(encrypted_value: str) -> str:
    """Decrypt an encrypted credential."""
    try:
        return cipher.decrypt(encrypted_value.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt credential: {e}")

def get_dropbox_credentials():
    """Get decrypted Dropbox credentials."""
    return {
        'app_key': decrypt_credential(ENCRYPTED_APP_KEY),
        'app_secret': decrypt_credential(ENCRYPTED_APP_SECRET),
        'refresh_token': decrypt_credential(ENCRYPTED_REFRESH_TOKEN)
    }