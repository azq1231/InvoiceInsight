import re
import logging
from datetime import datetime
import math
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Keywords that indicate a special expense rule might apply
# These could be moved to config if they become more complex
SPECIAL_EXPENSE_KEYWORDS = ['冷氣外機', '冷氣外机', '順茂', '顺茂', '匯']

# --- Shared Regex Patterns ---
DATE_PATTERN_1 = re.compile(r'(\d{2,3})年(\d{1,2})月(\d{1,2})日')
DATE_PATTERN_2 = re.compile(r'(\d{2,3})\s+(\d{1,2})/(\d{1,2})')
# New pattern for compact dates like "11410/21"
DATE_PATTERN_3 = re.compile(r'^(1\d{2})(\d{1,2})/(\d{1,2})')
# Pattern for items where name and amount are NOT separated by a space (e.g., "昌雄250")
ITEM_PATTERN_NO_SPACE = re.compile(r'^([\u4e00-\u9fa5a-zA-Z#]+)([0-9,.]+)(.*)$')
# Pattern for items where name and amount ARE separated by a space (e.g., "#64 50")
# This is the general pattern that also handles discounts.
ITEM_PATTERN_WITH_SPACE = re.compile(r'^(.+?)\s*[:：\s、]\s*([0-9,.]+)(.*)$')
# New pattern to specifically handle cases like "AA 4.330" -> name: "AA 4", amount: "330"
# It greedily captures the last number block as the amount.
ITEM_PATTERN_NAME_WITH_NUM = re.compile(r'^(.+?)\s+([0-9,.]+)$')

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

def _calculate_summary_from_items(
    income_items: List[Dict], 
    expense_items: List[Dict], 
    ocr_text: str, 
    declared_total: Optional[float], 
    declared_discount: Optional[float], 
    declared_special_total: Optional[float], 
    declared_special_discount_total: Optional[float], 
    declared_balance: Optional[float], 
    extracted_date: Optional[str]
) -> Dict:
    """
    Helper function to calculate summary data from a given list of income and expense items.
    This allows re-calculation after items have been potentially edited.
    """
    all_items = income_items + expense_items
    calculated_total_income = sum(item['amount'] for item in income_items)
    calculated_total_discount = sum(item['discount'] for item in all_items)

    calculated_expense = sum(
        round((item['amount'] * 0.1) / 10) * 10 for item in expense_items
    )
    final_balance = calculated_total_income - calculated_expense

    final_declared_total = declared_special_total if declared_special_total is not None else (declared_total or None)

    anomalies = [] # This helper doesn't generate item-specific anomalies, but can check totals.
    if final_declared_total is not None and not abs(final_declared_total - calculated_total_income) < 0.01:
        anomalies.append(f"總額不符：計算總額 ({calculated_total_income}) 與宣告總額 ({final_declared_total}) 不一致！")

    return {
        'date': extracted_date,
        'items': all_items,
        'calculated_total': calculated_total_income,
        'declared_total': final_declared_total, # Keep it as None if not found, don't fallback to calculated.
        'raw_text': ocr_text, # Keep original raw text for context
        'anomalies': anomalies,
        'has_anomalies': len(anomalies) > 0,
        'custom_fields': {
            'final_balance': final_balance,
            'declared_balance': declared_balance,
            'calculated_total_discount': calculated_total_discount,
            'declared_discount': declared_discount, # This is from 'x 50' line
            'declared_special_total': declared_special_total, # From '加 總額 X 折扣總額'
            'declared_special_discount_total': declared_special_discount_total
        }
    }

def parse(ocr_text: str, expense_keywords: Optional[List[str]] = None) -> dict:
    """Parse a general ledger format from OCR text."""
    # Use provided keywords, or fall back to the default list.
    keywords_to_use = expense_keywords if expense_keywords is not None else SPECIAL_EXPENSE_KEYWORDS
    
    if expense_keywords is not None:
        logger.info(f"Using custom expense keywords for parsing: {keywords_to_use}")
    else:
        logger.info("Using default expense keywords for parsing.")

    # --- Pre-process text to fix common OCR errors ---
    # Replace dots between a non-digit and a digit with a space (e.g., "弘瑜.200" -> "弘瑜 200")
    ocr_text = re.sub(r'([\u4e00-\u9fa5a-zA-Z])\.(?=\d)', r'\1 ', ocr_text)

    anomalies = []
    original_lines = ocr_text.strip().split('\n')
    lines = []
    # Heuristic to split lines that were incorrectly merged by OCR with a '/'
    # e.g., "磊成匯x101/0顺天9487" -> "磊成匯x10" and "10/20顺天9487"
    # This regex looks for a pattern like (text)(digit)/(digit)(text)
    # We add a condition that both parts must contain some non-digit characters to avoid splitting dates.
    merge_split_pattern = re.compile(r'^(.*[a-zA-Z\u4e00-\u9fa5].*\d)\s*/\s*(\d.*[a-zA-Z\u4e00-\u9fa5].*)$')
    for line in original_lines:
        match = merge_split_pattern.match(line)
        if match:
            logger.info(f"Splitting merged line: '{line}' -> '{match.group(1)}' and '{match.group(2)}'")
            lines.append(match.group(1))
            lines.append(match.group(2))
        else:
            lines.append(line)

    declared_total = None
    declared_discount = None
    declared_special_total = None
    declared_special_discount_total = None
    declared_balance = None
    extracted_date = None
    unmatched_lines = [] # Initialize here

    # --- First pass: Extract dates, special totals, discounts, and collect unmatched lines ---
    for line in lines: # Re-introducing the loop
        line = line.strip() # Strip whitespace for each line

        # Try matching both date patterns
        date_match_1 = DATE_PATTERN_1.search(line)
        date_match_2 = DATE_PATTERN_2.search(line)
        date_match_3 = DATE_PATTERN_3.search(line)
        date_match = date_match_1 or date_match_2 or date_match_3

        if date_match:
            if extracted_date is None: # Only take the first valid date found
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

        # Find declared discount (a line starting with x)
        discount_match = re.match(r'^[xX]\s*(\d+\.?\d*)$', line)
        if discount_match:
            if declared_discount is None: # Take the first one
                declared_discount = float(discount_match.group(1))
            continue # Don't process this line as an item
        
        if line: # Avoid adding empty lines
            unmatched_lines.append(line)

    # --- Parse Items ---
    income_items = []
    expense_items = []
    unmatched_lines_after_parsing = []

    # --- Pre-filter processed_lines to remove likely OCR noise from horizontal lines ---
    final_lines_to_process = []
    noise_pattern = re.compile(
        r"^[a-zA-Z]{1,4}\s+\d+$"  # Matches short words like "gma 201"
    )
    for line in unmatched_lines: # First, filter out all the noise
        # Heuristic 1: Very short lines with non-alphanumeric/non-CJK symbols are likely noise.
        # e.g., "男】", "】"
        if len(line) <= 3 and re.search(r'[^\u4e00-\u9fa5a-zA-Z0-9\s,.#]', line):
            logger.debug(f"Skipping likely noise line (short, with symbols): '{line}'")
            continue
        # Heuristic 2: Short English-like word followed by a number.
        if noise_pattern.match(line) and not any(kw in line for kw in keywords_to_use):
            logger.debug(f"Skipping likely noise line (short word + number): '{line}'")
            continue
        # Heuristic 3: Line contains only CJK characters and is likely noise from a separator line
        if len(line) > 3 and re.fullmatch(r'[\u4e00-\u9fa5]+', line):
            logger.debug(f"Skipping likely noise line (all CJK, potential separator): '{line}'")
            continue
        final_lines_to_process.append(line) # Add clean lines to the list for parsing

    # --- Stateful Parsing Logic ---
    # This logic can associate a name on one line with an amount on a subsequent line.
    last_seen_name = None
    
    # Now, iterate through the CLEANED list of lines
    for i, line in enumerate(final_lines_to_process):
        # Check if the previous clean line was a name for the current numeric line
        if i > 0 and re.fullmatch(r'[0-9,.]+', line) and not re.search(r'\d', final_lines_to_process[i-1]):
            last_seen_name = final_lines_to_process[i-1].strip().rstrip('.')
        else:
            last_seen_name = None

        # If the current line is just a number, it might belong to the previously seen name.
        if re.fullmatch(r'[0-9,.]+', line) and last_seen_name:
            # We found a number that likely corresponds to the name on the previous line.
            # Combine them into a single logical line for the parser.
            line = f"{last_seen_name} {line}"
            logger.debug(f"Combined cross-line item: '{line}'")
            last_seen_name = None # Reset after combining

        # Strategy: Match from most specific to most general pattern for better accuracy.
        # 1. Try the new pattern for names containing numbers first.
        # 2. Fallback to the general pattern with space/colon separators (handles discounts).
        # 3. Finally, try the pattern for items with no space.
        match_name_with_num = ITEM_PATTERN_NAME_WITH_NUM.match(line)
        match_with_space = ITEM_PATTERN_WITH_SPACE.match(line)
        match_no_space = ITEM_PATTERN_NO_SPACE.match(line)

        match = match_name_with_num or match_with_space or match_no_space

        if match:
            name = match.group(1).strip()
            amount_part = match.group(2)
            remaining_line = match.group(3).strip() if len(match.groups()) > 2 else ""

            # Rule: The name part cannot be empty or just spaces.
            if not name:
                unmatched_lines_after_parsing.append(line); continue

            # Now, parse the discount from the remaining part of the line
            discount = 0
            # The discount might be in the second or third group depending on the regex that matched.
            # Let's check both `amount_part` and `remaining_line`.
            discount_search_str = amount_part + " " + remaining_line
            discount_match = re.search(r'[xX×]\s*(\d+)', discount_search_str)
            if discount_match:
                discount = int(discount_match.group(1))
                # The actual amount is the part before the 'x'
                amount_str = amount_part.split(discount_match.group(0)[0])[0].strip()
            else:
                amount_str = amount_part

            # --- Post-regex Correction for specific OCR errors ---
            # Heuristic for "AA 4.330" -> name: "AA 4", amount: "330"
            # This pattern is a common OCR error where a space is read as a dot.
            correction_match = re.match(r'^(\d{1,2})\.(\d{2,})$', amount_str)
            if correction_match:
                logger.debug(f"Applying correction for potential space-as-dot OCR error on '{line}'")
                name = f"{name} {correction_match.group(1)}".strip()
                amount_str = correction_match.group(2)

            try:
                if not name: continue # Skip if name is empty
                # Clean the amount string: remove commas, then ensure only one dot remains for float conversion.
                # This handles cases like "800.." or "1,000."
                temp_amount_str = amount_str.replace(',', '')
                numbers_found = re.findall(r'[0-9]+\.?[0-9]*', temp_amount_str) # Find all numbers
                if not numbers_found:
                    raise ValueError("No valid number found in amount string")
                cleaned_amount_str = numbers_found[0] # Take the first valid number found
                amount = float(cleaned_amount_str)
            except ValueError:
                anomalies.append(f"無法解析金額或折扣: '{line}'")
                continue

            # Rule: Item name should not be purely numeric
            if name.isdigit():
                anomalies.append(f"項目名稱不應為純數字: '{line}'")
                continue # Skip this invalid item
            
            # Heuristic: Flag names that are short, all-caps, and non-standard as they are likely OCR errors.
            # e.g., "AA" from "AA 4.330" which should have been "明中 330"
            if len(name) <= 3 and name.isupper() and name.isalpha():
                review_reason = f"項目名稱可能為 OCR 辨識錯誤: '{name}'"
                anomalies.append(f"{review_reason} (來自行: '{line}')")
                # We can still add the item but flag it for review.

            item_data = {
                'name': name,
                'amount': amount,
                'discount': discount, # Add discount to the item
                'needs_review': False,
                'review_reason': ''
            }

            # Categorize as expense or income based on keywords
            # Special case for '匯'
            if '匯' in name:
                item_data['category'] = '匯'
                # For now, '匯' is treated as income for calculation purposes.
                income_items.append(item_data)
                continue

            is_expense = any(keyword.strip() in name for keyword in keywords_to_use if keyword.strip() and keyword.strip() != '匯')
            if is_expense:
                item_data['category'] = '支出'
                expense_items.append(item_data)
            else:
                item_data['category'] = '收入'
                income_items.append(item_data)
        else:
            # If the line was just a name that we successfully combined with a number on the next line,
            # we don't need to do anything with it here.
            is_just_a_name_for_next_line = (
                not re.search(r'\d', line) and 
                i + 1 < len(final_lines_to_process) and 
                re.fullmatch(r'[0-9,.]+', final_lines_to_process[i+1])
            )
            if not is_just_a_name_for_next_line:
                unmatched_lines_after_parsing.append(line)

    # --- Calculations & Validation ---
    # Process the remaining unmatched lines to find total and balance
    # This logic is now part of the _calculate_summary_from_items helper, but we need to find declared_total/balance first.
    temp_declared_total = declared_total
    temp_declared_balance = declared_balance

    standalone_numbers = [line for line in unmatched_lines_after_parsing if line.strip().isdigit()]
    if len(standalone_numbers) >= 1:
        # The largest standalone number is most likely the declared total income
        temp_declared_total = float(max(standalone_numbers, key=float))
        logger.info(f"Found declared total income from unmatched numbers: {temp_declared_total}")
    if len(standalone_numbers) >= 2:
        # The last standalone number is the declared balance
        temp_declared_balance = float(standalone_numbers[-1])
        logger.info(f"Found declared balance from unmatched numbers: {temp_declared_balance}")

    return _calculate_summary_from_items(
        income_items, 
        expense_items, 
        ocr_text, 
        temp_declared_total, 
        declared_discount, 
        declared_special_total, 
        declared_special_discount_total, 
        temp_declared_balance, 
        extracted_date
    )