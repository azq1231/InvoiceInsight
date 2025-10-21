import re
import logging
from datetime import datetime
import math
from typing import Optional, List

logger = logging.getLogger(__name__)

# Keywords that indicate a special expense rule might apply
# These could be moved to config if they become more complex
SPECIAL_EXPENSE_KEYWORDS = ['冷氣外機', '冷氣外机', '順茂', '顺茂']

# --- Shared Regex Patterns ---
DATE_PATTERN_1 = re.compile(r'(\d{2,3})年(\d{1,2})月(\d{1,2})日')
DATE_PATTERN_2 = re.compile(r'(\d{2,3})\s+(\d{1,2})/(\d{1,2})')
# This pattern handles two cases:
# 1. Name and amount are separated by a space (e.g., "#64 50x50"). The name can be anything.
# 2. Name and amount are NOT separated by a space (e.g., "昌雄250x30"). The name must be non-digits.
# The groups are structured to be consistent: group 1 is always the name, group 2 the amount, group 3 the discount.
ITEM_PATTERN_GENERAL = re.compile(r'^(?:(.+?)\s+|([\u4e00-\u9fa5a-zA-Z#]+))\s*([0-9,.]+)(?:\s*[xX×]\s*(\d+))?')

def is_general_ledger(ocr_text: str) -> bool:
    """
    Check if the OCR text matches a general ledger format.
    This is now a broad check, as this parser is intended to be a general-purpose engine.
    It triggers if it finds a date, a standalone number, or an item with a price.
    """
    lines = ocr_text.strip().split('\n')
    has_standalone_number = any(line.strip().isdigit() for line in lines)
    
    has_date = any(DATE_PATTERN_1.search(line) or DATE_PATTERN_2.search(line) for line in lines)
    
    # Check for at least one item-like pattern (name + number)
    item_pattern = re.compile(r'([\u4e00-\u9fa5a-zA-Z]+)\s*(\d+)')
    has_item = any(item_pattern.search(line) for line in lines)

    # Trigger if any of these common patterns are found.
    return has_date or has_standalone_number or has_item

def parse(ocr_text: str, expense_keywords: Optional[List[str]] = None) -> dict:
    """Parse a general ledger format from OCR text."""
    # Use provided keywords, or fall back to the default list.
    keywords_to_use = expense_keywords if expense_keywords is not None else SPECIAL_EXPENSE_KEYWORDS
    
    if expense_keywords is not None:
        logger.info(f"Using custom expense keywords for parsing: {keywords_to_use}")
    else:
        logger.info("Using default expense keywords for parsing.")

    anomalies = []
    lines = ocr_text.strip().split('\n')
    declared_total = None
    declared_discount = None
    declared_special_total = None
    declared_special_discount_total = None
    declared_balance = None
    extracted_date = None
    processed_lines = []

    # --- Pre-scan for standalone numbers to correctly assign total and balance ---
    standalone_numbers = [line for line in lines if line.strip().isdigit()]
    if len(standalone_numbers) >= 1:
        # The first standalone number is the declared total income
        declared_total = float(standalone_numbers[0])
        logger.info(f"Found declared total income: {declared_total}")
    if len(standalone_numbers) >= 2:
        # The last standalone number is the declared balance
        declared_balance = float(standalone_numbers[-1])
        logger.info(f"Found declared balance: {declared_balance}")
    
    for line in lines:
        line = line.strip()
        
        # Try matching both date patterns
        date_match_1 = DATE_PATTERN_1.search(line)
        date_match_2 = DATE_PATTERN_2.search(line)
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

        # Find special total format: "加 總額 X 折扣總額"
        declared_total_pattern = re.compile(r'加\s*(\d+)\s*X(\d+)')
        declared_match = declared_total_pattern.search(line)
        if declared_match:
            declared_special_total = float(declared_match.group(1))
            declared_special_discount_total = float(declared_match.group(2))
            continue

        # Find declared total (a line with only numbers)
        if line.isdigit():
            # This is now handled by the pre-scan, so we just skip it here.
            continue
        
        # Find declared discount (a line starting with x)
        if line.startswith('x') and line[1:].isdigit():
            if declared_discount is None: # Take the first one
                declared_discount = float(line[1:])
            continue # Don't add this line
        
        if line: # Avoid adding empty lines
            processed_lines.append(line)

    # --- Parse Items ---
    income_items = []
    expense_items = []

    for line in processed_lines:
        match = ITEM_PATTERN_GENERAL.match(line)
        if match:
            # Group 1 is for names with spaces, Group 2 for names without. One will be None.
            name = (match.group(1) or match.group(2) or '').strip()
            amount_str = match.group(3)
            discount_str = match.group(4)

            try:
                if not name: continue # Skip if name is empty
                amount = float(amount_str.replace(',', ''))
                discount = int(discount_str) if discount_str else 0
            except ValueError:
                anomalies.append(f"無法解析金額或折扣: '{line}'")
                continue

            # Rule: Item name should not be purely numeric
            if name.isdigit():
                anomalies.append(f"項目名稱不應為純數字: '{line}'")
                continue # Skip this invalid item
            
            item_data = {
                'name': name,
                'amount': amount,
                'discount': discount, # Add discount to the item
                'needs_review': False,
                'review_reason': ''
            }

            # Categorize as expense or income based on keywords
            is_expense = any(keyword.strip() in name for keyword in keywords_to_use if keyword.strip())
            if is_expense:
                item_data['category'] = '支出'
                expense_items.append(item_data)
            else:
                item_data['category'] = '收入'
                income_items.append(item_data)
        else:
            # If a line in processed_lines doesn't match the item pattern, flag it.
            anomalies.append(f"無法解析的項目: '{line}'")

    # --- Calculations & Validation ---
    all_items = income_items + expense_items
    calculated_total_income = sum(item['amount'] for item in income_items)
    calculated_total_discount = sum(item['discount'] for item in all_items)

    # --- Special Balance Calculation ---
    # Apply the formula to each expense item individually, then sum them up.
    calculated_expense = sum(
        math.floor((item['amount'] * 0.1) / 10) * 10 for item in expense_items
    )
    final_balance = calculated_total_income - calculated_expense

    # Use the special declared total if found, otherwise the general one
    final_declared_total = declared_special_total if declared_special_total is not None else (declared_total or None)

    if final_declared_total is not None and not abs(final_declared_total - calculated_total_income) < 0.01:
        anomalies.append(f"總額不符：計算總額 ({calculated_total_income}) 與宣告總額 ({final_declared_total}) 不一致！")

    # --- Structuring Output ---
    extracted_data = {
        'date': extracted_date,
        'items': all_items,
        'calculated_total': calculated_total_income,
        'declared_total': final_declared_total or calculated_total_income,
        'raw_text': ocr_text,
        'anomalies': anomalies,
        'has_anomalies': len(anomalies) > 0,
        'custom_fields': {
            'final_balance': final_balance,
            'declared_balance': declared_balance,
            'calculated_total_discount': calculated_total_discount,
            'declared_discount': declared_discount,
            'declared_special_discount_total': declared_special_discount_total
        }
    }
    
    return extracted_data