"""
A dedicated service for re-parsing existing OCR results without any external dependencies.
"""
import logging
from typing import Dict, Optional, List

from src.processing.data_extractor import DataExtractor
from src.processing.validator import DataValidator
from src.processing.general_ledger_parser import is_general_ledger, parse as parse_general_ledger

logger = logging.getLogger(__name__)

class Reparser:
    """
    A lightweight class to re-process OCR data without needing OCR engines or credentials.
    It encapsulates the post-processing logic.
    """
    def __init__(self):
        self.extractor = DataExtractor()
        self.validator = DataValidator()
        logger.info("Reparser initialized.")

    def reprocess(self, ocr_result: Dict, expense_keywords: Optional[List[str]] = None) -> Dict:
        """
        Takes a full OCR result and re-runs the parsing and validation logic.
        """
        try:
            full_text = self.extractor.normalize_full_width(ocr_result.get('full_text', ''))
            
            # Step 1: Always run the generic extractor first to get baseline data.
            final_extracted_data = self.extractor.extract_from_text(full_text, ocr_result.get('blocks'))
            
            # Step 2: If a more specific parser matches, let its results selectively override.
            custom_data = None
            if is_general_ledger(full_text):
                custom_data = parse_general_ledger(full_text, expense_keywords=expense_keywords)

            if custom_data:
                # Selectively update the extracted data with the more accurate custom results.
                for key in ['items', 'declared_total', 'calculated_total', 'date']:
                    if key in custom_data:
                        final_extracted_data[key] = custom_data[key]
                if 'custom_fields' in custom_data:
                    final_extracted_data.setdefault('custom_fields', {}).update(custom_data['custom_fields'])
           
            # Step 3: Validate the final data.
            validated_data = self.validator.validate(final_extracted_data, ocr_result.get('confidence', 0))
            
            # Step 4: Final merge.
            final_data = {**final_extracted_data, **validated_data}
            
            return {'ocr_result': ocr_result, 'extracted_data': final_data, 'status': 'success'}

        except Exception as e:
            logger.error(f"Reprocessing failed: {e}", exc_info=True)
            return {'status': 'failed', 'error': f"Reprocessing failed: {e}"}