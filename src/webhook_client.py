"""
Make.com webhook client - FINAL VERSION
Features:
- Config request (markets + photographer name)
- Content type support (daytime/twilight/video)
- Simplified path handling (Make.com returns complete path)
- Connection pooling for performance
"""

import requests
import logging
from typing import Dict, Any
from datetime import datetime
from config import WEBHOOK_URL

logger = logging.getLogger(__name__)

class MakeWebhookClient:
    """Handles all communication with Make.com webhook."""
    
    TIMEOUT = 20  # seconds
    
    def __init__(self, photographer_id: str):
        self.photographer_id = photographer_id
        self.webhook_url = WEBHOOK_URL
        self.session = requests.Session()  # Connection pooling
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PhotoUploader/2.0'
        })
    
    def request_config(self) -> Dict[str, Any]:
        """
        Request configuration from Make.com at app startup.
        
        Returns:
            {
                'success': bool,
                'markets': ['Bay Area', 'Atlanta', ...],
                'photographer_name': 'John Smith',
                'photographer_id': 'PHOTO01',
                'error': str (if failed)
            }
        """
        payload = {
            "action": "request_config",
            "photographer_id": self.photographer_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "2.0"
        }
        
        try:
            logger.info(f"Requesting config for photographer: {self.photographer_id}")
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                markets = result.get('markets', [])
                photographer_name = result.get('photographer_name', '')
                logger.info(f"Config received: {len(markets)} markets, photographer: {photographer_name}")
            else:
                logger.warning(f"Config request failed: {result.get('error')}")
            
            return result
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
                'message': 'Server did not respond in time. Please check your connection.'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Config request failed: {e}")
            return {
                'success': False,
                'error': 'Network error',
                'message': f'Failed to contact server: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error during config request: {e}")
            return {
                'success': False,
                'error': 'Unexpected error',
                'message': str(e)
            }
    
    def validate_site(self, market: str, site_id: str, 
                     file_count: int, total_size_mb: float,
                     content_type: str = "daytime") -> Dict[str, Any]:
        """
        Validate site ID with market context and content type.
        
        Args:
            market: Market/Branch name (e.g., "Bay Area")
            site_id: Site ID without prefix (e.g., "507")
            file_count: Total number of files
            total_size_mb: Total size in MB
            content_type: Type of content ("daytime", "twilight", "video")
        
        Returns:
            {
                'success': bool,
                'dropbox_path': str,  # Complete path from Make.com (includes subfolder)
                'client_name': str,
                'property_address': str,
                'job_id': str,
                'message': str,
                'error': str (if failed)
            }
        """
        payload = {
            "action": "validate_site",
            "market": market,
            "site_id": site_id,
            "photographer_id": self.photographer_id,
            "file_count": file_count,
            "total_size_mb": round(total_size_mb, 2),
            "content_type": content_type,
            "is_twilight": content_type == "twilight",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "2.0"
        }
        
        try:
            logger.info(f"Validating site: Market={market}, Site ID={site_id}, Content={content_type}")
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                logger.info(f"Site validated: {result.get('client_name')} - {result.get('property_address')}")
                logger.info(f"Dropbox path: {result.get('dropbox_path')}")
            else:
                logger.warning(f"Site validation failed: {result.get('error', result.get('message'))}")
            
            return result
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
                'message': 'Server did not respond in time. Please check your connection.'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook request failed: {e}")
            return {
                'success': False,
                'error': 'Network error',
                'message': f'Failed to contact server: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}")
            return {
                'success': False,
                'error': 'Unexpected error',
                'message': str(e)
            }
    
    def notify_upload_started(self, market: str, site_id: str, job_id: str, 
                             file_count: int, total_size_mb: float,
                             dropbox_path: str, content_type: str = "daytime") -> bool:
        """Notify Make that upload has started."""
        payload = {
            "action": "upload_started",
            "market": market,
            "site_id": site_id,
            "job_id": job_id,
            "photographer_id": self.photographer_id,
            "file_count": file_count,
            "total_size_mb": round(total_size_mb, 2),
            "dropbox_path": dropbox_path,
            "content_type": content_type,
            "is_twilight": content_type == "twilight",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "2.0"
        }
        
        return self._send_notification(payload, "Upload started notification")
    
    def notify_upload_progress(self, market: str, site_id: str, job_id: str,
                              progress_percent: int, files_uploaded: int,
                              files_remaining: int, content_type: str = "daytime") -> bool:
        """Notify Make of upload progress."""
        payload = {
            "action": "upload_progress",
            "market": market,
            "site_id": site_id,
            "job_id": job_id,
            "photographer_id": self.photographer_id,
            "progress_percent": progress_percent,
            "files_uploaded": files_uploaded,
            "files_remaining": files_remaining,
            "content_type": content_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "2.0"
        }
        
        return self._send_notification(payload, "Upload progress update")
    
    def notify_upload_complete(self, market: str, site_id: str, job_id: str,
                              files_uploaded: int, total_size_mb: float,
                              duration_seconds: int, dropbox_path: str,
                              content_type: str = "daytime") -> Dict[str, Any]:
        """
        Notify Make that upload completed successfully.
        
        IMPORTANT: If content_type is "twilight", Make.com should send Slack notification!
        """
        avg_speed_mbps = (total_size_mb / duration_seconds) if duration_seconds > 0 else 0
        
        payload = {
            "action": "upload_complete",
            "market": market,
            "site_id": site_id,
            "job_id": job_id,
            "photographer_id": self.photographer_id,
            "files_uploaded": files_uploaded,
            "total_size_mb": round(total_size_mb, 2),
            "duration_seconds": duration_seconds,
            "avg_speed_mbps": round(avg_speed_mbps, 2),
            "dropbox_path": dropbox_path,
            "content_type": content_type,
            "is_twilight": content_type == "twilight",  # Trigger for Slack notification
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "success",
            "version": "2.0"
        }
        
        try:
            logger.info(f"Sending upload completion notification (content_type={content_type})")
            if content_type == "twilight":
                logger.info("⚠️ Twilight upload - Make.com should send Slack notification")
            
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")
            return {'success': False}
    
    def notify_upload_failed(self, market: str, site_id: str, job_id: str,
                            files_uploaded: int, files_failed: int,
                            error_message: str, content_type: str = "daytime") -> bool:
        """Notify Make that upload failed."""
        payload = {
            "action": "upload_failed",
            "market": market,
            "site_id": site_id,
            "job_id": job_id,
            "photographer_id": self.photographer_id,
            "files_uploaded": files_uploaded,
            "files_failed": files_failed,
            "error_message": error_message,
            "content_type": content_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "2.0"
        }
        
        return self._send_notification(payload, "Upload failure notification")
    
    def _send_notification(self, payload: Dict[str, Any], description: str) -> bool:
        """Internal helper to send notifications to webhook."""
        try:
            logger.info(f"Sending {description}")
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get('success'):
                logger.info(f"{description} sent successfully")
                return True
            else:
                logger.warning(f"{description} acknowledged but flagged: {result.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send {description}: {e}")
            return False
    
    def __del__(self):
        """Clean up session on destruction."""
        if hasattr(self, 'session'):
            self.session.close()