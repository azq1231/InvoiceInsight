"""Centralized logging configuration"""

import logging
import logging.handlers
import os
from pathlib import Path
import yaml


def setup_logging():
    """Configure application-wide logging with rotation"""
    with open('config/settings.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    log_config = config.get('logging', {})
    log_dir = Path(log_config.get('log_dir', 'data/logs'))
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / 'app.log'
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    max_bytes = log_config.get('max_file_size', 10485760)
    backup_count = log_config.get('backup_count', 5)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logging.info("Logging system initialized")
