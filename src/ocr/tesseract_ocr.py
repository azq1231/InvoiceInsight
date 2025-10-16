"""Tesseract OCR engine with image preprocessing"""

import logging
from typing import Dict, List
import pytesseract
import cv2
import numpy as np
from PIL import Image
import io

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class TesseractOCR:
    """Tesseract OCR engine with skew correction and preprocessing"""
    
    def __init__(self):
        self.config = get_config()
        self.language = self.config.get('ocr.tesseract.language', 'chi_tra+eng')
        self.psm_config = self.config.get('ocr.tesseract.config', '--psm 6')
        logger.info(f"Tesseract OCR initialized with language: {self.language}")
    
    def recognize_text(self, image_bytes: bytes) -> Dict:
        """Perform OCR on image bytes using Tesseract"""
        try:
            img_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            preprocessed = self._preprocess_image(image)
            
            data = pytesseract.image_to_data(
                preprocessed,
                lang=self.language,
                config=self.psm_config,
                output_type=pytesseract.Output.DICT
            )
            
            return self._parse_tesseract_output(data)
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR accuracy"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        angle = self._detect_skew(gray)
        if abs(angle) > 0.5:
            gray = self._rotate_image(gray, angle)
            logger.info(f"Image rotated by {angle:.2f} degrees")
        
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        thresh = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        return thresh
    
    def _detect_skew(self, image: np.ndarray) -> float:
        """Detect skew angle in image"""
        try:
            coords = np.column_stack(np.where(image > 0))
            angle = cv2.minAreaRect(coords)[-1]
            
            if angle < -45:
                angle = 90 + angle
            
            return angle
        except:
            return 0.0
    
    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image by given angle"""
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return rotated
    
    def _parse_tesseract_output(self, data: Dict) -> Dict:
        """Parse Tesseract output data"""
        result = {
            'engine': 'tesseract',
            'full_text': '',
            'blocks': [],
            'confidence': 0.0
        }
        
        text_parts = []
        total_confidence = 0
        valid_count = 0
        
        n_boxes = len(data['text'])
        for i in range(n_boxes):
            conf = int(data['conf'][i])
            text = data['text'][i].strip()
            
            if conf > 0 and text:
                text_parts.append(text)
                
                result['blocks'].append({
                    'text': text,
                    'confidence': conf / 100.0,
                    'bounding_box': {
                        'x': data['left'][i],
                        'y': data['top'][i],
                        'width': data['width'][i],
                        'height': data['height'][i]
                    }
                })
                
                total_confidence += conf / 100.0
                valid_count += 1
        
        result['full_text'] = ' '.join(text_parts)
        
        if valid_count > 0:
            result['confidence'] = total_confidence / valid_count
        
        logger.info(f"Tesseract OCR completed: {valid_count} blocks, confidence: {result['confidence']:.2f}")
        return result
