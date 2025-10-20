"""Tesseract OCR engine with image preprocessing"""

import logging
from typing import Dict, List
import pytesseract
import cv2
import numpy as np
from PIL import Image
import io
import os
import time

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
        """Perform OCR on image bytes using Tesseract, splitting the image into two columns."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            image = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            h, w = image.shape[:2]
            mid_x = w // 2
            
            # Define left and right ROIs (Regions of Interest)
            rois = [
                (image[0:h, 0:mid_x], 0),         # Left half, offset 0
                (image[0:h, mid_x:w], mid_x)      # Right half, offset mid_x
            ]
            
            # Initialize a combined data dictionary
            combined_data = {
                'level': [], 'page_num': [], 'block_num': [], 'par_num': [], 'line_num': [], 'word_num': [],
                'left': [], 'top': [], 'width': [], 'height': [], 'conf': [], 'text': []
            }

            for roi, x_offset in rois:
                preprocessed_roi = self._preprocess_image(roi)
                
                data = pytesseract.image_to_data(
                    preprocessed_roi,
                    lang=self.language,
                    config=self.psm_config,
                    output_type=pytesseract.Output.DICT
                )
                
                # Append data from this ROI to the combined_data, adjusting coordinates
                num_boxes = len(data['text'])
                for i in range(num_boxes):
                    for key in combined_data.keys():
                        if key == 'left':
                            combined_data[key].append(data[key][i] + x_offset)
                        else:
                            combined_data[key].append(data[key][i])

            # --- DEBUG: Draw bounding boxes on the original image ---
            debug_image = image.copy()
            if len(debug_image.shape) == 2:
                debug_image = cv2.cvtColor(debug_image, cv2.COLOR_GRAY2BGR)

            n_boxes = len(combined_data['level'])
            for i in range(n_boxes):
                if int(combined_data['conf'][i]) > -1:
                    (x, y, w, h) = (combined_data['left'][i], combined_data['top'][i], combined_data['width'][i], combined_data['height'][i])
                    cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 0), 2)

            debug_dir = 'data/debug'
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = int(time.time())
            debug_image_path = os.path.join(debug_dir, f'tesseract_debug_split_{timestamp}.png')
            cv2.imwrite(debug_image_path, debug_image)
            logger.info(f"Debug image with split-column boxes saved to: {debug_image_path}")
            # --- END DEBUG ---

            return self._parse_tesseract_output(combined_data)
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR accuracy"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        thresh = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        return thresh
    
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
