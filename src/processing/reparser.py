"""
A dedicated service for re-parsing existing OCR results without any external dependencies.
"""
import logging
from typing import Dict, Optional, List

from src.processing.data_extractor import DataExtractor
from src.processing.validator import DataValidator
from src.processing.general_ledger_parser import is_general_ledger, parse as parse_general_ledger, _calculate_summary_from_items, SPECIAL_EXPENSE_KEYWORDS

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

    def reprocess(self, ocr_result: Dict, expense_keywords: Optional[List[str]] = None, edited_items: Optional[List[Dict]] = None) -> Dict:
        """
        Takes a full OCR result and re-runs the parsing and validation logic.
        If edited_items are provided, it uses them directly instead of parsing from text.
        """
        try:
            # The frontend sends the whole `lastSuccessfulData` object as `ocr_result`.
            # The actual OCR text is nested inside it.
            nested_ocr_result = ocr_result.get('ocr_result', {})
            full_text = self.extractor.normalize_full_width(nested_ocr_result.get('full_text', ''))

            keywords_to_use = expense_keywords if expense_keywords is not None else SPECIAL_EXPENSE_KEYWORDS
            
            if edited_items:
                logger.info("Reparsing with manually edited items.")
                income_items = []
                expense_items = []
                
                # Re-categorize based on the category from the UI
                for item_data in edited_items:
                    category = item_data.get('category', '收入')
                    if category == '支出':
                        expense_items.append(item_data)
                    elif category == '匯':
                        # '匯' is treated as income for calculation
                        income_items.append(item_data)
                    else: # '收入'
                        income_items.append(item_data)
                
                # Start with a copy of the original data to preserve fields like date.
                original_extracted_data = ocr_result.get('extracted_data', {})
                final_extracted_data = original_extracted_data.copy()

                original_custom_fields = original_extracted_data.get('custom_fields', {})

                # Recalculate the summary based on the edited items
                recalculated_summary = _calculate_summary_from_items(
                    income_items,
                    expense_items,
                    full_text,
                    original_extracted_data.get('declared_total') or 0, # Ensure we pass a number, not None
                    original_custom_fields.get('declared_discount'),
                    original_custom_fields.get('declared_special_total'),
                    original_custom_fields.get('declared_special_discount_total'),
                    original_custom_fields.get('declared_balance'),
                    original_extracted_data.get('date') # Pass the original date
                )
                
                # Update the data with the newly calculated values, preserving the original date and other fields.
                final_extracted_data.update(recalculated_summary)

            else:
                # If no edited items, parse from full_text as usual
                if is_general_ledger(full_text):
                    final_extracted_data = parse_general_ledger(full_text, expense_keywords=keywords_to_use)
                else:
                    # Fallback to generic extractor if not a general ledger
                    final_extracted_data = self.extractor.extract_from_text(full_text, nested_ocr_result.get('blocks'))
           
            # Validate the final data.
            validated_data = self.validator.validate(final_extracted_data, ocr_result.get('confidence', 0))
            
            # Final merge.
            final_data = {**final_extracted_data, **validated_data}
            
            return {'ocr_result': ocr_result, 'extracted_data': final_data, 'status': 'success'}

        except Exception as e:
            logger.error(f"Reprocessing failed: {e}", exc_info=True)
            return {'status': 'failed', 'error': f"Reprocessing failed: {e}"}