"""Photo selector dialog for choosing photos from Google Photos"""

import logging
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel

logger = logging.getLogger(__name__)


class PhotoSelectorDialog(QDialog):
    """Dialog for selecting photos from Google Photos albums"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("選擇照片")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        label = QLabel("照片選擇功能開發中...")
        layout.addWidget(label)
        
        logger.info("Photo selector dialog initialized")
