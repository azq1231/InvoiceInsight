import logging
from google.cloud import vision
from google.oauth2.credentials import Credentials
from src.utils.config import get_config

logger = logging.getLogger(__name__)

class VisionOCR:
    """Google Cloud Vision API OCR engine."""

    def __init__(self, credentials_dict: dict):
        try:
            self.credentials = Credentials(**credentials_dict)
            self.client = vision.ImageAnnotatorClient(credentials=self.credentials)
            self.config = get_config()
            logger.info("Google Cloud Vision OCR initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud Vision OCR: {e}")
            raise

    def recognize_text(self, image_bytes: bytes) -> dict:
        """Performs OCR on image bytes using the Vision API."""
        try:
            image = vision.Image(content=image_bytes)
            
            feature_type = self.config.get('ocr.google_vision.feature_type', 'DOCUMENT_TEXT_DETECTION')
            
            if feature_type == 'DOCUMENT_TEXT_DETECTION':
                response = self.client.document_text_detection(image=image)
            else:
                response = self.client.text_detection(image=image)

            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")

            return self._parse_response(response)

        except Exception as e:
            logger.error(f"Vision OCR recognition failed: {e}")
            raise

    def _parse_response(self, response) -> dict:
        """Parses the Vision API response into a standardized format."""
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
                block_confidence = block.confidence
                
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        word_text = ''.join([symbol.text for symbol in word.symbols])
                        block_text += word_text + ' '
                
                if block_text:
                    result['blocks'].append({
                        'text': block_text.strip(),
                        'confidence': block_confidence,
                        'bounding_box': self._get_bounding_box(block.bounding_box)
                    })
                    total_confidence += block_confidence
                    block_count += 1
        
        if block_count > 0:
            result['confidence'] = total_confidence / block_count
        
        logger.info(f"Vision OCR completed: {block_count} blocks, confidence: {result['confidence']:.2f}")
        return result

    def _get_bounding_box(self, bounding_poly) -> dict:
        """Extracts bounding box coordinates from a bounding poly."""
        if not bounding_poly or not bounding_poly.vertices:
            return {'x': 0, 'y': 0, 'width': 0, 'height': 0}
        
        x_coords = [v.x for v in bounding_poly.vertices]
        y_coords = [v.y for v in bounding_poly.vertices]
        
        return {
            'x': min(x_coords),
            'y': min(y_coords),
            'width': max(x_coords) - min(x_coords),
            'height': max(y_coords) - min(y_coords)
        }
