"""Image viewer panel with zoom, pan, rotate functionality"""

import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QRubberBand
)
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QImage
from typing import Optional

logger = logging.getLogger(__name__)


class ImageViewerPanel(QWidget):
    """Image viewer with zoom, pan, rotate and ROI selection"""
    
    roi_selected = pyqtSignal(QRect)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pixmap: Optional[QPixmap] = None
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        
        self._init_ui()
        logger.info("Image viewer panel initialized")
    
    def _init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        toolbar = QHBoxLayout()
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(30, 30)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedSize(30, 30)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(self.zoom_out_btn)
        
        self.rotate_btn = QPushButton("⟳")
        self.rotate_btn.setFixedSize(30, 30)
        self.rotate_btn.clicked.connect(self.rotate_cw)
        toolbar.addWidget(self.rotate_btn)
        
        self.fit_btn = QPushButton("適合")
        self.fit_btn.clicked.connect(self.fit_to_view)
        toolbar.addWidget(self.fit_btn)
        
        toolbar.addStretch()
        
        self.zoom_label = QLabel("100%")
        toolbar.addWidget(self.zoom_label)
        
        layout.addLayout(toolbar)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("尚未載入圖片")
        self.image_label.setStyleSheet("QLabel { background-color: #f0f0f0; }")
        
        scroll_area.setWidget(self.image_label)
        layout.addWidget(scroll_area)
    
    def load_image(self, image_path_or_pixmap):
        """Load image from path or QPixmap"""
        if isinstance(image_path_or_pixmap, str):
            self.current_pixmap = QPixmap(image_path_or_pixmap)
        elif isinstance(image_path_or_pixmap, QPixmap):
            self.current_pixmap = image_path_or_pixmap
        else:
            logger.error("Invalid image type")
            return
        
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self._update_display()
        logger.info("Image loaded successfully")
    
    def _update_display(self):
        """Update image display with current zoom and rotation"""
        if not self.current_pixmap:
            return
        
        from PyQt5.QtGui import QTransform
        transform = QTransform().rotate(self.rotation_angle)
        rotated = self.current_pixmap.transformed(transform, Qt.SmoothTransformation)
        
        scaled = rotated.scaled(
            int(rotated.width() * self.zoom_factor),
            int(rotated.height() * self.zoom_factor),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled)
        self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")
    
    def zoom_in(self):
        """Zoom in image"""
        self.zoom_factor *= 1.2
        self._update_display()
    
    def zoom_out(self):
        """Zoom out image"""
        self.zoom_factor /= 1.2
        self._update_display()
    
    def rotate_cw(self):
        """Rotate image clockwise"""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self._update_display()
    
    def fit_to_view(self):
        """Fit image to view"""
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self._update_display()
