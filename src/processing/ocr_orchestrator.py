"""Main OCR orchestrator coordinating all processing steps"""

import logging
from typing import Dict, Optional
from io import BytesIO
from PIL import Image

from src.ocr.vision_ocr import VisionOCR
from src.ocr.tesseract_ocr import TesseractOCR
from src.processing.ocr_fusion import OCRFusion
from src.processing.data_extractor import DataExtractor
from src.processing.validator import DataValidator
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class OCROrchestrator:
    """Orchestrates the complete OCR processing pipeline"""
    
    def __init__(self, credentials=None):
        self.config = get_config()
        
        self.vision_enabled = self.config.get('ocr.google_vision.enabled', True) and credentials is not None
        self.tesseract_enabled = self.config.get('ocr.tesseract.enabled', True)
        
        self.vision_ocr = VisionOCR(credentials) if self.vision_enabled else None
        self.tesseract_ocr = TesseractOCR() if self.tesseract_enabled else None
        
        self.fusion = OCRFusion()
        self.extractor = DataExtractor()
        self.validator = DataValidator()
        
        if credentials is None:
            logger.info("OCR Orchestrator initialized (Tesseract only mode)")
        else:
            logger.info("OCR Orchestrator initialized (dual-engine mode)")
    
    def process_image(self, image_bytes: bytes, photo_id: str = None) -> Dict:
        """Process image through complete OCR pipeline"""
        try:
            logger.info(f"Starting OCR processing for photo: {photo_id or 'unknown'}")
            
            vision_result = None
            tesseract_result = None
            
            if self.vision_ocr and self.vision_enabled:
                try:
                    vision_result = self.vision_ocr.recognize_text(image_bytes)
                    logger.info(f"Vision OCR completed: confidence={vision_result.get('confidence', 0):.2f}")
                except Exception as e:
                    logger.error(f"Vision OCR failed: {e}")
            
            if self.tesseract_ocr and self.tesseract_enabled:
                try:
                    tesseract_result = self.tesseract_ocr.recognize_text(image_bytes)
                    logger.info(f"Tesseract OCR completed: confidence={tesseract_result.get('confidence', 0):.2f}")
                except Exception as e:
                    logger.error(f"Tesseract OCR failed: {e}")
            
            if not vision_result and not tesseract_result:
                raise Exception("Both OCR engines failed")
            
            if vision_result and tesseract_result:
                ocr_result = self.fusion.fuse_results(vision_result, tesseract_result)
            else:
                ocr_result = vision_result or tesseract_result
            
            full_text = self.extractor.normalize_full_width(ocr_result.get('full_text', ''))
            
            extracted_data = self.extractor.extract_from_text(full_text, ocr_result.get('blocks'))
            
            validated_data = self.validator.validate(extracted_data, ocr_result.get('confidence', 0))
            
            result = {
                'photo_id': photo_id,
                'ocr_result': ocr_result,
                'extracted_data': validated_data,
                'status': 'success',
                'needs_review': validated_data.get('has_anomalies', False) or ocr_result.get('confidence', 0) < 0.6
            }
            
            logger.info(f"OCR processing completed successfully for photo: {photo_id}")
            return result
            
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {
                'photo_id': photo_id,
                'status': 'failed',
                'error': str(e),
                'needs_review': True
            }
