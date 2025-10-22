"""
Photographer SnapFlow - FINAL VERSION
Features:
- Two-column layout (Market + Photos)
- Content type selection (Daytime/Twilight/Video)
- Parallel uploads (4 concurrent)
- Simplified path handling (Make.com returns complete path)
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import logging
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional PIL import for icon support
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️  Warning: Pillow not installed. Icons will not be displayed.")
    print("   To enable icons, run: pip install Pillow")

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dropbox_uploader import DropboxUploader
from webhook_client import MakeWebhookClient
from utils import (
    setup_logging, format_bytes, format_time, 
    scan_folder, validate_site_id
)
from config import PROGRESS_UPDATE_THRESHOLD

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# UI Color Scheme - Professional and Clean
COLORS = {
    'header_bg': '#F8F9FA',        # Light gray background
    'header_border': '#DEE2E6',    # Subtle border
    'accent': '#007BFF',           # Primary blue
    'success': '#28A745',          # Green for success
    'warning': '#FFC107',          # Yellow/orange for warnings
    'error': '#DC3545',            # Red for errors
    'text_primary': '#212529',     # Dark text
    'text_secondary': '#6C757D',   # Gray text
    'bg_light': '#FFFFFF',         # White background
}

# Platform-specific fonts
if sys.platform == 'win32':
    FONTS = {
        'app_title': ('Segoe UI', 20, 'bold'),
        'subtitle': ('Segoe UI', 9),
        'section_header': ('Segoe UI', 10, 'bold'),
        'body': ('Segoe UI', 9),
        'small': ('Segoe UI', 8),
    }
elif sys.platform == 'darwin':
    FONTS = {
        'app_title': ('SF Pro Display', 20, 'bold'),
        'subtitle': ('SF Pro Text', 9),
        'section_header': ('SF Pro Text', 10, 'bold'),
        'body': ('SF Pro Text', 9),
        'small': ('SF Pro Text', 8),
    }
else:
    FONTS = {
        'app_title': ('Arial', 20, 'bold'),
        'subtitle': ('Arial', 9),
        'section_header': ('Arial', 10, 'bold'),
        'body': ('Arial', 9),
        'small': ('Arial', 8),
    }

class PhotoUploaderApp:
    """Main application window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("SnapFlow - Professional Photo & Video Uploader")
        self.root.geometry("750x720")
        self.root.resizable(False, False)
        
        # State variables
        self.photographer_id = self._load_photographer_id()
        self.photographer_name = None
        self.available_markets = []
        self.selected_market = tk.StringVar()
        self.content_type = tk.StringVar(value="daytime")  # Default: daytime
        self.selected_folder = None
        self.files_to_upload = []
        self.total_size_bytes = 0
        self.upload_in_progress = False
        
        # Upload tracking
        self.files_uploaded = 0
        self.files_failed = 0
        self.upload_start_time = None
        self.last_progress_update = 0
        self.upload_lock = threading.Lock()  # Thread-safe counter updates
        
        # Validated site info
        self.validated_site_info = None
        
        # Initialize clients
        self.webhook_client = None
        self.dropbox_uploader = None
        
        # UI Resources
        self.app_icon = None
        self.window_icon = None
        
        self._create_widgets()
        self._check_photographer_id()
    
    def _load_photographer_id(self) -> Optional[str]:
        """Load photographer ID from local config file."""
        config_file = Path.home() / '.photo_uploader_config'
        if config_file.exists():
            try:
                return config_file.read_text().strip()
            except Exception as e:
                logger.error(f"Failed to load photographer ID: {e}")
        return None
    
    def _save_photographer_id(self, photographer_id: str):
        """Save photographer ID to local config file."""
        config_file = Path.home() / '.photo_uploader_config'
        try:
            config_file.write_text(photographer_id)
            logger.info("Photographer ID saved")
        except Exception as e:
            logger.error(f"Failed to save photographer ID: {e}")
    
    def _check_photographer_id(self):
        """Check if photographer ID is set, prompt if not."""
        if not self.photographer_id:
            self._prompt_photographer_id()
        else:
            self._initialize_clients()
    
    
    def _load_app_icon(self):
        """Load application icon for display in UI and window."""
        try:
            # Try to find icon file
            icon_paths = [
                'uploadericon.png',  # Same directory
                '../uploadericon.png',  # Parent directory
                os.path.join(os.path.dirname(__file__), 'uploadericon.png'),
                os.path.join(os.path.dirname(__file__), '..', 'uploadericon.png'),
            ]
            
            icon_file = None
            for path in icon_paths:
                if os.path.exists(path):
                    icon_file = path
                    break
            
            if icon_file:
                # Load icon for UI display (64x64 for better quality)
                img = Image.open(icon_file)
                
                # Use high-quality downsampling
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                
                # Optional: Enhance sharpness for better display
                try:
                    from PIL import ImageEnhance
                    enhancer = ImageEnhance.Sharpness(img)
                    img = enhancer.enhance(1.2)  # Slightly sharpen
                except:
                    pass  # If enhancement fails, use original
                
                self.app_icon = ImageTk.PhotoImage(img)
                
                # Set window icon
                self._set_window_icon(icon_file)
                
                logger.info(f"Loaded app icon from: {icon_file}")
            else:
                logger.warning("Icon file not found, using default")
        except Exception as e:
            logger.error(f"Failed to load icon: {e}")
    
    def _set_window_icon(self, icon_path):
        """Set window icon in title bar and taskbar."""
        try:
            if sys.platform == 'win32':
                # Windows: Try to use .ico file if available
                ico_path = icon_path.replace('.png', '.ico')
                if os.path.exists(ico_path):
                    self.root.iconbitmap(ico_path)
                    logger.info("Set Windows .ico icon")
                else:
                    # Use PNG as fallback
                    icon_img = Image.open(icon_path)
                    icon_img = icon_img.resize((32, 32), Image.Resampling.LANCZOS)
                    self.window_icon = ImageTk.PhotoImage(icon_img)
                    self.root.iconphoto(True, self.window_icon)
                    logger.info("Set Windows PNG icon")
            else:
                # macOS/Linux: Use PNG
                icon_img = Image.open(icon_path)
                icon_img = icon_img.resize((32, 32), Image.Resampling.LANCZOS)
                self.window_icon = ImageTk.PhotoImage(icon_img)
                self.root.iconphoto(True, self.window_icon)
                logger.info("Set macOS/Linux icon")
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}")

    def _prompt_photographer_id(self):
        """Show dialog to enter photographer ID."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Enter your Name")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Enter Your Name:", 
                 font=('Segoe UI', 11)).pack(pady=20)
        
        id_entry = ttk.Entry(dialog, width=30, font=('Segoe UI', 10))
        id_entry.pack(pady=10)
        id_entry.focus()
        
        def save_id():
            photographer_id = id_entry.get().strip().upper()
            if photographer_id:
                self.photographer_id = photographer_id
                self._save_photographer_id(photographer_id)
                self._initialize_clients()
                dialog.destroy()
            else:
                messagebox.showwarning("Invalid Input", "Please enter a Name")
        
        ttk.Button(dialog, text="Save", command=save_id).pack(pady=10)
        
        dialog.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
    
    def _initialize_clients(self):
        """Initialize webhook client and request config from Make.com."""
        try:
            self.webhook_client = MakeWebhookClient(self.photographer_id)
            self.photographer_label.config(text=f"Loading configuration...")
            self.root.update()
            
            # Request config in background
            thread = threading.Thread(target=self._request_config_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            messagebox.showerror("Initialization Error", 
                               f"Failed to initialize: {str(e)}")
    
    def _request_config_thread(self):
        """Request configuration from Make.com in background thread."""
        try:
            logger.info("Requesting config from Make.com...")
            result = self.webhook_client.request_config()
            self.root.after(0, self._handle_config_response, result)
        except Exception as e:
            logger.error(f"Config request error: {e}")
            self.root.after(0, self._handle_config_response, {
                'success': False,
                'error': str(e)
            })
    
    def _handle_config_response(self, result: dict):
        """Handle config response from Make.com in main thread."""
        if result.get('success'):
            self.available_markets = result.get('markets', [])
            self.photographer_name = result.get('photographer_name', '')
            
            display_name = self.photographer_name if self.photographer_name else self.photographer_id
            self.photographer_label.config(text=f"Photographer: {display_name}")
            
            if self.available_markets:
                self.market_combo['values'] = self.available_markets
                self.market_combo.current(0)
                self.market_combo.config(state='readonly')
                logger.info(f"Loaded {len(self.available_markets)} markets")
            else:
                logger.warning("No markets received")
                messagebox.showwarning("No Markets", 
                                     "No markets available. Please contact administrator.")
            
            logger.info(f"Initialized for photographer: {display_name}")
        else:
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            logger.error(f"Config request failed: {error_msg}")
            self.photographer_label.config(text=f"Photographer: {self.photographer_id} (Offline)")
            messagebox.showerror("Configuration Failed", 
                               f"Failed to load configuration:\n\n{error_msg}\n\n"
                               f"You can continue but validation may not work.")
            self.market_combo.config(state='disabled')
    
    def _create_widgets(self):
        """Create UI widgets with improved layout."""
        
        # HEADER - Enhanced with icon and professional styling
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X)
        
        # Header with professional styling
        header_bg = tk.Frame(header_frame, bg=COLORS['header_bg'], height=110)
        header_bg.pack(fill=tk.X)
        
        # Load app icon first
        self._load_app_icon()
        
        # Content container with proper padding
        content_container = tk.Frame(header_bg, bg=COLORS['header_bg'])
        content_container.pack(fill=tk.X, padx=25, pady=20)
        
        # Horizontal layout: Icon + Text with improved spacing
        icon_text_layout = tk.Frame(content_container, bg=COLORS['header_bg'])
        icon_text_layout.pack(anchor=tk.W)
        
        # Icon with better positioning (if loaded)
        if self.app_icon:
            # Icon container for better control
            icon_container = tk.Frame(icon_text_layout, bg=COLORS['header_bg'])
            icon_container.pack(side=tk.LEFT, padx=(0, 20))  # Increased spacing from 15 to 20
            
            icon_label = tk.Label(icon_container, image=self.app_icon, bg=COLORS['header_bg'])
            icon_label.pack()
        
        # Text section with improved hierarchy
        text_container = tk.Frame(icon_text_layout, bg=COLORS['header_bg'])
        text_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # App name - Larger, bolder
        app_name_label = tk.Label(
            text_container,
            text="SnapFlow Uploader",
            font=FONTS['app_title'],
            fg=COLORS['text_primary'],
            bg=COLORS['header_bg'],
            anchor=tk.W
        )
        app_name_label.pack(anchor=tk.W)
        
        # Subtitle with better spacing
        subtitle_label = tk.Label(
            text_container,
            text="Professional Photo & Video Uploader",
            font=FONTS['subtitle'],
            fg=COLORS['text_secondary'],
            bg=COLORS['header_bg'],
            anchor=tk.W
        )
        subtitle_label.pack(anchor=tk.W, pady=(3, 0))  # Added top padding
        
        # Photographer info with accent color
        self.photographer_label = tk.Label(
            text_container,
            text="Loading...",
            font=FONTS['body'],
            fg=COLORS['accent'],
            bg=COLORS['header_bg'],
            anchor=tk.W
        )
        self.photographer_label.pack(anchor=tk.W, pady=(8, 0))  # More spacing from subtitle
        
        # Bottom border line
        border_line = tk.Frame(self.root, bg=COLORS['header_border'], height=1)
        border_line.pack(fill=tk.X)
        
        # TWO-COLUMN ROW: MARKET (40%) + PHOTOS (60%)
        top_row_frame = ttk.Frame(self.root, padding=(20, 15))  # Increased vertical padding
        top_row_frame.pack(fill=tk.X)
        
        # LEFT COLUMN: MARKET (40%)
        market_frame = ttk.LabelFrame(top_row_frame, text="Select Market", padding=15)
        market_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
        market_frame.config(width=250)
        
        ttk.Label(market_frame, text="Market:").pack(anchor=tk.W, pady=(0, 5))
        
        self.market_combo = ttk.Combobox(market_frame, 
                                        textvariable=self.selected_market,
                                        width=20, state='disabled', font=('Segoe UI', 10))
        self.market_combo.pack(fill=tk.X)
        self.market_combo.bind('<<ComboboxSelected>>', self._on_market_changed)
        
        # RIGHT COLUMN: PHOTOS (60%)
        folder_frame = ttk.LabelFrame(top_row_frame, text="Select Photos/Videos", padding=15)
        folder_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Button container for folder and file selection
        button_container = ttk.Frame(folder_frame)
        button_container.pack(pady=(5, 15))
        
        self.select_folder_btn = ttk.Button(button_container, text="📁 Select Folder", 
                                           command=self._select_folder)
        self.select_folder_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.select_files_btn = ttk.Button(button_container, text="📄 Select Files", 
                                          command=self._select_files)
        self.select_files_btn.pack(side=tk.LEFT)
        
        self.folder_label = ttk.Label(folder_frame, text="No folder selected", 
                                     font=('Segoe UI', 9), foreground='#6C757D')
        self.folder_label.pack(anchor=tk.W)
        
        self.file_info_label = ttk.Label(folder_frame, text="", 
                                        font=('Segoe UI', 9), foreground='#007BFF')
        self.file_info_label.pack(anchor=tk.W, pady=(5, 0))
        
        # CONTENT TYPE SELECTION (FULL WIDTH)
        content_frame = ttk.LabelFrame(self.root, text="Content Type", padding=15)
        content_frame.pack(fill=tk.X, padx=20, pady=10)
        
        radio_frame = ttk.Frame(content_frame)
        radio_frame.pack(anchor=tk.W)
        
        ttk.Radiobutton(radio_frame, text="Daytime Photos", 
                       variable=self.content_type, value="daytime",
                       command=self._on_content_type_changed).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Radiobutton(radio_frame, text="Twilight Photos (manual editors)", 
                       variable=self.content_type, value="twilight",
                       command=self._on_content_type_changed).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(radio_frame, text="High end (Manual)", 
                       variable=self.content_type, value="manual",
                       command=self._on_content_type_changed).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Radiobutton(radio_frame, text="Video", 
                       variable=self.content_type, value="video",
                       command=self._on_content_type_changed).pack(side=tk.LEFT)
        
        self.content_info_label = ttk.Label(content_frame, text="Standard daytime photos for automated processing", 
                                           font=('Segoe UI', 8), foreground='#6C757D')
        self.content_info_label.pack(anchor=tk.W, pady=(5, 0))
        
        # SITE ID & VALIDATION (FULL WIDTH)
        site_frame = ttk.LabelFrame(self.root, text="Site ID & Validation", padding=15)
        site_frame.pack(fill=tk.X, padx=20, pady=10)
        
        input_frame = ttk.Frame(site_frame)
        input_frame.pack(fill=tk.X)
        
        ttk.Label(input_frame, text="Site ID:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.site_id_var = tk.StringVar()
        self.site_id_var.trace('w', lambda *args: self._update_validate_button_state())
        self.site_id_entry = ttk.Entry(input_frame, textvariable=self.site_id_var, 
                                       width=25, font=('Segoe UI', 11))
        self.site_id_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        self.validate_btn = ttk.Button(input_frame, text="Validate", 
                                       command=self._validate_site, state='disabled')
        self.validate_btn.pack(side=tk.LEFT)
        
        self.site_status_label = ttk.Label(site_frame, text="", 
                                          font=('Segoe UI', 9), wraplength=600)
        self.site_status_label.pack(pady=(10, 0), anchor=tk.W)
        
        # UPLOAD SECTION (FULL WIDTH)
        upload_frame = ttk.LabelFrame(self.root, text="Upload", padding=15)
        upload_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Upload button - centered
        button_frame = ttk.Frame(upload_frame)
        button_frame.pack(pady=(0, 15))
        
        self.upload_btn = ttk.Button(button_frame, text="🚀 Start Upload", 
                                     command=self._start_upload, state='disabled')
        self.upload_btn.pack()
        
        # Progress info
        self.progress_label = ttk.Label(upload_frame, text="", 
                                       font=('Segoe UI', 9))
        self.progress_label.pack()
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(upload_frame, length=620, 
                                           mode='determinate')
        self.progress_bar.pack(pady=10)
        
        # Status messages
        self.status_label = ttk.Label(upload_frame, text="", 
                                     font=('Segoe UI', 9), foreground='#007BFF')
        self.status_label.pack()
        
        self.detail_label = ttk.Label(upload_frame, text="", 
                                     font=('Segoe UI', 8), foreground='#6C757D')
        self.detail_label.pack(pady=(5, 0))
    
    def _on_market_changed(self, event=None):
        """Handle market selection change."""
        self.validated_site_info = None
        self.site_status_label.config(text="")
        self.upload_btn.config(state='disabled')
        self._update_validate_button_state()
    
    def _on_content_type_changed(self):
        """Handle content type selection change."""
        content = self.content_type.get()
        
        # Update info label based on selection
        if content == "daytime":
            self.content_info_label.config(text="Standard daytime photos for automated processing")
        elif content == "twilight":
            self.content_info_label.config(text="⚠️ Twilight photos - Slack notification will be sent to manual editors")
        elif content == "video":
            self.content_info_label.config(text="📹 Video files - will be uploaded to video folder")
        elif content == "manual":
            self.content_info_label.config(text="📹 These files - will be uploaded to Photos folder")
        
        # Reset validation when content type changes
        self.validated_site_info = None
        self.site_status_label.config(text="")
        self.upload_btn.config(state='disabled')
    
    def _update_validate_button_state(self):
        """Enable validate button only when all prerequisites are met."""
        market = self.selected_market.get().strip()
        site_id = self.site_id_var.get().strip()
        has_folder = self.selected_folder is not None
        
        if market and site_id and has_folder:
            self.validate_btn.config(state='normal')
        else:
            self.validate_btn.config(state='disabled')
    
    def _validate_site(self):
        """Validate site ID with Make webhook."""
        market = self.selected_market.get().strip()
        site_id = self.site_id_var.get().strip()
        
        if not market:
            messagebox.showwarning("No Market Selected", 
                                 "Please select a market first")
            return
        
        if not validate_site_id(site_id):
            messagebox.showwarning("Invalid Site ID", 
                                 "Please enter a valid site ID")
            return
        
        if not self.selected_folder:
            messagebox.showinfo("Select Folder First", 
                              "Please select a photo folder before validating")
            return
        
        self.validate_btn.config(state='disabled')
        self.site_status_label.config(text="Validating...", foreground='#007BFF')
        
        thread = threading.Thread(target=self._validate_site_thread, 
                                 args=(market, site_id))
        thread.daemon = True
        thread.start()
    
    def _validate_site_thread(self, market: str, site_id: str):
        """Validate site in background thread."""
        try:
            total_size_mb = self.total_size_bytes / (1024 * 1024)
            content_type = self.content_type.get()
            
            result = self.webhook_client.validate_site(
                market=market,
                site_id=site_id,
                file_count=len(self.files_to_upload),
                total_size_mb=total_size_mb,
                content_type=content_type
            )
            
            self.root.after(0, self._handle_validation_result, result)
        
        except Exception as e:
            logger.error(f"Validation error: {e}")
            self.root.after(0, self._handle_validation_result, {
                'success': False,
                'error': str(e)
            })
    
    def _handle_validation_result(self, result: dict):
        """Handle validation result in main thread."""
        self.validate_btn.config(state='normal')
        
        if result.get('success'):
            self.validated_site_info = result
            
            status_text = (f"✓ {result['client_name']}\n"
                          f"   {result['property_address']}")
            self.site_status_label.config(text=status_text, foreground='#28A745')
            
            self.upload_btn.config(state='normal')
            
            messagebox.showinfo("Site Validated", 
                              f"Ready to upload to:\n\n"
                              f"{result['client_name']}\n"
                              f"{result['property_address']}")
        else:
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            self.site_status_label.config(text=f"✗ {error_msg}", 
                                        foreground='#DC3545')
            messagebox.showerror("Validation Failed", error_msg)
    
    def _select_files(self):
        """Select individual files instead of a folder."""
        from config import ALLOWED_EXTENSIONS
        
        # Create file type filters
        photo_exts = ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.cr2', '.cr3', '.nef', '.arw', '.dng']
        video_exts = ['.mp4', '.mov', '.avi', '.mkv', '.mts', '.m2ts', '.m4v']
        
        files = filedialog.askopenfilenames(
            title="Select Photos/Videos",
            filetypes=[
                ("All Media", " ".join(f"*{ext}" for ext in ALLOWED_EXTENSIONS)),
                ("Photos", " ".join(f"*{ext}" for ext in photo_exts)),
                ("Videos", " ".join(f"*{ext}" for ext in video_exts)),
                ("All files", "*.*")
            ]
        )
        
        if not files:
            return  # User cancelled
        
        # Validate and collect files
        self.files_to_upload = []
        self.total_size_bytes = 0
        skipped = 0
        
        for file_path in files:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in ALLOWED_EXTENSIONS:
                file_size = os.path.getsize(file_path)
                
                # Skip suspiciously small files (< 100KB)
                if file_size > 100 * 1024:
                    self.files_to_upload.append(file_path)
                    self.total_size_bytes += file_size
                else:
                    skipped += 1
                    logger.warning(f"Skipping small file: {os.path.basename(file_path)} ({file_size} bytes)")
            else:
                skipped += 1
                logger.warning(f"Skipping unsupported file type: {file_path}")
        
        if not self.files_to_upload:
            messagebox.showwarning("No Valid Files", 
                                 "No valid photo or video files were selected.\n\n"
                                 "Supported formats: Photos (JPG, PNG, RAW) and Videos (MP4, MOV, etc)")
            return
        
        # Update UI
        file_count = len(self.files_to_upload)
        self.selected_folder = "Multiple Files"  # Mark as file selection
        
        self.folder_label.config(
            text=f"✓ {file_count} file{'s' if file_count != 1 else ''} selected",
            foreground='#212529'
        )
        
        info_text = f"{format_bytes(self.total_size_bytes)} total"
        if skipped > 0:
            info_text += f" • {skipped} file{'s' if skipped != 1 else ''} skipped"
        
        self.file_info_label.config(text=info_text)
        
        # Enable validation if market is selected
        if self.selected_market.get():
            self.validate_btn.config(state='normal')
        
        logger.info(f"Selected {file_count} files, total size: {format_bytes(self.total_size_bytes)}")
        
    def _select_folder(self):
        """Select folder containing photos."""
        folder_path = filedialog.askdirectory(title="Select Photo Folder")
        
        if folder_path:
            self.selected_folder = folder_path
            folder_name = os.path.basename(folder_path)
            
            try:
                self.files_to_upload, self.total_size_bytes = scan_folder(folder_path)
                
                if not self.files_to_upload:
                    messagebox.showwarning("No Files", 
                                         "No valid photo files found in this folder")
                    return
                
                self.folder_label.config(text=folder_name, foreground='#212529')
                self.file_info_label.config(
                    text=f"{len(self.files_to_upload)} files • {format_bytes(self.total_size_bytes)}"
                )
                
                self._update_validate_button_state()
                
            except Exception as e:
                logger.error(f"Error scanning folder: {e}")
                messagebox.showerror("Error", f"Failed to scan folder: {str(e)}")
    
    def _start_upload(self):
        """Start upload process."""
        if not self.validated_site_info:
            messagebox.showwarning("Not Validated", 
                                 "Please validate the site ID first")
            return
        
        if self.upload_in_progress:
            return
        
        from config import PARALLEL_UPLOADS
        
        confirm = messagebox.askyesno(
            "Confirm Upload",
            f"Upload {len(self.files_to_upload)} files to:\n\n"
            f"{self.validated_site_info['client_name']}\n"
            f"{self.validated_site_info['property_address']}\n\n"
            f"Total size: {format_bytes(self.total_size_bytes)}\n"
            f"Method: {PARALLEL_UPLOADS} parallel uploads\n\n"
            f"Continue?"
        )
        
        if not confirm:
            return
        
        # Disable controls
        self.upload_btn.config(state='disabled')
        self.select_folder_btn.config(state='disabled')
        self.validate_btn.config(state='disabled')
        self.site_id_entry.config(state='disabled')
        self.market_combo.config(state='disabled')
        
        self.upload_in_progress = True
        self.files_uploaded = 0
        self.files_failed = 0
        self.upload_start_time = time.time()
        self.last_progress_update = 0
        
        # Start upload thread
        thread = threading.Thread(target=self._upload_thread)
        thread.daemon = True
        thread.start()
    
    def _upload_thread(self):
        """Upload files in background thread with PARALLEL processing."""
        try:
            self.dropbox_uploader = DropboxUploader()
            
            market = self.selected_market.get()
            site_id = self.site_id_var.get().strip()
            content_type = self.content_type.get()
            job_id = self.validated_site_info['job_id']
            dropbox_path = self.validated_site_info['dropbox_path']  # Complete path from Make.com
            total_size_mb = self.total_size_bytes / (1024 * 1024)
            
            self.webhook_client.notify_upload_started(
                market=market,
                site_id=site_id,
                job_id=job_id,
                file_count=len(self.files_to_upload),
                total_size_mb=total_size_mb,
                dropbox_path=dropbox_path,
                content_type=content_type
            )
            
            bytes_uploaded = 0
            completed_count = 0
            
            # Use ThreadPoolExecutor for parallel uploads
            from config import PARALLEL_UPLOADS
            
            with ThreadPoolExecutor(max_workers=PARALLEL_UPLOADS) as executor:
                # Submit all upload tasks
                future_to_file = {}
                
                for file_path in self.files_to_upload:
                    file_name = os.path.basename(file_path)
                    # Use dropbox_path exactly as returned by Make.com
                    full_dropbox_path = f"{dropbox_path}/{file_name}"
                    
                    future = executor.submit(
                        self._upload_single_file,
                        file_path,
                        full_dropbox_path,
                        file_name
                    )
                    future_to_file[future] = (file_path, file_name)
                
                # Process completed uploads as they finish
                for future in as_completed(future_to_file):
                    file_path, file_name = future_to_file[future]
                    
                    try:
                        success = future.result()
                        completed_count += 1
                        
                        file_size = os.path.getsize(file_path)
                        
                        if success:
                            with self.upload_lock:
                                self.files_uploaded += 1
                                bytes_uploaded += file_size
                        else:
                            with self.upload_lock:
                                self.files_failed += 1
                            logger.error(f"Failed to upload: {file_name}")
                        
                        # Update progress UI
                        self.root.after(0, self._update_progress_parallel, 
                                      completed_count, len(self.files_to_upload),
                                      bytes_uploaded)
                        
                        # Send webhook progress update
                        progress_percent = int((completed_count / len(self.files_to_upload)) * 100)
                        if progress_percent - self.last_progress_update >= PROGRESS_UPDATE_THRESHOLD:
                            self.webhook_client.notify_upload_progress(
                                market=market,
                                site_id=site_id,
                                job_id=job_id,
                                progress_percent=progress_percent,
                                files_uploaded=self.files_uploaded,
                                files_remaining=len(self.files_to_upload) - completed_count,
                                content_type=content_type
                            )
                            self.last_progress_update = progress_percent
                    
                    except Exception as e:
                        logger.error(f"Error processing upload result: {e}")
                        with self.upload_lock:
                            self.files_failed += 1
                        completed_count += 1
            
            # Upload complete
            duration = int(time.time() - self.upload_start_time)
            
            if self.files_failed == 0:
                completion_result = self.webhook_client.notify_upload_complete(
                    market=market,
                    site_id=site_id,
                    job_id=job_id,
                    files_uploaded=self.files_uploaded,
                    total_size_mb=total_size_mb,
                    duration_seconds=duration,
                    dropbox_path=dropbox_path,
                    content_type=content_type
                )
                self.root.after(0, self._upload_complete_success, completion_result)
            else:
                self.webhook_client.notify_upload_failed(
                    market=market,
                    site_id=site_id,
                    job_id=job_id,
                    files_uploaded=self.files_uploaded,
                    files_failed=self.files_failed,
                    error_message=f"{self.files_failed} files failed to upload",
                    content_type=content_type
                )
                self.root.after(0, self._upload_complete_partial)
        
        except Exception as e:
            logger.error(f"Upload thread error: {e}")
            self.root.after(0, self._upload_failed, str(e))
    
    def _upload_single_file(self, local_path: str, dropbox_path: str, file_name: str) -> bool:
        """Upload a single file (called by thread pool)."""
        try:
            return self.dropbox_uploader.upload_file(
                local_path=local_path,
                dropbox_path=dropbox_path,
                progress_callback=None
            )
        except Exception as e:
            logger.error(f"Error uploading {file_name}: {e}")
            return False
    
    def _update_progress_parallel(self, completed: int, total_files: int, bytes_uploaded: int):
        """Update progress UI for parallel uploads."""
        progress = (completed / total_files) * 100
        self.progress_bar['value'] = progress
        
        with self.upload_lock:
            uploaded = self.files_uploaded
            failed = self.files_failed
        
        self.progress_label.config(
            text=f"File {completed} of {total_files} • {int(progress)}%"
        )
        
        elapsed = time.time() - self.upload_start_time
        if bytes_uploaded > 0 and elapsed > 0:
            speed = bytes_uploaded / elapsed
            remaining_bytes = self.total_size_bytes - bytes_uploaded
            eta = int(remaining_bytes / speed) if speed > 0 else 0
            
            from config import PARALLEL_UPLOADS
            self.detail_label.config(
                text=f"⚡ {format_bytes(int(speed))}/s • ETA: {format_time(eta)} • {PARALLEL_UPLOADS} parallel uploads"
            )
        
        self.status_label.config(
            text=f"Uploading... (✓ {uploaded} | ✗ {failed})",
            foreground='#007BFF'
        )
    
    def _upload_complete_success(self, completion_result: dict):
        """Handle successful upload completion."""
        self.upload_in_progress = False
        self.progress_bar['value'] = 100
        
        duration = int(time.time() - self.upload_start_time)
        avg_speed = self.total_size_bytes / duration if duration > 0 else 0
        next_steps = completion_result.get('next_steps', 'Photos will be processed shortly')
        
        from config import PARALLEL_UPLOADS
        
        self.status_label.config(text="✓ Upload Complete!", foreground='#28A745')
        self.detail_label.config(
            text=f"Uploaded {self.files_uploaded} files in {format_time(duration)} • Avg: {format_bytes(int(avg_speed))}/s"
        )
        
        messagebox.showinfo(
            "Upload Complete!",
            f"Successfully uploaded {self.files_uploaded} files\n\n"
            f"Time: {format_time(duration)}\n"
            f"Size: {format_bytes(self.total_size_bytes)}\n"
            f"Avg Speed: {format_bytes(int(avg_speed))}/s\n"
            f"Method: {PARALLEL_UPLOADS} parallel uploads\n\n"
            f"{next_steps}"
        )
        
        self._reset_ui()
    
    def _upload_complete_partial(self):
        """Handle partial upload completion."""
        self.upload_in_progress = False
        
        self.status_label.config(text="⚠ Upload Completed with Errors", foreground='#FFC107')
        self.detail_label.config(
            text=f"Uploaded: {self.files_uploaded} • Failed: {self.files_failed}"
        )
        
        messagebox.showwarning(
            "Partial Upload",
            f"Uploaded: {self.files_uploaded} files\n"
            f"Failed: {self.files_failed} files\n\n"
            f"Please check the logs and retry failed files."
        )
        
        self._reset_ui()
    
    def _upload_failed(self, error_msg: str):
        """Handle upload failure."""
        self.upload_in_progress = False
        
        self.status_label.config(text="✗ Upload Failed", foreground='#DC3545')
        self.detail_label.config(text=error_msg)
        
        messagebox.showerror("Upload Failed", f"Upload failed:\n\n{error_msg}")
        
        self._reset_ui()
    
    def _reset_ui(self):
        """Reset UI after upload."""
        self.upload_btn.config(state='disabled')
        self.select_folder_btn.config(state='normal')
        self.validate_btn.config(state='disabled')
        self.site_id_entry.config(state='normal')
        self.market_combo.config(state='readonly')
        
        self.selected_folder = None
        self.files_to_upload = []
        self.validated_site_info = None
        self.site_id_var.set("")
        self.folder_label.config(text="No folder selected", foreground='#6C757D')
        self.file_info_label.config(text="")
        self.site_status_label.config(text="")
        
        self.progress_bar['value'] = 0
        self.progress_label.config(text="")
        self.status_label.config(text="")
        self.detail_label.config(text="")

def main():
    """Main entry point with error handling."""
    try:
        root = tk.Tk()
        app = PhotoUploaderApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"Fatal Error:\n\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        
        # Try to show error in messagebox
        try:
            import tkinter.messagebox as mb
            root = tk.Tk()
            root.withdraw()
            mb.showerror("SnapFlow - Fatal Error", error_msg)
        except:
            pass
        
        # Keep window open to see error
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()