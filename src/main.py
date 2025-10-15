"""
Photographer Photo Uploader - Main Application
Desktop app for uploading photos to Dropbox via Make.com workflow.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
import logging
from pathlib import Path
from typing import Optional

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dropbox_uploader import DropboxUploader
from webhook_client import MakeWebhookClient
from utils import (
    setup_logging, format_bytes, format_time, 
    scan_folder, extract_site_id_from_folder, validate_site_id
)
from config import PROGRESS_UPDATE_THRESHOLD

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

class PhotoUploaderApp:
    """Main application window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Photo Uploader")
        self.root.geometry("680x820")
        self.root.resizable(False, False)
        
        # Configure styles
        self._configure_styles()
        
        # State variables
        self.photographer_id = self._load_photographer_id()
        self.selected_folder = None
        self.files_to_upload = []
        self.total_size_bytes = 0
        self.upload_in_progress = False
        
        # Upload tracking
        self.files_uploaded = 0
        self.files_failed = 0
        self.upload_start_time = None
        self.last_progress_update = 0
        
        # Validated site info
        self.validated_site_info = None
        
        # Initialize clients
        self.webhook_client = None
        self.dropbox_uploader = None
        
        self._create_widgets()
        self._check_photographer_id()
    
    def _configure_styles(self):
        """Configure custom styles for better UI."""
        style = ttk.Style()
        
        # Configure button styles
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))
        
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
    
    def _prompt_photographer_id(self):
        """Show dialog to enter photographer ID."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Photographer ID Required")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Enter Your Photographer ID:", 
                 font=('Arial', 11)).pack(pady=20)
        
        id_entry = ttk.Entry(dialog, width=30, font=('Arial', 10))
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
                messagebox.showwarning("Invalid Input", "Please enter a photographer ID")
        
        ttk.Button(dialog, text="Save", command=save_id).pack(pady=10)
        
        dialog.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
    
    def _initialize_clients(self):
        """Initialize webhook and Dropbox clients."""
        try:
            self.webhook_client = MakeWebhookClient(self.photographer_id)
            self.photographer_label.config(text=f"Photographer: {self.photographer_id}")
            logger.info(f"Initialized for photographer: {self.photographer_id}")
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            self._show_notification(f"⚠️ Initialization Error\n{str(e)}", "error")
    
    def _create_widgets(self):
        """Create UI widgets."""
        # Header
        header_frame = ttk.Frame(self.root, padding=15)
        header_frame.pack(fill=tk.X)
        
        ttk.Label(header_frame, text="📸 Photo Uploader", 
                 font=('Arial', 16, 'bold')).pack()
        
        self.photographer_label = ttk.Label(header_frame, text="", 
                                           font=('Arial', 9))
        self.photographer_label.pack()
        
        # Site ID Section
        site_frame = ttk.LabelFrame(self.root, text="1. Site ID", padding=12)
        site_frame.pack(fill=tk.X, padx=20, pady=8)
        
        input_frame = ttk.Frame(site_frame)
        input_frame.pack(fill=tk.X)
        
        ttk.Label(input_frame, text="Site ID:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.site_id_var = tk.StringVar()
        self.site_id_var.trace('w', lambda *args: self._check_validation_ready())
        self.site_id_entry = ttk.Entry(input_frame, textvariable=self.site_id_var, 
                                       width=20, font=('Arial', 11))
        self.site_id_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        self.validate_btn = ttk.Button(input_frame, text="Validate", 
                                       command=self._validate_site, state='disabled')
        self.validate_btn.pack(side=tk.LEFT)
        
        self.site_status_label = ttk.Label(site_frame, text="", 
                                          font=('Arial', 9))
        self.site_status_label.pack(pady=(10, 0))
        
        # Folder Selection Section
        folder_frame = ttk.LabelFrame(self.root, text="2. Select Photos", padding=12)
        folder_frame.pack(fill=tk.X, padx=20, pady=8)
        
        self.select_folder_btn = ttk.Button(folder_frame, text="📁 Select Folder", 
                                           command=self._select_folder, state='normal')
        self.select_folder_btn.pack()
        
        self.folder_label = ttk.Label(folder_frame, text="No folder selected", 
                                     font=('Arial', 9), foreground='gray')
        self.folder_label.pack(pady=(10, 0))
        
        self.file_info_label = ttk.Label(folder_frame, text="", 
                                        font=('Arial', 9))
        self.file_info_label.pack(pady=(5, 0))
        
        # Photo Type and Notes Section
        info_frame = ttk.LabelFrame(self.root, text="Photo Details", padding=12)
        info_frame.pack(fill=tk.X, padx=20, pady=8)
        
        # Photo Type dropdown
        type_frame = ttk.Frame(info_frame)
        type_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(type_frame, text="Photo Type:", font=('Arial', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.photo_type_var = tk.StringVar(value="Daytime")
        photo_types = ["Daytime", "Real Time Twilight", "Lifestyle"]
        self.photo_type_combo = ttk.Combobox(type_frame, 
                                             textvariable=self.photo_type_var,
                                             values=photo_types,
                                             state='readonly',
                                             width=25,
                                             font=('Arial', 10))
        self.photo_type_combo.pack(side=tk.LEFT)
        
        # Notes field
        notes_label_frame = ttk.Frame(info_frame)
        notes_label_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(notes_label_frame, text="Notes (optional):", font=('Arial', 10)).pack(side=tk.LEFT)
        
        # Rich text field for notes
        self.notes_text = scrolledtext.ScrolledText(info_frame, 
                                                    height=4, 
                                                    width=60,
                                                    font=('Arial', 10),
                                                    wrap=tk.WORD,
                                                    relief=tk.SOLID,
                                                    borderwidth=1)
        self.notes_text.pack(fill=tk.BOTH, expand=True)
        
        # Upload Section (Notification Center)
        upload_frame = ttk.LabelFrame(self.root, text="3. Upload", padding=12)
        upload_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)
        
        self.upload_btn = ttk.Button(upload_frame, text="🚀 Start Upload", 
                                     command=self._start_upload, 
                                     state='disabled',
                                     style='Action.TButton')
        self.upload_btn.pack(pady=(0, 10))
        
        # Notification Card with scrollable content
        self.notification_card = tk.Frame(upload_frame, 
                                         relief=tk.FLAT, 
                                         borderwidth=2,
                                         bg='#f0f0f0',
                                         highlightthickness=1,
                                         highlightbackground='#d0d0d0',
                                         height=160)
        self.notification_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.notification_card.pack_propagate(False)  # Prevent shrinking
        
        # Create canvas for scrollable notification
        self.notification_canvas = tk.Canvas(self.notification_card, 
                                            bg='#f0f0f0',
                                            highlightthickness=0)
        self.notification_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar for notification (only shows when needed)
        self.notification_scrollbar = ttk.Scrollbar(self.notification_card, 
                                                   orient=tk.VERTICAL,
                                                   command=self.notification_canvas.yview)
        
        self.notification_canvas.configure(yscrollcommand=self.notification_scrollbar.set)
        
        # Frame inside canvas for content
        self.notification_content_frame = tk.Frame(self.notification_canvas, bg='#f0f0f0')
        self.notification_canvas_window = self.notification_canvas.create_window(
            (0, 0), 
            window=self.notification_content_frame, 
            anchor='nw',
            width=600
        )
        
        # Notification label
        self.notification_label = tk.Label(self.notification_content_frame, 
                                          text="Ready to upload photos", 
                                          font=('Arial', 10),
                                          bg='#f0f0f0',
                                          fg='#666666',
                                          wraplength=580,
                                          justify=tk.LEFT,
                                          anchor='nw',
                                          padx=15,
                                          pady=15)
        self.notification_label.pack(fill=tk.BOTH, expand=True)
        
        # Bind canvas resize
        self.notification_content_frame.bind('<Configure>', self._on_notification_configure)
        
        # Progress Section (compact)
        progress_container = ttk.Frame(upload_frame)
        progress_container.pack(fill=tk.X)
        
        self.progress_label = ttk.Label(progress_container, text="", 
                                       font=('Arial', 9))
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(progress_container, length=600, 
                                           mode='determinate')
        self.progress_bar.pack(pady=5)
        
        self.status_label = ttk.Label(progress_container, text="", 
                                     font=('Arial', 9), foreground='blue')
        self.status_label.pack()
        
        self.detail_label = ttk.Label(progress_container, text="", 
                                     font=('Arial', 8), foreground='gray')
        self.detail_label.pack(pady=(3, 0))
    
    def _get_notes(self) -> str:
        """Get notes from text widget."""
        return self.notes_text.get("1.0", tk.END).strip()
    
    def _get_photo_type(self) -> str:
        """Get selected photo type."""
        return self.photo_type_var.get()
    
    def _on_notification_configure(self, event=None):
        """Update scroll region when notification content changes."""
        self.notification_canvas.configure(scrollregion=self.notification_canvas.bbox("all"))
        
        # Show/hide scrollbar based on content height
        content_height = self.notification_content_frame.winfo_reqheight()
        canvas_height = self.notification_canvas.winfo_height()
        
        if content_height > canvas_height:
            self.notification_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            self.notification_scrollbar.pack_forget()
    
    def _show_notification(self, message: str, notification_type: str = "info"):
        """
        Display notification in section 3 with proper styling.
        
        Types: success, error, warning, info, progress
        """
        # Color scheme based on notification type
        colors = {
            'success': {'bg': '#d4edda', 'fg': '#155724', 'border': '#c3e6cb'},
            'error': {'bg': '#f8d7da', 'fg': '#721c24', 'border': '#f5c6cb'},
            'warning': {'bg': '#fff3cd', 'fg': '#856404', 'border': '#ffeaa7'},
            'info': {'bg': '#d1ecf1', 'fg': '#0c5460', 'border': '#bee5eb'},
            'progress': {'bg': '#cfe2ff', 'fg': '#084298', 'border': '#b6d4fe'}
        }
        
        style = colors.get(notification_type, colors['info'])
        
        # Update card styling
        self.notification_card.config(
            bg=style['bg'],
            highlightbackground=style['border']
        )
        
        # Update canvas styling
        self.notification_canvas.config(bg=style['bg'])
        
        # Update content frame styling
        self.notification_content_frame.config(bg=style['bg'])
        
        # Update notification label
        self.notification_label.config(
            text=message,
            fg=style['fg'],
            bg=style['bg'],
            font=('Arial', 10)
        )
        
        # Reset scroll position to top
        self.notification_canvas.yview_moveto(0)
        
        # Update scroll region
        self.root.update_idletasks()
        self._on_notification_configure()
    
    def _clear_notification(self):
        """Clear notification area to default state."""
        self._show_notification("Ready to upload photos", "info")
    
    def _check_validation_ready(self):
        """Check if validation can be enabled."""
        site_id = self.site_id_var.get().strip().upper()
        has_valid_site_id = validate_site_id(site_id)
        has_folder = self.selected_folder is not None and len(self.files_to_upload) > 0
        
        # Enable validate button only if both site ID and folder are ready
        if has_valid_site_id and has_folder:
            self.validate_btn.config(state='normal')
        else:
            self.validate_btn.config(state='disabled')
    
    def _validate_site(self):
        """Validate site ID with Make webhook."""
        site_id = self.site_id_var.get().strip().upper()
        
        if not validate_site_id(site_id):
            self._show_notification("⚠️ Invalid Site ID\n\nPlease enter a valid site ID to continue.", "warning")
            return
        
        if not self.selected_folder or not self.files_to_upload:
            self._show_notification("⚠️ No Folder Selected\n\nPlease select a photo folder before validating.", "warning")
            return
        
        self.validate_btn.config(state='disabled')
        self.site_status_label.config(text="Validating...", foreground='blue')
        self._show_notification("🔄 Validating Site ID\n\nPlease wait while we verify your site information...", "progress")
        
        # Run validation in thread
        thread = threading.Thread(target=self._validate_site_thread, args=(site_id,))
        thread.daemon = True
        thread.start()
    
    def _validate_site_thread(self, site_id: str):
        """Validate site in background thread."""
        try:
            total_size_mb = self.total_size_bytes / (1024 * 1024)
            photo_type = self._get_photo_type()
            notes = self._get_notes()
            
            logger.info(f"Sending validation request for site {site_id}")
            logger.info(f"Webhook URL: {self.webhook_client.webhook_url}")
            logger.info(f"File count: {len(self.files_to_upload)}, Size: {total_size_mb:.2f} MB")
            logger.info(f"Photo type: {photo_type}, Notes: {notes[:50] if notes else 'None'}")
            
            result = self.webhook_client.validate_site(
                site_id=site_id,
                file_count=len(self.files_to_upload),
                total_size_mb=total_size_mb,
                photo_type=photo_type,
                notes=notes
            )
            
            logger.info(f"Validation result: {result}")
            
            self.root.after(0, self._handle_validation_result, result)
        
        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            self.root.after(0, self._handle_validation_result, {
                'success': False,
                'error': str(e)
            })
    
    def _handle_validation_result(self, result: dict):
        """Handle validation result in main thread."""
        self._check_validation_ready()  # Re-enable button based on state
        
        if result.get('success'):
            self.validated_site_info = result
            
            # Display in Section 1 (Site ID)
            status_text = (f"✓ {result['client_name']}\n"
                          f"   {result['property_address']}")
            self.site_status_label.config(text=status_text, foreground='green')
            
            # Display in Section 3 (Upload) - NO POPUP
            photo_type = self._get_photo_type()
            notification = (
                f"✅ Site Validated Successfully\n\n"
                f"Client: {result['client_name']}\n"
                f"Address: {result['property_address']}\n"
                f"Job ID: {result.get('job_id', 'N/A')}\n"
                f"Photo Type: {photo_type}\n\n"
                f"📦 Ready to upload {len(self.files_to_upload)} files "
                f"({format_bytes(self.total_size_bytes)})\n\n"
                f"Click 'Start Upload' to begin"
            )
            self._show_notification(notification, "success")
            
            self.upload_btn.config(state='normal')
        else:
            # Display error in Section 3 - NO POPUP
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            self.site_status_label.config(text=f"✗ Validation failed", 
                                        foreground='red')
            
            notification = f"❌ Validation Failed\n\n{error_msg}\n\nPlease check the site ID and try again."
            self._show_notification(notification, "error")
    
    def _select_folder(self):
        """Select folder containing photos."""
        folder_path = filedialog.askdirectory(title="Select Photo Folder")
        
        if folder_path:
            self.selected_folder = folder_path
            folder_name = os.path.basename(folder_path)
            
            # Site ID auto-fill disabled - user must enter manually
            
            try:
                self.files_to_upload, self.total_size_bytes = scan_folder(folder_path)
                
                if not self.files_to_upload:
                    self._show_notification(
                        "⚠️ No Valid Files Found\n\n"
                        "No valid photo files were found in the selected folder.\n"
                        "Please select a folder containing photos.", 
                        "warning"
                    )
                    self.selected_folder = None
                    return
                
                self.folder_label.config(text=folder_name, foreground='black')
                self.file_info_label.config(
                    text=f"{len(self.files_to_upload)} files • {format_bytes(self.total_size_bytes)}"
                )
                
                # Show folder selected notification
                self._show_notification(
                    f"📁 Folder Selected\n\n"
                    f"Found {len(self.files_to_upload)} files\n"
                    f"Total size: {format_bytes(self.total_size_bytes)}\n\n"
                    f"Next: Enter Site ID and click Validate",
                    "info"
                )
                
                # Check if validation can be enabled
                self._check_validation_ready()
                
                logger.info(f"Folder selected: {folder_name} ({len(self.files_to_upload)} files)")
                
            except Exception as e:
                logger.error(f"Error scanning folder: {e}", exc_info=True)
                self._show_notification(
                    f"❌ Folder Scan Error\n\n{str(e)}\n\nPlease try selecting a different folder.", 
                    "error"
                )
                self.selected_folder = None
    
    def _start_upload(self):
        """Start upload process."""
        if not self.validated_site_info:
            self._show_notification("⚠️ Not Validated\n\nPlease validate the site ID first.", "warning")
            return
        
        if self.upload_in_progress:
            return
        
        # Get photo details
        photo_type = self._get_photo_type()
        notes = self._get_notes()
        
        # Build confirmation message
        confirm_msg = (
            f"Upload {len(self.files_to_upload)} files to:\n\n"
            f"{self.validated_site_info['client_name']}\n"
            f"{self.validated_site_info['property_address']}\n\n"
            f"Photo Type: {photo_type}\n"
            f"Total size: {format_bytes(self.total_size_bytes)}"
        )
        
        if notes:
            confirm_msg += f"\n\nNotes: {notes[:100]}{'...' if len(notes) > 100 else ''}"
        
        confirm_msg += "\n\nContinue?"
        
        # KEEP: Upload confirmation dialog
        confirm = messagebox.askyesno("Confirm Upload", confirm_msg)
        
        if not confirm:
            return
        
        # Disable controls
        self.upload_btn.config(state='disabled')
        self.select_folder_btn.config(state='disabled')
        self.validate_btn.config(state='disabled')
        self.site_id_entry.config(state='disabled')
        self.photo_type_combo.config(state='disabled')
        self.notes_text.config(state='disabled')
        
        self.upload_in_progress = True
        self.files_uploaded = 0
        self.files_failed = 0
        self.upload_start_time = time.time()
        self.last_progress_update = 0
        
        # Show upload starting
        self._show_notification(
            "🚀 Upload Starting\n\nInitializing upload process...", 
            "progress"
        )
        
        # Start upload thread
        thread = threading.Thread(target=self._upload_thread)
        thread.daemon = True
        thread.start()
    
    def _upload_thread(self):
        """Upload files in background thread."""
        try:
            # Initialize Dropbox uploader
            self.dropbox_uploader = DropboxUploader()
            
            site_id = self.site_id_var.get().strip().upper()
            job_id = self.validated_site_info['job_id']
            dropbox_base_path = self.validated_site_info['dropbox_path']
            total_size_mb = self.total_size_bytes / (1024 * 1024)
            photo_type = self._get_photo_type()
            notes = self._get_notes()
            
            # Notify upload started
            self.webhook_client.notify_upload_started(
                site_id=site_id,
                job_id=job_id,
                file_count=len(self.files_to_upload),
                total_size_mb=total_size_mb,
                dropbox_path=dropbox_base_path,
                photo_type=photo_type,
                notes=notes
            )
            
            # Update notification
            self.root.after(0, self._show_notification, 
                          f"📤 Uploading Files\n\n"
                          f"Uploading {len(self.files_to_upload)} {photo_type} photos to Dropbox...\n"
                          f"Please do not close the application.", 
                          "progress")
            
            # Upload each file
            bytes_uploaded = 0
            
            for i, file_path in enumerate(self.files_to_upload):
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                
                # Build Dropbox path
                dropbox_path = f"{dropbox_base_path}/{file_name}"
                
                # Update UI
                self.root.after(0, self._update_progress, 
                              i + 1, len(self.files_to_upload),
                              bytes_uploaded, self.total_size_bytes,
                              f"Uploading: {file_name}")
                
                # Upload file
                success = self.dropbox_uploader.upload_file(
                    local_path=file_path,
                    dropbox_path=dropbox_path,
                    progress_callback=lambda current, total: None
                )
                
                if success:
                    self.files_uploaded += 1
                    bytes_uploaded += file_size
                else:
                    self.files_failed += 1
                    logger.error(f"Failed to upload: {file_name}")
                
                # Send progress update to webhook (every 25%)
                progress_percent = int((self.files_uploaded / len(self.files_to_upload)) * 100)
                if progress_percent - self.last_progress_update >= PROGRESS_UPDATE_THRESHOLD:
                    self.webhook_client.notify_upload_progress(
                        site_id=site_id,
                        job_id=job_id,
                        progress_percent=progress_percent,
                        files_uploaded=self.files_uploaded,
                        files_remaining=len(self.files_to_upload) - self.files_uploaded
                    )
                    self.last_progress_update = progress_percent
            
            # Upload complete
            duration = int(time.time() - self.upload_start_time)
            
            if self.files_failed == 0:
                # All files uploaded successfully
                completion_result = self.webhook_client.notify_upload_complete(
                    site_id=site_id,
                    job_id=job_id,
                    files_uploaded=self.files_uploaded,
                    total_size_mb=total_size_mb,
                    duration_seconds=duration,
                    dropbox_path=dropbox_base_path,
                    photo_type=photo_type,
                    notes=notes
                )
                
                self.root.after(0, self._upload_complete_success, completion_result)
            else:
                # Some files failed
                self.webhook_client.notify_upload_failed(
                    site_id=site_id,
                    job_id=job_id,
                    files_uploaded=self.files_uploaded,
                    files_failed=self.files_failed,
                    error_message=f"{self.files_failed} files failed to upload"
                )
                
                self.root.after(0, self._upload_complete_partial)
        
        except Exception as e:
            logger.error(f"Upload thread error: {e}", exc_info=True)
            self.root.after(0, self._upload_failed, str(e))
    
    def _update_progress(self, current_file: int, total_files: int,
                        bytes_uploaded: int, total_bytes: int, status: str):
        """Update progress UI."""
        progress = (current_file / total_files) * 100
        self.progress_bar['value'] = progress
        
        self.progress_label.config(
            text=f"File {current_file} of {total_files} • {int(progress)}%"
        )
        
        elapsed = int(time.time() - self.upload_start_time)
        if bytes_uploaded > 0:
            speed = bytes_uploaded / elapsed if elapsed > 0 else 0
            remaining_bytes = total_bytes - bytes_uploaded
            eta = int(remaining_bytes / speed) if speed > 0 else 0
            
            self.detail_label.config(
                text=f"Speed: {format_bytes(int(speed))}/s • ETA: {format_time(eta)}"
            )
        
        self.status_label.config(text=status)
    
    def _upload_complete_success(self, completion_result: dict):
        """Handle successful upload completion - NO POPUP."""
        self.upload_in_progress = False
        self.progress_bar['value'] = 100
        
        duration = int(time.time() - self.upload_start_time)
        avg_speed = self.total_size_bytes / duration if duration > 0 else 0
        
        next_steps = completion_result.get('next_steps', 
                                          'Photos will be processed shortly')
        
        self.status_label.config(text="✓ Upload Complete!", foreground='green')
        self.detail_label.config(
            text=f"Completed in {format_time(duration)} • Avg speed: {format_bytes(int(avg_speed))}/s"
        )
        
        # Display in Section 3 - NO POPUP
        notification = (
            f"✅ Upload Complete!\n\n"
            f"Successfully uploaded {self.files_uploaded} files\n"
            f"Total size: {format_bytes(self.total_size_bytes)}\n"
            f"Duration: {format_time(duration)}\n"
            f"Average speed: {format_bytes(int(avg_speed))}/s\n\n"
            f"📋 {next_steps}"
        )
        self._show_notification(notification, "success")
        
        self._reset_ui()
    
    def _upload_complete_partial(self):
        """Handle partial upload completion - NO POPUP."""
        self.upload_in_progress = False
        
        duration = int(time.time() - self.upload_start_time)
        
        self.status_label.config(text="⚠ Upload Completed with Errors", 
                               foreground='orange')
        self.detail_label.config(
            text=f"Uploaded: {self.files_uploaded} • Failed: {self.files_failed}"
        )
        
        # Display in Section 3 - NO POPUP
        notification = (
            f"⚠️ Partial Upload\n\n"
            f"✓ Successfully uploaded: {self.files_uploaded} files\n"
            f"✗ Failed to upload: {self.files_failed} files\n"
            f"Duration: {format_time(duration)}\n\n"
            f"Please check the application logs (uploader.log) for details about failed files.\n"
            f"You may need to retry uploading the failed files."
        )
        self._show_notification(notification, "warning")
        
        self._reset_ui()
    
    def _upload_failed(self, error_msg: str):
        """Handle upload failure - NO POPUP."""
        self.upload_in_progress = False
        
        self.status_label.config(text="✗ Upload Failed", foreground='red')
        self.detail_label.config(text=error_msg[:100])
        
        # Display in Section 3 - NO POPUP
        notification = (
            f"❌ Upload Failed\n\n"
            f"An error occurred during the upload process:\n\n"
            f"{error_msg}\n\n"
            f"Please check your internet connection and try again.\n"
            f"Check uploader.log for detailed error information."
        )
        self._show_notification(notification, "error")
        
        self._reset_ui()
    
    def _reset_ui(self):
        """Reset UI after upload."""
        self.upload_btn.config(state='disabled')
        self.select_folder_btn.config(state='normal')
        self.site_id_entry.config(state='normal')
        self.photo_type_combo.config(state='readonly')
        self.notes_text.config(state='normal')
        
        # Clear selection
        self.selected_folder = None
        self.files_to_upload = []
        self.validated_site_info = None
        self.site_id_var.set("")
        self.photo_type_var.set("Daytime")
        self.notes_text.delete("1.0", tk.END)
        self.folder_label.config(text="No folder selected", foreground='gray')
        self.file_info_label.config(text="")
        self.site_status_label.config(text="")
        
        # Re-check validation state
        self._check_validation_ready()

def main():
    """Main entry point."""
    root = tk.Tk()
    app = PhotoUploaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()