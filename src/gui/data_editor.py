"""Data editor panel for reviewing and editing OCR results"""

import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QLabel, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)


class DataEditorPanel(QWidget):
    """Panel for editing and reviewing OCR extracted data"""
    
    data_approved = pyqtSignal(dict)
    data_rejected = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_data = None
        
        self._init_ui()
        logger.info("Data editor panel initialized")
    
    def _init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        header_layout = QHBoxLayout()
        title_label = QLabel("<h3>辨識結果</h3>")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.status_label = QLabel("尚未辨識")
        header_layout.addWidget(self.status_label)
        
        layout.addLayout(header_layout)
        
        self.date_label = QLabel("日期: -")
        layout.addWidget(self.date_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["項目", "金額", "分類", "狀態"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.table)
        
        self.total_label = QLabel("總計: NT$ 0")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.total_label)
        
        button_layout = QHBoxLayout()
        
        self.reocr_btn = QPushButton("重新辨識")
        self.reocr_btn.clicked.connect(self._handle_reocr)
        button_layout.addWidget(self.reocr_btn)
        
        button_layout.addStretch()
        
        self.reject_btn = QPushButton("拒絕")
        self.reject_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        self.reject_btn.clicked.connect(self._handle_reject)
        button_layout.addWidget(self.reject_btn)
        
        self.approve_btn = QPushButton("核准並儲存")
        self.approve_btn.setStyleSheet("background-color: #51cf66; color: white;")
        self.approve_btn.clicked.connect(self._handle_approve)
        button_layout.addWidget(self.approve_btn)
        
        layout.addLayout(button_layout)
    
    def load_data(self, data: dict):
        """Load OCR result data into editor"""
        self.current_data = data
        
        self.date_label.setText(f"日期: {data.get('date', '-')}")
        
        items = data.get('items', [])
        self.table.setRowCount(len(items))
        
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get('name', '')))
            self.table.setItem(row, 1, QTableWidgetItem(str(item.get('amount', 0))))
            self.table.setItem(row, 2, QTableWidgetItem(item.get('category', '支出')))
            
            status = "需確認" if item.get('needs_review', False) else "正常"
            status_item = QTableWidgetItem(status)
            if item.get('needs_review', False):
                status_item.setBackground(Qt.yellow)
            self.table.setItem(row, 3, status_item)
        
        total = sum(item.get('amount', 0) for item in items)
        self.total_label.setText(f"總計: NT$ {total:.2f}")
        
        self.status_label.setText("請核對資料")
        logger.info(f"Loaded {len(items)} items for review")
    
    def _handle_reocr(self):
        """Handle re-OCR request"""
        logger.info("Re-OCR requested")
        self.status_label.setText("重新辨識功能開發中...")
    
    def _handle_approve(self):
        """Handle data approval"""
        if self.current_data:
            self.data_approved.emit(self.current_data)
            logger.info("Data approved")
            self.status_label.setText("已核准")
    
    def _handle_reject(self):
        """Handle data rejection"""
        self.data_rejected.emit()
        logger.info("Data rejected")
        self.status_label.setText("已拒絕")
