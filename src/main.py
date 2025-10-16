"""
Photographer Photo Uploader - FINAL VERSION
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

class PhotoUploaderApp:
    """Main application window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Photo Uploader")
        self.root.geometry("700x650")
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
        
        # HEADER
        header_frame = ttk.Frame(self.root, padding=15)
        header_frame.pack(fill=tk.X)
        
        ttk.Label(header_frame, text="📸 Photo Uploader", 
                 font=('Arial', 16, 'bold')).pack()
        
        self.photographer_label = ttk.Label(header_frame, text="Loading...", 
                                           font=('Arial', 9))
        self.photographer_label.pack()
        
        # TWO-COLUMN ROW: MARKET (40%) + PHOTOS (60%)
        top_row_frame = ttk.Frame(self.root, padding=(20, 10))
        top_row_frame.pack(fill=tk.X)
        
        # LEFT COLUMN: MARKET (40%)
        market_frame = ttk.LabelFrame(top_row_frame, text="Select Market", padding=15)
        market_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
        market_frame.config(width=250)
        
        ttk.Label(market_frame, text="Market:").pack(anchor=tk.W, pady=(0, 5))
        
        self.market_combo = ttk.Combobox(market_frame, 
                                        textvariable=self.selected_market,
                                        width=20, state='disabled', font=('Arial', 10))
        self.market_combo.pack(fill=tk.X)
        self.market_combo.bind('<<ComboboxSelected>>', self._on_market_changed)
        
        # RIGHT COLUMN: PHOTOS (60%)
        folder_frame = ttk.LabelFrame(top_row_frame, text="Select Photos", padding=15)
        folder_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.select_folder_btn = ttk.Button(folder_frame, text="📁 Select Folder", 
                                           command=self._select_folder)
        self.select_folder_btn.pack(pady=(0, 10))
        
        self.folder_label = ttk.Label(folder_frame, text="No folder selected", 
                                     font=('Arial', 9), foreground='gray')
        self.folder_label.pack(anchor=tk.W)
        
        self.file_info_label = ttk.Label(folder_frame, text="", 
                                        font=('Arial', 9), foreground='blue')
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
        
        ttk.Radiobutton(radio_frame, text="Video", 
                       variable=self.content_type, value="video",
                       command=self._on_content_type_changed).pack(side=tk.LEFT)
        
        self.content_info_label = ttk.Label(content_frame, text="Standard daytime photos for automated processing", 
                                           font=('Arial', 8), foreground='gray')
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
                                       width=25, font=('Arial', 11))
        self.site_id_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        self.validate_btn = ttk.Button(input_frame, text="Validate", 
                                       command=self._validate_site, state='disabled')
        self.validate_btn.pack(side=tk.LEFT)
        
        self.site_status_label = ttk.Label(site_frame, text="", 
                                          font=('Arial', 9), wraplength=600)
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
                                       font=('Arial', 9))
        self.progress_label.pack()
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(upload_frame, length=620, 
                                           mode='determinate')
        self.progress_bar.pack(pady=10)
        
        # Status messages
        self.status_label = ttk.Label(upload_frame, text="", 
                                     font=('Arial', 9), foreground='blue')
        self.status_label.pack()
        
        self.detail_label = ttk.Label(upload_frame, text="", 
                                     font=('Arial', 8), foreground='gray')
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
        self.site_status_label.config(text="Validating...", foreground='blue')
        
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
            self.site_status_label.config(text=status_text, foreground='green')
            
            self.upload_btn.config(state='normal')
            
            messagebox.showinfo("Site Validated", 
                              f"Ready to upload to:\n\n"
                              f"{result['client_name']}\n"
                              f"{result['property_address']}")
        else:
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            self.site_status_label.config(text=f"✗ {error_msg}", 
                                        foreground='red')
            messagebox.showerror("Validation Failed", error_msg)
    
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
                
                self.folder_label.config(text=folder_name, foreground='black')
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
            foreground='blue'
        )
    
    def _upload_complete_success(self, completion_result: dict):
        """Handle successful upload completion."""
        self.upload_in_progress = False
        self.progress_bar['value'] = 100
        
        duration = int(time.time() - self.upload_start_time)
        avg_speed = self.total_size_bytes / duration if duration > 0 else 0
        next_steps = completion_result.get('next_steps', 'Photos will be processed shortly')
        
        from config import PARALLEL_UPLOADS
        
        self.status_label.config(text="✓ Upload Complete!", foreground='green')
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
        
        self.status_label.config(text="⚠ Upload Completed with Errors", foreground='orange')
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
        
        self.status_label.config(text="✗ Upload Failed", foreground='red')
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
        self.folder_label.config(text="No folder selected", foreground='gray')
        self.file_info_label.config(text="")
        self.site_status_label.config(text="")
        
        self.progress_bar['value'] = 0
        self.progress_label.config(text="")
        self.status_label.config(text="")
        self.detail_label.config(text="")

def main():
    """Main entry point."""
    root = tk.Tk()
    app = PhotoUploaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()