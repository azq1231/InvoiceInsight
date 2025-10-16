"""Google Photos API integration with lazy loading and pagination"""

import logging
from typing import List, Dict, Optional, Generator
from datetime import datetime
import requests
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class GooglePhotosAPI:
    """Google Photos API client with lazy loading and pagination support"""
    
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.service = build('photoslibrary', 'v1', credentials=credentials, static_discovery=False)
        self.config = get_config()
        logger.info("Google Photos API client initialized")
    
    def list_albums(self, page_size: int = 50) -> Generator[Dict, None, None]:
        """List albums with pagination (lazy loading)"""
        try:
            page_token = None
            
            while True:
                response = self.service.albums().list(
                    pageSize=page_size,
                    pageToken=page_token
                ).execute()
                
                albums = response.get('albums', [])
                for album in albums:
                    yield {
                        'id': album.get('id'),
                        'title': album.get('title'),
                        'cover_photo_url': album.get('coverPhotoBaseUrl'),
                        'media_items_count': album.get('mediaItemsCount', 0),
                        'product_url': album.get('productUrl')
                    }
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                    
            logger.info("Albums listing completed")
            
        except Exception as e:
            logger.error(f"Failed to list albums: {e}")
            raise
    
    def list_media_items(self, album_id: Optional[str] = None, page_size: int = 100) -> Generator[Dict, None, None]:
        """List media items from album or library with pagination"""
        try:
            page_token = None
            
            while True:
                if album_id:
                    response = self.service.mediaItems().search(
                        body={
                            'albumId': album_id,
                            'pageSize': page_size,
                            'pageToken': page_token
                        }
                    ).execute()
                else:
                    response = self.service.mediaItems().list(
                        pageSize=page_size,
                        pageToken=page_token
                    ).execute()
                
                media_items = response.get('mediaItems', [])
                for item in media_items:
                    yield {
                        'id': item.get('id'),
                        'filename': item.get('filename'),
                        'base_url': item.get('baseUrl'),
                        'mime_type': item.get('mimeType'),
                        'creation_time': item.get('mediaMetadata', {}).get('creationTime'),
                        'width': item.get('mediaMetadata', {}).get('width'),
                        'height': item.get('mediaMetadata', {}).get('height'),
                        'product_url': item.get('productUrl')
                    }
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                    
            logger.info(f"Media items listing completed for album: {album_id or 'library'}")
            
        except Exception as e:
            logger.error(f"Failed to list media items: {e}")
            raise
    
    def get_image_url(self, base_url: str, width: int = 2048, height: int = 2048) -> str:
        """Get download URL for image with specified dimensions"""
        return f"{base_url}=w{width}-h{height}"
    
    def download_image(self, base_url: str, width: int = 2048, height: int = 2048) -> bytes:
        """Download image bytes from Google Photos"""
        try:
            image_url = self.get_image_url(base_url, width, height)
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            logger.info(f"Image downloaded successfully")
            return response.content
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            raise
    
    def get_thumbnail_url(self, base_url: str) -> str:
        """Get thumbnail URL (256x256)"""
        return self.get_image_url(base_url, 256, 256)
