import re
import math
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Keywords that indicate a special expense rule might apply
SPECIAL_EXPENSE_KEYWORDS = ['冷氣外機', '順茂']

def is_custom_ledger_v2(ocr_text: str) -> bool:
    """Check if the OCR text matches the pattern of the second custom ledger."""
    lines = ocr_text.strip().split('\n')
    # This format is identified by having a line with just a number (total) 
    # or a line starting with 'x' (discount).
    has_standalone_number = any(line.strip().isdigit() for line in lines)
    has_standalone_discount = any(line.strip().startswith('x') and line.strip()[1:].isdigit() for line in lines)
    
    # Also check for the specific date formats as a strong indicator
    date_pattern_1 = re.compile(r'(\d{2,3})年(\d{1,2})月(\d{1,2})日')
    date_pattern_2 = re.compile(r'(\d{2,3})\s+(\d{1,2})/(\d{1,2})')
    has_date = any(date_pattern_1.search(line) or date_pattern_2.search(line) for line in lines)
    
    return has_standalone_number or has_standalone_discount or has_date

def parse_v2(ocr_text: str) -> dict:
    """Parse the custom ledger format v2 from OCR text."""
    logger.info("Using custom ledger parser V2.")

    anomalies = []
    # --- DEBUGGING ANOMALY ---
    anomalies.append("DEBUG: V2解析器已成功執行") 

    lines = ocr_text.strip().split('\n')
    
    declared_total = None
    declared_discount = None
    extracted_date = None
    processed_lines = []

    # --- Pre-parsing to extract dates, totals, and discounts ---
    date_pattern_1 = re.compile(r'(\d{2,3})年(\d{1,2})月(\d{1,2})日')
    date_pattern_2 = re.compile(r'(\d{2,3})\s+(\d{1,2})/(\d{1,2})')

    for line in lines:
        line = line.strip()
        
        # Try matching both date patterns
        date_match_1 = date_pattern_1.search(line)
        date_match_2 = date_pattern_2.search(line)
        date_match = date_match_1 or date_match_2

        if date_match:
            if extracted_date is None: # Take the first valid date found
                try:
                    roc_year = int(date_match.group(1))
                    month = int(date_match.group(2))
                    day = int(date_match.group(3))
                    gregorian_year = roc_year + 1911
                    extracted_date = datetime(gregorian_year, month, day).strftime('%Y-%m-%d')
                    logger.info(f"Parsed ROC date: {line} -> {extracted_date}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Could not parse date from line '{line}': {e}")
                    anomalies.append(f"日期格式錯誤: '{line}'")
            continue # Don't process this line as an item

        # Find declared total (a line with only numbers)
        if line.isdigit():
            if declared_total is None: # Take the first one
                declared_total = float(line)
            continue # Don't add this line to be parsed as an item
        
        # Find declared discount (a line starting with x)
        if line.startswith('x') and line[1:].isdigit():
            if declared_discount is None: # Take the first one
                declared_discount = float(line[1:])
            continue # Don't add this line
        
        if line: # Avoid adding empty lines
            processed_lines.append(line)

    # --- Parse Items ---
    items = []
    # Regex updated to not include numbers in the name part, but allows spaces.
    item_pattern = re.compile(r'([\u4e00-\u9fa5a-zA-Z\s]+?)\s*([0-9,.]+)')

    for line in processed_lines:
        match = item_pattern.match(line)
        if match:
            name = match.group(1).strip()
            amount_str = match.group(2).strip().replace(',', '')
            amount = float(amount_str)

            # Rule: Item name should not be purely numeric
            if name.isdigit():
                anomalies.append(f"項目名稱不應為純數字: '{line}'")
                continue # Skip this invalid item
            
            needs_review = any(keyword in name for keyword in SPECIAL_EXPENSE_KEYWORDS)
            review_reason = '此項目可能需要根據底線規則手動調整費用' if needs_review else ''

            items.append({
                'name': name,
                'amount': amount,
                'category': '支出', # Assuming all are expenses unless specified otherwise
                'needs_review': needs_review,
                'review_reason': review_reason
            })
        else:
            # If a line in processed_lines doesn't match the item pattern, flag it.
            anomalies.append(f"無法解析的項目: '{line}'")

    # --- Calculations & Validation ---
    calculated_total = sum(item['amount'] for item in items)

    if declared_total is not None and declared_total != calculated_total:
        anomalies.append(f"總額不符：計算總額 ({calculated_total}) 與宣告總額 ({declared_total}) 不一致！")

    # --- Structuring Output ---
    extracted_data = {
        'date': extracted_date,
        'items': items,
        'calculated_total': calculated_total,
        'declared_total': declared_total or calculated_total,
        'raw_text': ocr_text,
        'anomalies': anomalies,
        'has_anomalies': len(anomalies) > 0,
        'custom_fields': {
            'declared_discount': declared_discount
        }
    }
    
    logger.info(f"Custom parser V2 finished. Found {len(anomalies)} anomalies.")
    return extracted_data