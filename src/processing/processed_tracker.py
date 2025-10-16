"""Track processed photos to prevent duplicate processing"""

import logging
import json
from pathlib import Path
from typing import Set, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class ProcessedPhotoTracker:
    """Track which photos have been processed"""
    
    def __init__(self, tracker_file: str = 'data/processed_photos/tracker.json'):
        self.tracker_file = Path(tracker_file)
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.processed_photos: Dict[str, Dict] = self._load()
        logger.info(f"Processed photo tracker initialized: {len(self.processed_photos)} photos tracked")
    
    def _load(self) -> Dict[str, Dict]:
        """Load processed photos from file"""
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load tracker: {e}")
                return {}
        return {}
    
    def _save(self):
        """Save processed photos to file"""
        try:
            with open(self.tracker_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_photos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tracker: {e}")
    
    def is_processed(self, photo_id: str) -> bool:
        """Check if photo has been processed"""
        return photo_id in self.processed_photos
    
    def mark_processed(self, photo_id: str, result: Dict):
        """Mark photo as processed with result metadata"""
        self.processed_photos[photo_id] = {
            'processed_at': datetime.now().isoformat(),
            'status': result.get('status', 'unknown'),
            'needs_review': result.get('needs_review', False),
            'item_count': len(result.get('extracted_data', {}).get('items', []))
        }
        self._save()
        logger.info(f"Marked photo as processed: {photo_id}")
    
    def get_processed_count(self) -> int:
        """Get count of processed photos"""
        return len(self.processed_photos)
    
    def get_pending_review_count(self) -> int:
        """Get count of photos pending review"""
        return sum(1 for p in self.processed_photos.values() if p.get('needs_review', False))
    
    def clear_all(self):
        """Clear all processed photo records"""
        self.processed_photos = {}
        self._save()
        logger.info("Cleared all processed photo records")
