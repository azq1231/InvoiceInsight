"""Extract structured data from OCR text using patterns and validation"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extract structured expense data from OCR text"""
    
    def __init__(self):
        self.config = get_config()
        self.date_pattern = self.config.get('validation.regex.date')
        self.amount_pattern = self.config.get('validation.regex.amount')
        self.currency_pattern = self.config.get('validation.regex.currency')
        logger.info("Data extractor initialized")
    
    def extract_from_text(self, ocr_text: str, blocks: List[Dict] = None) -> Dict:
        """Extract structured data from OCR text"""
        try:
            lines = ocr_text.strip().split('\n')
            
            date = self._extract_date(lines[0] if lines else '')
            
            items, declared_total = self._extract_items_and_total(lines[1:] if len(lines) > 1 else [])
            
            calculated_total = sum(item['amount'] for item in items if item['category'] != '總計')
            
            result = {
                'date': date,
                'items': items,
                'calculated_total': calculated_total,
                'declared_total': declared_total if declared_total is not None else calculated_total,
                'raw_text': ocr_text
            }
            
            logger.info(f"Extracted {len(items)} items, calculated: {calculated_total}, declared: {result['declared_total']}")
            return result
            
        except Exception as e:
            logger.error(f"Data extraction failed: {e}")
            raise
    
    def _extract_date(self, first_line: str) -> str:
        """Extract date from first line"""
        match = re.search(self.date_pattern, first_line)
        if match:
            return match.group(0)
        
        return datetime.now().strftime('%Y-%m-%d')
    
    def _extract_items_and_total(self, lines: List[str]) -> Tuple[List[Dict], Optional[float]]:
        """Extract items and declared total from text lines"""
        items = []
        declared_total = None
        
        total_keywords = ['總計', '合計', '總額', 'total', '小計']
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            is_total_line = any(keyword in line.lower() for keyword in total_keywords)
            
            item = self._parse_item_line(line)
            if item:
                if is_total_line:
                    declared_total = item['amount']
                    item['category'] = '總計'
                items.append(item)
        
        return items, declared_total
    
    def _parse_item_line(self, line: str) -> Optional[Dict]:
        """Parse a single line to extract item name and amount"""
        amount_match = re.search(self.amount_pattern, line)
        
        if amount_match:
            amount_str = amount_match.group(0).replace(',', '')
            try:
                amount = float(amount_str)
            except:
                return None
            
            name = line[:amount_match.start()].strip()
            
            name = re.sub(self.currency_pattern, '', name).strip()
            
            if not name:
                name = "未知項目"
            
            category = self._categorize_item(name, amount)
            
            return {
                'name': name,
                'amount': amount,
                'category': category,
                'needs_review': False
            }
        
        return None
    
    def _categorize_item(self, name: str, amount: float) -> str:
        """Categorize item as income, expense, or balance"""
        income_keywords = ['收入', '薪資', '獎金', '退款']
        balance_keywords = ['結餘', '餘額', '總計', '合計']
        
        name_lower = name.lower()
        
        for keyword in balance_keywords:
            if keyword in name_lower:
                return '結餘'
        
        for keyword in income_keywords:
            if keyword in name_lower:
                return '收入'
        
        return '支出'
    
    def normalize_full_width(self, text: str) -> str:
        """Convert full-width characters to half-width"""
        result = []
        for char in text:
            code = ord(char)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            elif code == 0x3000:
                result.append(' ')
            else:
                result.append(char)
        return ''.join(result)
