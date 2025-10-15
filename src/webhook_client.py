"""
Make.com webhook client with improved error handling and debugging.
"""

import requests
import logging
from typing import Dict, Any
from datetime import datetime
from config import WEBHOOK_URL

logger = logging.getLogger(__name__)

class MakeWebhookClient:
    """Handles all communication with Make.com webhook."""
    
    TIMEOUT = 30  # Increased timeout to 30 seconds
    
    def __init__(self, photographer_id: str):
        self.photographer_id = photographer_id
        self.webhook_url = WEBHOOK_URL
        logger.info(f"Webhook client initialized for photographer: {photographer_id}")
        logger.info(f"Webhook URL: {self.webhook_url}")
    
    def validate_site(self, site_id: str, file_count: int, total_size_mb: float,
                     photo_type: str = "", location: str = "", notes: str = "") -> Dict[str, Any]:
        """
        Validate site ID and get Dropbox upload path.
        
        Returns:
            {
                'success': bool,
                'dropbox_path': str,
                'client_name': str,
                'property_address': str,
                'job_id': str,
                'error': str (if failed)
            }
        """
        payload = {
            "action": "validate_site",
            "site_id": site_id,
            "photographer_id": self.photographer_id,
            "file_count": file_count,
            "total_size_mb": round(total_size_mb, 2),
            "photo_type": photo_type,
            "location": location,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        try:
            logger.info(f"=== VALIDATION REQUEST ===")
            logger.info(f"Site ID: {site_id}")
            logger.info(f"Photographer ID: {self.photographer_id}")
            logger.info(f"File count: {file_count}")
            logger.info(f"Total size: {total_size_mb:.2f} MB")
            logger.info(f"Photo type: {photo_type}")
            logger.info(f"Location: {location}")
            logger.info(f"Notes: {notes[:50]}..." if len(notes) > 50 else f"Notes: {notes}")
            logger.info(f"Webhook URL: {self.webhook_url}")
            logger.info(f"Full payload: {payload}")
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.TIMEOUT,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'PhotoUploader/1.0'
                }
            )
            
            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            logger.info(f"Response body: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                logger.info(f"✓ Site validated successfully")
                logger.info(f"  Client: {result.get('client_name')}")
                logger.info(f"  Address: {result.get('property_address')}")
                logger.info(f"  Dropbox path: {result.get('dropbox_path')}")
                logger.info(f"  Job ID: {result.get('job_id')}")
            else:
                logger.warning(f"✗ Site validation failed: {result.get('error', 'Unknown error')}")
                logger.warning(f"  Message: {result.get('message', 'No message')}")
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after {self.TIMEOUT} seconds")
            return {
                'success': False,
                'error': 'Request timeout',
                'message': f'Server did not respond within {self.TIMEOUT} seconds. Please check your connection and try again.'
            }
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            return {
                'success': False,
                'error': 'Connection error',
                'message': 'Could not connect to server. Please check your internet connection.'
            }
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"Response: {response.text if 'response' in locals() else 'No response'}")
            return {
                'success': False,
                'error': f'HTTP {response.status_code}',
                'message': f'Server returned error: {response.status_code}\n{response.text[:200]}'
            }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {e}")
            return {
                'success': False,
                'error': 'Network error',
                'message': f'Network error: {str(e)}'
            }
        
        except ValueError as e:
            logger.error(f"Invalid JSON response: {e}")
            logger.error(f"Response text: {response.text if 'response' in locals() else 'No response'}")
            return {
                'success': False,
                'error': 'Invalid response',
                'message': 'Server returned invalid data. Please contact support.'
            }
        
        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Unexpected error',
                'message': f'Unexpected error: {str(e)}'
            }
    
    def notify_upload_started(self, site_id: str, job_id: str, 
                             file_count: int, total_size_mb: float,
                             dropbox_path: str,
                             photo_type: str = "", location: str = "", notes: str = "") -> bool:
        """Notify Make that upload has started."""
        payload = {
            "action": "upload_started",
            "site_id": site_id,
            "job_id": job_id,
            "photographer_id": self.photographer_id,
            "file_count": file_count,
            "total_size_mb": round(total_size_mb, 2),
            "dropbox_path": dropbox_path,
            "photo_type": photo_type,
            "location": location,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return self._send_notification(payload, "Upload started notification")
    
    def notify_upload_progress(self, site_id: str, job_id: str,
                              progress_percent: int, files_uploaded: int,
                              files_remaining: int) -> bool:
        """Notify Make of upload progress."""
        payload = {
            "action": "upload_progress",
            "site_id": site_id,
            "job_id": job_id,
            "photographer_id": self.photographer_id,
            "progress_percent": progress_percent,
            "files_uploaded": files_uploaded,
            "files_remaining": files_remaining,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return self._send_notification(payload, "Upload progress update")
    
    def notify_upload_complete(self, site_id: str, job_id: str,
                              files_uploaded: int, total_size_mb: float,
                              duration_seconds: int, dropbox_path: str,
                              photo_type: str = "", location: str = "", notes: str = "") -> Dict[str, Any]:
        """Notify Make that upload completed successfully."""
        payload = {
            "action": "upload_complete",
            "site_id": site_id,
            "job_id": job_id,
            "photographer_id": self.photographer_id,
            "files_uploaded": files_uploaded,
            "total_size_mb": round(total_size_mb, 2),
            "duration_seconds": duration_seconds,
            "dropbox_path": dropbox_path,
            "photo_type": photo_type,
            "location": location,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "success"
        }
        
        try:
            logger.info("Sending upload completion notification")
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.TIMEOUT,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")
            return {'success': False}
    
    def notify_upload_failed(self, site_id: str, job_id: str,
                            files_uploaded: int, files_failed: int,
                            error_message: str) -> bool:
        """Notify Make that upload failed."""
        payload = {
            "action": "upload_failed",
            "site_id": site_id,
            "job_id": job_id,
            "photographer_id": self.photographer_id,
            "files_uploaded": files_uploaded,
            "files_failed": files_failed,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return self._send_notification(payload, "Upload failure notification")
    
    def _send_notification(self, payload: Dict[str, Any], description: str) -> bool:
        """Internal helper to send notifications to webhook."""
        try:
            logger.info(f"Sending {description}")
            logger.debug(f"Payload: {payload}")
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.TIMEOUT,
                headers={'Content-Type': 'application/json'}
            )
            
            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            if result.get('success'):
                logger.info(f"✓ {description} sent successfully")
                return True
            else:
                logger.warning(f"⚠ {description} acknowledged but flagged: {result.get('message')}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout sending {description}")
            return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send {description}: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error sending {description}: {e}", exc_info=True)
            return False