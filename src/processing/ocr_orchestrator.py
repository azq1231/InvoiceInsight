"""Main OCR orchestrator coordinating all processing steps"""

import logging
from typing import Dict, Optional, List

# Import both OCR engines
from src.ocr.vision_ocr import VisionOCR
from src.ocr.tesseract_ocr import TesseractOCR

from src.processing.data_extractor import DataExtractor
from src.processing.validator import DataValidator
from src.utils.config import get_config
# Import parsers
from src.processing.general_ledger_parser import is_general_ledger, parse as parse_general_ledger

logger = logging.getLogger(__name__)


class OCROrchestrator:
    """Orchestrates the complete OCR processing pipeline."""
    
    def __init__(self, google_credentials: Optional[dict] = None):
        """
        Initializes the orchestrator with available OCR engines.

        Args:
            google_credentials (Optional[dict]): A dictionary of Google credentials.
                                                 If provided, Google Vision OCR will be enabled.
        """
        self.config = get_config()
        self.vision_ocr = None
        self.tesseract_ocr = None

        # Initialize Google Vision if credentials are provided
        if google_credentials:
            try:
                self.vision_ocr = VisionOCR(credentials_dict=google_credentials)
                logger.info("OCR Orchestrator: Google Vision engine is ENABLED.")
            except Exception as e:
                logger.error(f"OCR Orchestrator: Failed to initialize Google Vision engine: {e}")
        else:
            logger.info("OCR Orchestrator: Google Vision engine is DISABLED (no credentials).")

        # Always initialize Tesseract as a fallback
        try:
            self.tesseract_ocr = TesseractOCR()
            logger.info("OCR Orchestrator: Tesseract engine is available as a fallback.")
        except Exception as e:
            logger.error(f"OCR Orchestrator: Failed to initialize Tesseract engine: {e}")

        self.extractor = DataExtractor()
        self.validator = DataValidator()
    
    def process_image(self, image_bytes: bytes, photo_id: str = None, expense_keywords: Optional[List[str]] = None) -> Dict:
        """
        Process an image through the OCR pipeline.
        It will try Google Vision first if available, otherwise it falls back to Tesseract.

        Args:
            image_bytes (bytes): The image file bytes.
            photo_id (str, optional): An identifier for the photo. Defaults to None.
            expense_keywords (Optional[List[str]], optional): A list of custom expense keywords. Defaults to None.
        """
        ocr_result = None
        logger.info(f"Starting OCR processing for photo: {photo_id or 'unknown'}")

        # Try Google Vision first
        if self.vision_ocr:
            try:
                logger.info("Attempting OCR with Google Vision...")
                ocr_result = self.vision_ocr.recognize_text(image_bytes)
                logger.info(f"Google Vision OCR successful. Confidence: {ocr_result.get('confidence', 0):.2f}")
            except Exception as e:
                logger.error(f"Google Vision OCR failed: {e}. Falling back to Tesseract.")
                ocr_result = None # Ensure ocr_result is None if it fails

        # Fallback to Tesseract if Google Vision is not available or failed
        if not ocr_result and self.tesseract_ocr:
            try:
                logger.info("Attempting OCR with Tesseract...")
                ocr_result = self.tesseract_ocr.recognize_text(image_bytes)
                logger.info(f"Tesseract OCR successful. Confidence: {ocr_result.get('confidence', 0):.2f}")
            except Exception as e:
                logger.error(f"Tesseract OCR also failed: {e}")
                return self._create_failure_response(photo_id, "All OCR engines failed.")

        if not ocr_result:
            return self._create_failure_response(photo_id, "No OCR engines were available or all failed.")

        # --- Post-OCR Processing ---
        try:
            full_text = self.extractor.normalize_full_width(ocr_result.get('full_text', ''))
            
            # 步驟 1: 總是先執行通用提取器，以獲取包含日期在內的基礎資料。
            final_extracted_data = self.extractor.extract_from_text(full_text, ocr_result.get('blocks'))
            
            # 步驟 2: 如果有更精確的自訂解析器匹配，讓其結果選擇性地覆蓋通用結果。
            custom_data = None
            if is_general_ledger(full_text):
                # Pass the custom keywords to the parser
                custom_data = parse_general_ledger(full_text, expense_keywords=expense_keywords) # No edited_items here, as this is initial parse

            if custom_data:
                # 自訂解析器對其項目列表有最高優先權。
                for key in ['items', 'declared_total', 'calculated_total', 'date']:
                    if key in custom_data:
                        final_extracted_data[key] = custom_data[key]
                # 合併自訂欄位，例如 'final_balance'
                if 'custom_fields' in custom_data:
                    final_extracted_data.setdefault('custom_fields', {}).update(custom_data['custom_fields'])
           
            # 步驟 4: 驗證資料。
            validated_data = self.validator.validate(final_extracted_data, ocr_result.get('confidence', 0))
           
            # 步驟 5: 最終合併。以提取的資料為基礎，並更新驗證結果。
            final_data = {**final_extracted_data, **validated_data}
            
            return {
                'photo_id': photo_id,
                'ocr_result': ocr_result,
                'extracted_data': final_data,
                'status': 'success',
                'needs_review': validated_data.get('has_anomalies', False) or ocr_result.get('confidence', 0) < 0.6
            }
        except Exception as e:
            logger.error(f"Post-OCR processing failed: {e}", exc_info=True)
            return self._create_failure_response(photo_id, f"Post-OCR processing failed: {e}")

    def _create_failure_response(self, photo_id: str, error_message: str) -> dict:
        """Creates a standardized failure response dictionary."""
        return {
            'photo_id': photo_id,
            'status': 'failed',
            'error': error_message,
            'needs_review': True
        }
