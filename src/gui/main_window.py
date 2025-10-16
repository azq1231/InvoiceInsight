"""Main application window with split-view layout"""

import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QMenuBar, QMenu, QAction, QStatusBar,
    QPushButton, QLabel, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

from src.utils.config import get_config
from src.gui.image_viewer import ImageViewerPanel
from src.gui.data_editor import DataEditorPanel
from src.gui.photo_selector import PhotoSelectorDialog
from src.auth.google_auth import GoogleAuthManager


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with split-view interface"""
    
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.auth_manager = None
        self.current_photo = None
        
        self._init_ui()
        self._setup_shortcuts()
        self._check_authentication()
    
    def _init_ui(self):
        """Initialize user interface"""
        ui_config = self.config.get('ui.window', {})
        
        self.setWindowTitle(self.config.get('app.name', 'OCR Expense Tracker'))
        self.setGeometry(100, 100, 
                        ui_config.get('width', 1400), 
                        ui_config.get('height', 900))
        self.setMinimumSize(ui_config.get('min_width', 1200), 
                           ui_config.get('min_height', 700))
        
        self._create_menu_bar()
        self._create_central_widget()
        self._create_status_bar()
        
        logger.info("Main window initialized")
    
    def _create_menu_bar(self):
        """Create application menu bar"""
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu('文件(&F)')
        
        login_action = QAction('登入 Google 帳號(&L)', self)
        login_action.triggered.connect(self._handle_login)
        file_menu.addAction(login_action)
        
        logout_action = QAction('登出(&O)', self)
        logout_action.triggered.connect(self._handle_logout)
        file_menu.addAction(logout_action)
        
        file_menu.addSeparator()
        
        select_photos_action = QAction('選擇照片(&S)', self)
        select_photos_action.setShortcut('Ctrl+P')
        select_photos_action.triggered.connect(self._handle_select_photos)
        file_menu.addAction(select_photos_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出(&X)', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        ocr_menu = menubar.addMenu('辨識(&O)')
        
        start_ocr_action = QAction('開始 OCR 辨識(&S)', self)
        start_ocr_action.setShortcut('Ctrl+O')
        start_ocr_action.triggered.connect(self._handle_start_ocr)
        ocr_menu.addAction(start_ocr_action)
        
        batch_ocr_action = QAction('批次辨識(&B)', self)
        batch_ocr_action.triggered.connect(self._handle_batch_ocr)
        ocr_menu.addAction(batch_ocr_action)
        
        view_menu = menubar.addMenu('檢視(&V)')
        
        zoom_in_action = QAction('放大(&I)', self)
        zoom_in_action.setShortcut('Ctrl++')
        zoom_in_action.triggered.connect(self._handle_zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction('縮小(&O)', self)
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.triggered.connect(self._handle_zoom_out)
        view_menu.addAction(zoom_out_action)
        
        help_menu = menubar.addMenu('說明(&H)')
        
        about_action = QAction('關於(&A)', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_central_widget(self):
        """Create central widget with split-view layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        toolbar_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("登入 Google")
        self.login_btn.clicked.connect(self._handle_login)
        toolbar_layout.addWidget(self.login_btn)
        
        self.select_photos_btn = QPushButton("選擇照片")
        self.select_photos_btn.clicked.connect(self._handle_select_photos)
        self.select_photos_btn.setEnabled(False)
        toolbar_layout.addWidget(self.select_photos_btn)
        
        toolbar_layout.addStretch()
        
        self.status_label = QLabel("請先登入 Google 帳號")
        toolbar_layout.addWidget(self.status_label)
        
        main_layout.addLayout(toolbar_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        
        splitter_config = self.config.get('ui.splitter', {})
        left_ratio = splitter_config.get('left_panel_ratio', 0.6)
        right_ratio = splitter_config.get('right_panel_ratio', 0.4)
        
        self.image_viewer = ImageViewerPanel(self)
        splitter.addWidget(self.image_viewer)
        
        self.data_editor = DataEditorPanel(self)
        splitter.addWidget(self.data_editor)
        
        total_width = self.width()
        splitter.setSizes([int(total_width * left_ratio), int(total_width * right_ratio)])
        
        main_layout.addWidget(splitter)
    
    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就緒")
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        pass
    
    def _check_authentication(self):
        """Check if user is already authenticated"""
        try:
            self.auth_manager = GoogleAuthManager()
            if self.auth_manager.is_authenticated():
                self._on_login_success()
            else:
                logger.info("User not authenticated")
        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
    
    def _handle_login(self):
        """Handle Google login"""
        try:
            if not self.auth_manager:
                self.auth_manager = GoogleAuthManager()
            
            self.status_label.setText("正在登入...")
            QTimer.singleShot(100, self._perform_login)
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            QMessageBox.critical(self, "登入錯誤", f"登入失敗: {str(e)}")
            self.status_label.setText("登入失敗")
    
    def _perform_login(self):
        """Perform actual login"""
        try:
            success = self.auth_manager.authenticate()
            if success:
                self._on_login_success()
            else:
                self.status_label.setText("登入失敗")
        except Exception as e:
            logger.error(f"Login error: {e}")
            self.status_label.setText("登入錯誤")
    
    def _on_login_success(self):
        """Handle successful login"""
        self.status_label.setText("已登入")
        self.login_btn.setText("已登入")
        self.login_btn.setEnabled(False)
        self.select_photos_btn.setEnabled(True)
        self.status_bar.showMessage("Google 帳號已連接")
        logger.info("Login successful")
    
    def _handle_logout(self):
        """Handle Google logout"""
        if self.auth_manager:
            self.auth_manager.logout()
            self.status_label.setText("已登出")
            self.login_btn.setText("登入 Google")
            self.login_btn.setEnabled(True)
            self.select_photos_btn.setEnabled(False)
            self.status_bar.showMessage("已登出")
            logger.info("Logout successful")
    
    def _handle_select_photos(self):
        """Handle photo selection"""
        self.status_label.setText("功能開發中...")
        logger.info("Photo selection requested")
    
    def _handle_start_ocr(self):
        """Handle OCR start"""
        self.status_label.setText("OCR 功能開發中...")
        logger.info("OCR requested")
    
    def _handle_batch_ocr(self):
        """Handle batch OCR"""
        self.status_label.setText("批次 OCR 功能開發中...")
        logger.info("Batch OCR requested")
    
    def _handle_zoom_in(self):
        """Handle zoom in"""
        if self.image_viewer:
            self.image_viewer.zoom_in()
    
    def _handle_zoom_out(self):
        """Handle zoom out"""
        if self.image_viewer:
            self.image_viewer.zoom_out()
    
    def _show_about(self):
        """Show about dialog"""
        version = self.config.get('app.version', '1.0.0')
        QMessageBox.about(
            self,
            "關於",
            f"<h3>OCR 收支辨識系統</h3>"
            f"<p>版本: {version}</p>"
            f"<p>企業級手寫帳單自動辨識與整理工具</p>"
            f"<p>使用 Google Cloud Vision API 與 Tesseract OCR</p>"
        )
