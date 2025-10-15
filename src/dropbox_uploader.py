"""
Dropbox Team uploader using admin access.
Based on the provided teamaccount.py reference script.
"""

import os
import logging
from typing import Optional, Callable
import dropbox
from dropbox.files import CommitInfo, UploadSessionCursor, WriteMode
from dropbox.exceptions import ApiError, AuthError
import dropbox.common
from config import get_dropbox_credentials, CHUNK_SIZE, MAX_RETRIES

logger = logging.getLogger(__name__)

class DropboxUploader:
    """Manages Dropbox Team uploads via admin access."""
    
    def __init__(self):
        self.credentials = get_dropbox_credentials()
        self.dbx_team = None
        self.dbx_admin = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Dropbox Team client and admin access."""
        try:
            # Initialize team client
            self.dbx_team = dropbox.DropboxTeam(
                app_key=self.credentials['app_key'],
                app_secret=self.credentials['app_secret'],
                oauth2_refresh_token=self.credentials['refresh_token']
            )
            
            logger.info("DropboxTeam client initialized successfully")
            
            # Get admin ID and initialize admin client
            admin_id = self._get_first_admin_id()
            if not admin_id:
                raise ValueError("Could not find an active admin ID")
            
            self.dbx_admin = self.dbx_team.as_admin(admin_id)
            
            # Root to team namespace (from reference script)
            root_ns_id = self.dbx_admin.users_get_current_account().root_info.root_namespace_id
            self.dbx_admin = self.dbx_admin.with_path_root(
                dropbox.common.PathRoot.root(root_ns_id)
            )
            
            logger.info(f"Admin client initialized with ID: {admin_id}")
            
        except AuthError as e:
            logger.error(f"Authentication failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise
    
    def _get_first_admin_id(self) -> Optional[str]:
        """
        Find the first active team admin ID.
        Based on the reference script's get_first_admin_id function.
        """
        logger.info("Searching for active admin...")
        
        try:
            result = self.dbx_team.team_members_list(limit=100)
            
            while True:
                for member in result.members:
                    if member.profile.status.is_active() and member.role.is_team_admin():
                        admin_id = member.profile.team_member_id
                        logger.info(f"Found admin ID: {admin_id}")
                        return admin_id
                
                if not result.has_more:
                    break
                
                result = self.dbx_team.team_members_list_continue(result.cursor)
        
        except ApiError as e:
            logger.error(f"Error finding admin: {e}")
            return None
        
        logger.error("No active admin found")
        return None
    
    def upload_file(self, local_path: str, dropbox_path: str, 
                   progress_callback: Optional[Callable] = None) -> bool:
        """
        Upload a single file using chunked session upload.
        
        Args:
            local_path: Path to local file
            dropbox_path: Target path in Dropbox
            progress_callback: Optional callback(bytes_uploaded, total_bytes)
        
        Returns:
            True if successful, False otherwise
        """
        file_size = os.path.getsize(local_path)
        
        for attempt in range(MAX_RETRIES):
            try:
                with open(local_path, 'rb') as f:
                    if file_size <= CHUNK_SIZE:
                        # Small file - single upload
                        self.dbx_admin.files_upload(
                            f.read(),
                            dropbox_path,
                            mode=WriteMode.add
                        )
                        
                        if progress_callback:
                            progress_callback(file_size, file_size)
                        
                        logger.info(f"Uploaded (single): {os.path.basename(local_path)}")
                        return True
                    
                    else:
                        # Large file - chunked upload
                        return self._upload_chunked(f, dropbox_path, file_size, progress_callback)
            
            except ApiError as e:
                if 'not_found' in str(e):
                    logger.error(f"Path not found: {dropbox_path}")
                    return False
                
                logger.warning(f"Upload attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"Failed to upload after {MAX_RETRIES} attempts")
                    return False
            
            except Exception as e:
                logger.error(f"Unexpected error uploading {local_path}: {e}")
                return False
        
        return False
    
    def _upload_chunked(self, file_obj, dropbox_path: str, file_size: int,
                       progress_callback: Optional[Callable] = None) -> bool:
        """Upload large file in chunks."""
        try:
            # Start upload session
            chunk = file_obj.read(CHUNK_SIZE)
            session_start = self.dbx_admin.files_upload_session_start(chunk)
            
            cursor = UploadSessionCursor(
                session_id=session_start.session_id,
                offset=file_obj.tell()
            )
            
            if progress_callback:
                progress_callback(file_obj.tell(), file_size)
            
            # Upload remaining chunks
            while file_obj.tell() < file_size:
                chunk = file_obj.read(CHUNK_SIZE)
                
                if file_obj.tell() < file_size:
                    # More chunks to come
                    self.dbx_admin.files_upload_session_append_v2(chunk, cursor)
                    cursor.offset = file_obj.tell()
                else:
                    # Final chunk
                    commit = CommitInfo(
                        path=dropbox_path,
                        mode=WriteMode.add
                    )
                    self.dbx_admin.files_upload_session_finish(chunk, cursor, commit)
                
                if progress_callback:
                    progress_callback(file_obj.tell(), file_size)
            
            logger.info(f"Uploaded (chunked): {os.path.basename(dropbox_path)}")
            return True
        
        except Exception as e:
            logger.error(f"Chunked upload failed: {e}")
            return False
    
    def create_folder(self, folder_path: str) -> bool:
        """Create a folder in Dropbox (if it doesn't exist)."""
        try:
            self.dbx_admin.files_create_folder_v2(folder_path)
            logger.info(f"Created folder: {folder_path}")
            return True
        except ApiError as e:
            if 'conflict' in str(e):
                logger.info(f"Folder already exists: {folder_path}")
                return True
            logger.error(f"Failed to create folder: {e}")
            return False