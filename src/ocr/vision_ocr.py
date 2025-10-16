"""Google Cloud Vision API OCR engine"""

import logging
from typing import Dict, List, Tuple
from google.cloud import vision
from google.oauth2.credentials import Credentials
import io

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class VisionOCR:
    """Google Cloud Vision API OCR engine with confidence scoring"""
    
    def __init__(self, credentials: Credentials = None):
        self.config = get_config()
        self.client = vision.ImageAnnotatorClient(credentials=credentials)
        logger.info("Google Cloud Vision OCR initialized")
    
    def recognize_text(self, image_bytes: bytes) -> Dict:
        """Perform OCR on image bytes using Vision API"""
        try:
            image = vision.Image(content=image_bytes)
            
            feature_type = self.config.get('ocr.google_vision.feature_type', 'DOCUMENT_TEXT_DETECTION')
            
            if feature_type == 'DOCUMENT_TEXT_DETECTION':
                response = self.client.document_text_detection(image=image)
                return self._parse_document_text_response(response)
            else:
                response = self.client.text_detection(image=image)
                return self._parse_text_response(response)
                
        except Exception as e:
            logger.error(f"Vision OCR failed: {e}")
            raise
    
    def _parse_document_text_response(self, response) -> Dict:
        """Parse DOCUMENT_TEXT_DETECTION response"""
        if response.error.message:
            raise Exception(f"Vision API error: {response.error.message}")
        
        result = {
            'engine': 'google_vision',
            'full_text': '',
            'blocks': [],
            'confidence': 0.0
        }
        
        if not response.full_text_annotation:
            return result
        
        result['full_text'] = response.full_text_annotation.text
        
        total_confidence = 0
        block_count = 0
        
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                block_text = ''
                block_confidence = 0
                word_count = 0
                
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        word_text = ''.join([symbol.text for symbol in word.symbols])
                        block_text += word_text + ' '
                        block_confidence += word.confidence
                        word_count += 1
                
                if word_count > 0:
                    avg_confidence = block_confidence / word_count
                    result['blocks'].append({
                        'text': block_text.strip(),
                        'confidence': avg_confidence,
                        'bounding_box': self._get_bounding_box(block.bounding_box)
                    })
                    total_confidence += avg_confidence
                    block_count += 1
        
        if block_count > 0:
            result['confidence'] = total_confidence / block_count
        
        logger.info(f"Vision OCR completed: {block_count} blocks, confidence: {result['confidence']:.2f}")
        return result
    
    def _parse_text_response(self, response) -> Dict:
        """Parse TEXT_DETECTION response"""
        if response.error.message:
            raise Exception(f"Vision API error: {response.error.message}")
        
        result = {
            'engine': 'google_vision',
            'full_text': '',
            'blocks': [],
            'confidence': 0.0
        }
        
        if not response.text_annotations:
            return result
        
        result['full_text'] = response.text_annotations[0].description if response.text_annotations else ''
        
        total_confidence = 0
        for annotation in response.text_annotations[1:]:
            confidence = getattr(annotation, 'confidence', 0.9)
            result['blocks'].append({
                'text': annotation.description,
                'confidence': confidence,
                'bounding_box': self._get_bounding_box(annotation.bounding_poly)
            })
            total_confidence += confidence
        
        if len(result['blocks']) > 0:
            result['confidence'] = total_confidence / len(result['blocks'])
        
        logger.info(f"Vision OCR completed: {len(result['blocks'])} annotations, confidence: {result['confidence']:.2f}")
        return result
    
    def _get_bounding_box(self, bounding_poly) -> Dict:
        """Extract bounding box coordinates"""
        vertices = bounding_poly.vertices
        return {
            'x': vertices[0].x,
            'y': vertices[0].y,
            'width': vertices[2].x - vertices[0].x,
            'height': vertices[2].y - vertices[0].y
        }
