"""Data validation and anomaly detection"""

import logging
from typing import Dict, List, Optional

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class DataValidator:
    """Validate extracted data and detect anomalies"""
    
    def __init__(self):
        self.config = get_config()
        self.check_total_mismatch = self.config.get('validation.anomaly_detection.check_total_mismatch', True)
        self.mismatch_tolerance = self.config.get('validation.anomaly_detection.mismatch_tolerance', 0.01)
        self.check_tax_rate = self.config.get('validation.anomaly_detection.check_tax_rate', True)
        self.expected_tax_rate = self.config.get('validation.anomaly_detection.expected_tax_rate', 0.05)
        logger.info("Data validator initialized")
    
    def validate(self, extracted_data: Dict, ocr_confidence: float) -> Dict:
        """Validate extracted data and flag anomalies"""
        try:
            anomalies = []
            
            if self.check_total_mismatch:
                total_mismatch = self._check_total_mismatch(extracted_data)
                if total_mismatch:
                    anomalies.append(total_mismatch)
            
            if self.check_tax_rate:
                tax_anomaly = self._check_tax_rate(extracted_data)
                if tax_anomaly:
                    anomalies.append(tax_anomaly)
            
            if ocr_confidence < 0.7:
                anomalies.append({
                    'type': 'low_confidence',
                    'message': f'OCR 信心度過低: {ocr_confidence:.2f}',
                    'severity': 'warning'
                })
            
            for item in extracted_data.get('items', []):
                if ocr_confidence < 0.6:
                    item['needs_review'] = True
            
            extracted_data['anomalies'] = anomalies
            extracted_data['has_anomalies'] = len(anomalies) > 0
            
            logger.info(f"Validation completed: {len(anomalies)} anomalies detected")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return extracted_data
    
    def _check_total_mismatch(self, data: Dict) -> Optional[Dict]:
        """Check if item totals match declared total"""
        items = data.get('items', [])
        declared_total = data.get('declared_total') # Can be None
        calculated_total = data.get('calculated_total', 0.0)
        
        if declared_total is None or declared_total == 0:
            return None
        
        diff = abs(calculated_total - declared_total)
        tolerance = max(declared_total * self.mismatch_tolerance, 1.0)
        
        if diff > tolerance:
            return {
                'type': 'total_mismatch',
                'message': f'總額不符: 計算={calculated_total:.2f}, 宣告={declared_total:.2f}, 差額={diff:.2f}',
                'severity': 'error',
                'calculated_total': calculated_total,
                'declared_total': declared_total,
                'difference': diff
            }
        
        return None
    
    def _check_tax_rate(self, data: Dict) -> Optional[Dict]:
        """Check if tax rate seems abnormal"""
        items = data.get('items', [])
        
        tax_items = [item for item in items if '稅' in item['name'] or 'tax' in item['name'].lower()]
        
        if not tax_items:
            return None
        
        subtotal_items = [item for item in items if item not in tax_items and item['category'] == '支出']
        
        if not subtotal_items:
            return None
        
        subtotal = sum(item['amount'] for item in subtotal_items)
        tax = sum(item['amount'] for item in tax_items)
        
        if subtotal > 0:
            actual_rate = tax / subtotal
            expected_rate = self.expected_tax_rate
            
            if abs(actual_rate - expected_rate) > 0.02:
                return {
                    'type': 'tax_rate_anomaly',
                    'message': f'稅率異常: 實際={actual_rate:.1%}, 預期={expected_rate:.1%}',
                    'severity': 'warning',
                    'actual_rate': actual_rate,
                    'expected_rate': expected_rate
                }
        
        return None
