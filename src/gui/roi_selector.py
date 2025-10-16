"""ROI (Region of Interest) selection tool for image viewer"""

import logging
from PyQt5.QtWidgets import QRubberBand
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QMouseEvent

logger = logging.getLogger(__name__)


class ROISelector:
    """Handles ROI selection on images via rubber band selection"""
    
    roi_selected = pyqtSignal(QRect)
    
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self.parent)
        self.origin = QPoint()
        self.is_selecting = False
        self.selected_roi = None
        
        logger.info("ROI selector initialized")
    
    def start_selection(self):
        """Enable ROI selection mode"""
        self.is_selecting = True
        self.parent.setCursor(Qt.CrossCursor)
        logger.info("ROI selection mode activated")
    
    def stop_selection(self):
        """Disable ROI selection mode"""
        self.is_selecting = False
        self.parent.setCursor(Qt.ArrowCursor)
        self.rubber_band.hide()
        logger.info("ROI selection mode deactivated")
    
    def handle_mouse_press(self, event: QMouseEvent):
        """Handle mouse press event for ROI selection"""
        if self.is_selecting and event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()))
            self.rubber_band.show()
    
    def handle_mouse_move(self, event: QMouseEvent):
        """Handle mouse move event for ROI selection"""
        if self.is_selecting and self.rubber_band.isVisible():
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())
    
    def handle_mouse_release(self, event: QMouseEvent):
        """Handle mouse release event for ROI selection"""
        if self.is_selecting and event.button() == Qt.LeftButton:
            self.selected_roi = QRect(self.origin, event.pos()).normalized()
            logger.info(f"ROI selected: {self.selected_roi}")
            self.rubber_band.hide()
            return self.selected_roi
        return None
    
    def get_selected_roi(self) -> QRect:
        """Get the selected ROI rectangle"""
        return self.selected_roi
    
    def clear_selection(self):
        """Clear the current ROI selection"""
        self.selected_roi = None
        self.rubber_band.hide()
        logger.info("ROI selection cleared")
