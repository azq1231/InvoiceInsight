#!/usr/bin/env python3
"""
Enterprise-grade OCR Expense Tracking Application
Main entry point for the PyQt5 desktop application
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.gui.main_window import MainWindow
from src.utils.logger import setup_logging


def main():
    """Main application entry point"""
    setup_logging()
    
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("OCR Expense Tracker")
    app.setOrganizationName("ExpenseOCR")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
