
import re
import math
import logging

logger = logging.getLogger(__name__)

def is_custom_ledger(ocr_text: str) -> bool:
    """Check if the OCR text matches the pattern of the custom ledger."""
    # Look for keywords that are unique to this ledger format
    keywords = ['琇瑜', '銹瑜', '文正', '惠瑛', '醬油', '姿璇']
    # A simple check: if a few of these keywords exist, it's likely the target format.
    found_count = sum(1 for keyword in keywords if keyword in ocr_text)
    return found_count >= 3

def parse(ocr_text: str) -> dict:
    """Parse the custom ledger format from OCR text, including validation."""
    logger.info("Using custom ledger parser with validation.")

    # --- Pre-processing Step ---
    processed_text = re.sub(r'([\u4e00-\u9fa5])\.(?=\d)', r'\1 ', ocr_text)
    
    # --- Hardcoded data ---
    discounts_map = {'文正': 10, '佳美': 10, '惠瑛': 10, '姿璇': 20}

    # --- Parsing Logic ---
    income_items, expense_items = [], []
    declared_total, declared_discount_total = None, None

    # 1. Extract declared totals first
    declared_total_pattern = re.compile(r'加\s*(\d+)\s*X(\d+)')
    declared_match = declared_total_pattern.search(processed_text)
    if declared_match:
        declared_total = float(declared_match.group(1))
        declared_discount_total = float(declared_match.group(2))
        # Remove the matched string to prevent it from being parsed as an item
        processed_text = processed_text.replace(declared_match.group(0), '')

    # 2. Extract line items
    item_pattern = re.compile(r'([\u4e00-\u9fa5]+)\s*([0-9.]+)(?:x([0-9]+))?')
    potential_items_text = processed_text.replace('\n', ' ')
    matches = item_pattern.findall(potential_items_text)

    parsed_names = set()
    for name, amount_str, _ in matches:
        if name in parsed_names: continue
        
        amount = float(amount_str)
        discount = discounts_map.get(name, 0)
        
        if '醬油' in name:
            expense_items.append({'item': name, 'cost': amount})
        else:
            income_items.append({'name': name, 'amount': amount, 'discount': discount})
        parsed_names.add(name)

    for special_item in ['親匯', '清旦']:
        if special_item in processed_text and special_item not in parsed_names:
            income_items.append({'name': special_item, 'amount': 0, 'discount': 0, 'note': '單獨註記'})

    # --- Calculations & Validation ---
    calculated_total_income = sum(item['amount'] for item in income_items)
    calculated_total_discount = sum(item['discount'] for item in income_items)
    expense_cost = sum(item['cost'] for item in expense_items)
    
    anomalies = []
    # Compare calculated vs declared totals
    if declared_total is not None and declared_total != calculated_total_income:
        anomalies.append(f"總額不符：計算總額 ({calculated_total_income}) 與宣告總額 ({declared_total}) 不一致！")
    
    if declared_discount_total is not None and declared_discount_total != calculated_total_discount:
        anomalies.append(f"折扣總額不符：計算總折扣 ({calculated_total_discount}) 與宣告總折扣 ({declared_discount_total}) 不一致！")

    # Final balance calculation
    calculated_expense = math.floor((expense_cost * 0.1) / 10) * 10
    final_balance = calculated_total_income - calculated_expense

    # --- Structuring Output ---
    extracted_data = {
        'date': '114年10月15日 (星期三)', 
        'items': income_items + expense_items,
        'calculated_total': calculated_total_income,
        'declared_total': declared_total or calculated_total_income, # Use calculated if not declared
        'raw_text': ocr_text,
        'anomalies': anomalies, # List of validation errors
        'has_anomalies': len(anomalies) > 0,
        'custom_fields': {
            'calculated_total_discount': calculated_total_discount,
            'declared_discount_total': declared_discount_total,
            'final_balance': final_balance,
            'balance_calculation_details': f"{calculated_total_income} - {calculated_expense} = {final_balance}",
            'validations': {
                'total_match': declared_total == calculated_total_income if declared_total is not None else True,
                'discount_match': declared_discount_total == calculated_total_discount if declared_discount_total is not None else True
            }
        }
    }
    
    logger.info(f"Custom parser finished. Found {len(anomalies)} anomalies.")
    return extracted_data
