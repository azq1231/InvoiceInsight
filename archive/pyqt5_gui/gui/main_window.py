"""Main application window with split-view layout"""

import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QMenuBar, QMenu, QAction, QStatusBar,
    QPushButton, QLabel, QMessageBox, QProgressDialog,
    QDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QPixmap, QImage

from src.utils.config import get_config
from src.gui.image_viewer import ImageViewerPanel
from src.gui.data_editor import DataEditorPanel
from src.gui.photo_selector import PhotoSelectorDialog
from src.auth.google_auth import GoogleAuthManager
from src.api.google_photos import GooglePhotosAPI
from src.api.google_sheets import GoogleSheetsAPI
from src.processing.ocr_orchestrator import OCROrchestrator
from src.processing.processed_tracker import ProcessedPhotoTracker
from src.cache.image_cache import ImageCache


logger = logging.getLogger(__name__)


class OCRWorker(QThread):
    """Worker thread for OCR processing"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, orchestrator, image_bytes, photo_id):
        super().__init__()
        self.orchestrator = orchestrator
        self.image_bytes = image_bytes
        self.photo_id = photo_id
    
    def run(self):
        """Run OCR processing"""
        try:
            self.progress.emit("正在執行 OCR 辨識...")
            result = self.orchestrator.process_image(self.image_bytes, self.photo_id)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window with split-view interface"""
    
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.auth_manager = None
        self.photos_api = None
        self.sheets_api = None
        self.orchestrator = None
        self.tracker = ProcessedPhotoTracker()
        self.cache = ImageCache()
        
        self.current_photo = None
        self.current_photo_bytes = None
        self.current_ocr_result = None
        self.ocr_worker = None
        
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
        
        self.ocr_btn = QPushButton("開始 OCR 辨識")
        self.ocr_btn.clicked.connect(self._handle_start_ocr)
        self.ocr_btn.setEnabled(False)
        toolbar_layout.addWidget(self.ocr_btn)
        
        self.save_btn = QPushButton("核准並儲存")
        self.save_btn.clicked.connect(self._handle_save)
        self.save_btn.setEnabled(False)
        toolbar_layout.addWidget(self.save_btn)
        
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
        self.login_btn.setText("已登入 ✓")
        self.login_btn.setEnabled(False)
        self.select_photos_btn.setEnabled(True)
        self.status_bar.showMessage("Google 帳號已連接")
        
        creds = self.auth_manager.get_credentials()
        self.photos_api = GooglePhotosAPI(creds)
        self.sheets_api = GoogleSheetsAPI(creds)
        self.orchestrator = OCROrchestrator(creds)
        
        logger.info("Login successful, APIs initialized")
    
    def _handle_logout(self):
        """Handle Google logout"""
        if self.auth_manager:
            self.auth_manager.logout()
            self.status_label.setText("已登出")
            self.login_btn.setText("登入 Google")
            self.login_btn.setEnabled(True)
            self.select_photos_btn.setEnabled(False)
            self.ocr_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.status_bar.showMessage("已登出")
            logger.info("Logout successful")
    
    def _handle_select_photos(self):
        """Handle photo selection"""
        try:
            if not self.photos_api:
                QMessageBox.warning(self, "警告", "請先登入 Google 帳號")
                return
            
            creds = self.auth_manager.get_credentials()
            dialog = PhotoSelectorDialog(creds, self)
            
            if dialog.exec_() == QDialog.Accepted:
                photo = dialog.get_selected_photo()
                if photo:
                    self._load_photo(photo)
            
        except Exception as e:
            logger.error(f"Photo selection failed: {e}")
            QMessageBox.critical(self, "錯誤", f"選擇照片失敗: {str(e)}")
    
    def _load_photo(self, photo):
        """Load selected photo"""
        try:
            self.current_photo = photo
            self.status_label.setText(f"正在載入照片...")
            
            photo_bytes = self.cache.get_image(photo['baseUrl'], is_thumbnail=False)
            
            if not photo_bytes:
                photo_bytes = self.photos_api.download_photo(photo['baseUrl'])
                if photo_bytes:
                    self.cache.set_image(photo['baseUrl'], photo_bytes, is_thumbnail=False)
            
            if photo_bytes:
                self.current_photo_bytes = photo_bytes
                
                qimage = QImage.fromData(photo_bytes)
                pixmap = QPixmap.fromImage(qimage)
                
                self.image_viewer.set_image(pixmap)
                
                self.ocr_btn.setEnabled(True)
                self.status_label.setText(f"已載入: {photo.get('filename', 'Untitled')}")
                
                if self.tracker.is_processed(photo['id']):
                    self.status_bar.showMessage("此照片已處理過")
                else:
                    self.status_bar.showMessage("就緒 - 可開始 OCR 辨識")
            
        except Exception as e:
            logger.error(f"Failed to load photo: {e}")
            QMessageBox.critical(self, "錯誤", f"載入照片失敗: {str(e)}")
    
    def _handle_start_ocr(self):
        """Handle OCR start"""
        if not self.current_photo_bytes:
            QMessageBox.warning(self, "警告", "請先選擇一張照片")
            return
        
        try:
            self.ocr_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.status_label.setText("OCR 辨識中...")
            
            self.ocr_worker = OCRWorker(
                self.orchestrator,
                self.current_photo_bytes,
                self.current_photo['id']
            )
            self.ocr_worker.progress.connect(self._on_ocr_progress)
            self.ocr_worker.finished.connect(self._on_ocr_finished)
            self.ocr_worker.error.connect(self._on_ocr_error)
            self.ocr_worker.start()
            
        except Exception as e:
            logger.error(f"OCR start failed: {e}")
            QMessageBox.critical(self, "錯誤", f"OCR 啟動失敗: {str(e)}")
            self.ocr_btn.setEnabled(True)
    
    def _on_ocr_progress(self, message):
        """Handle OCR progress update"""
        self.status_label.setText(message)
    
    def _on_ocr_finished(self, result):
        """Handle OCR completion"""
        self.current_ocr_result = result
        
        if result['status'] == 'success':
            extracted = result['extracted_data']
            
            self.data_editor.set_data(extracted)
            
            self.save_btn.setEnabled(True)
            self.ocr_btn.setEnabled(True)
            
            confidence = result['ocr_result'].get('confidence', 0)
            self.status_label.setText(f"OCR 完成 (信心度: {confidence:.1%})")
            
            if result.get('needs_review'):
                self.status_bar.showMessage("⚠️ 偵測到異常，請仔細核對資料")
            else:
                self.status_bar.showMessage("OCR 辨識完成，請核對資料")
        else:
            QMessageBox.critical(self, "錯誤", f"OCR 失敗: {result.get('error', 'Unknown error')}")
            self.ocr_btn.setEnabled(True)
    
    def _on_ocr_error(self, error_msg):
        """Handle OCR error"""
        QMessageBox.critical(self, "OCR 錯誤", f"OCR 處理失敗: {error_msg}")
        self.ocr_btn.setEnabled(True)
        self.status_label.setText("OCR 失敗")
    
    def _handle_save(self):
        """Handle save to Google Sheets"""
        if not self.current_ocr_result:
            QMessageBox.warning(self, "警告", "沒有資料可儲存")
            return
        
        try:
            data = self.data_editor.get_data()
            
            reply = QMessageBox.question(
                self,
                "確認儲存",
                f"確定要將資料儲存到 Google Sheets 嗎？\n\n"
                f"日期: {data['date']}\n"
                f"項目數: {len(data['items'])}\n"
                f"總計: ${data.get('declared_total', data.get('calculated_total', 0)):.2f}",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._save_to_sheets(data)
                
        except Exception as e:
            logger.error(f"Save failed: {e}")
            QMessageBox.critical(self, "錯誤", f"儲存失敗: {str(e)}")
    
    def _save_to_sheets(self, data):
        """Save data to Google Sheets"""
        try:
            self.status_label.setText("正在儲存到 Google Sheets...")
            
            spreadsheet_name = self.config.get('google_sheets.spreadsheet_name', 'OCR 收支記錄')
            
            spreadsheet_id = self.sheets_api.get_or_create_spreadsheet(spreadsheet_name)
            
            rows = self.sheets_api.format_expense_data(data)
            
            self.sheets_api.append_data(spreadsheet_id, rows)
            
            self.tracker.mark_processed(self.current_photo['id'], self.current_ocr_result)
            
            QMessageBox.information(
                self,
                "儲存成功",
                f"資料已成功儲存到 Google Sheets\n試算表: {spreadsheet_name}"
            )
            
            self.status_label.setText("儲存完成")
            self.status_bar.showMessage("資料已儲存到 Google Sheets")
            self.save_btn.setEnabled(False)
            
            logger.info(f"Data saved to Google Sheets: {spreadsheet_id}")
            
        except Exception as e:
            logger.error(f"Failed to save to Sheets: {e}")
            QMessageBox.critical(self, "儲存錯誤", f"儲存到 Google Sheets 失敗: {str(e)}")
    
    def _handle_batch_ocr(self):
        """Handle batch OCR"""
        QMessageBox.information(self, "批次辨識", "批次辨識功能即將推出")
    
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
            f"<p>雙引擎智能融合，自動異常檢測</p>"
        )
