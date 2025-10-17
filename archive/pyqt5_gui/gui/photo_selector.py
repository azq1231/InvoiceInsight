"""Google Photos selector dialog"""

import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QListWidgetItem, QLabel, QMessageBox
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QImage

from src.api.google_photos import GooglePhotosAPI
from src.cache.image_cache import ImageCache

logger = logging.getLogger(__name__)


class PhotoSelectorDialog(QDialog):
    """Dialog for selecting photos from Google Photos"""
    
    def __init__(self, credentials, parent=None):
        super().__init__(parent)
        self.credentials = credentials
        self.photos_api = GooglePhotosAPI(credentials)
        self.cache = ImageCache()
        
        self.selected_photo = None
        self.all_photos = []
        
        self._init_ui()
        self._load_photos()
    
    def _init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("選擇照片 - Google Photos")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        self.info_label = QLabel("正在載入照片...")
        layout.addWidget(self.info_label)
        
        self.photo_list = QListWidget()
        self.photo_list.setIconSize(QSize(120, 120))
        self.photo_list.setViewMode(QListWidget.IconMode)
        self.photo_list.setResizeMode(QListWidget.Adjust)
        self.photo_list.setSpacing(10)
        self.photo_list.itemDoubleClicked.connect(self._on_photo_selected)
        self.photo_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.photo_list)
        
        btn_layout = QHBoxLayout()
        
        self.load_more_btn = QPushButton("載入更多")
        self.load_more_btn.clicked.connect(self._load_more)
        self.load_more_btn.setEnabled(False)
        btn_layout.addWidget(self.load_more_btn)
        
        btn_layout.addStretch()
        
        self.select_btn = QPushButton("選擇")
        self.select_btn.clicked.connect(self._on_select_clicked)
        self.select_btn.setEnabled(False)
        btn_layout.addWidget(self.select_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_photos(self):
        """Load photos from Google Photos"""
        try:
            self.info_label.setText("正在載入照片...")
            
            photos, next_token = self.photos_api.list_photos(page_size=50)
            
            if not photos:
                self.info_label.setText("未找到照片")
                return
            
            self.all_photos.extend(photos)
            self._populate_photo_list(photos)
            
            self.info_label.setText(f"已載入 {len(self.all_photos)} 張照片")
            
            if next_token:
                self.load_more_btn.setEnabled(True)
            
        except Exception as e:
            logger.error(f"Failed to load photos: {e}")
            self.info_label.setText(f"載入失敗: {str(e)}")
            QMessageBox.critical(self, "錯誤", f"載入照片失敗: {str(e)}")
    
    def _populate_photo_list(self, photos):
        """Populate photo list with thumbnails"""
        for photo in photos:
            try:
                thumb_bytes = self.cache.get_image(photo['baseUrl'], is_thumbnail=True)
                
                if not thumb_bytes:
                    thumb_bytes = self.photos_api.download_photo(photo['baseUrl'], max_size=200)
                    if thumb_bytes:
                        self.cache.set_image(photo['baseUrl'], thumb_bytes, is_thumbnail=True)
                
                if thumb_bytes:
                    qimage = QImage.fromData(thumb_bytes)
                    pixmap = QPixmap.fromImage(qimage)
                    
                    item = QListWidgetItem()
                    item.setIcon(pixmap)
                    item.setText(photo.get('filename', 'Untitled'))
                    item.setData(Qt.UserRole, photo)
                    
                    self.photo_list.addItem(item)
                    
            except Exception as e:
                logger.error(f"Failed to load thumbnail: {e}")
    
    def _load_more(self):
        """Load more photos"""
        try:
            self.load_more_btn.setEnabled(False)
            self.info_label.setText("正在載入更多照片...")
            
            photos, next_token = self.photos_api.list_photos(page_size=50)
            
            if photos:
                self.all_photos.extend(photos)
                self._populate_photo_list(photos)
                self.info_label.setText(f"已載入 {len(self.all_photos)} 張照片")
            
            if next_token:
                self.load_more_btn.setEnabled(True)
            else:
                self.info_label.setText(f"已載入全部 {len(self.all_photos)} 張照片")
                
        except Exception as e:
            logger.error(f"Failed to load more photos: {e}")
            QMessageBox.critical(self, "錯誤", f"載入失敗: {str(e)}")
    
    def _on_selection_changed(self, current, previous):
        """Handle selection change"""
        self.select_btn.setEnabled(current is not None)
    
    def _on_photo_selected(self, item):
        """Handle photo double-click"""
        self.selected_photo = item.data(Qt.UserRole)
        self.accept()
    
    def _on_select_clicked(self):
        """Handle select button click"""
        current_item = self.photo_list.currentItem()
        if current_item:
            self.selected_photo = current_item.data(Qt.UserRole)
            self.accept()
    
    def get_selected_photo(self):
        """Get selected photo data"""
        return self.selected_photo
