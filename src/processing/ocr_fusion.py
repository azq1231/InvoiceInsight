"""Weighted Dempster-Shafer fusion algorithm for combining OCR results"""

import logging
from typing import Dict, List, Tuple
import numpy as np

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class OCRFusion:
    """Weighted Dempster-Shafer (W-DST) fusion for combining OCR engine results"""
    
    def __init__(self):
        self.config = get_config()
        self.vision_weight = self.config.get('ocr.fusion.google_vision_weight', 0.7)
        self.tesseract_weight = self.config.get('ocr.fusion.tesseract_weight', 0.3)
        self.min_confidence = self.config.get('ocr.fusion.min_confidence_threshold', 0.5)
        logger.info(f"OCR Fusion initialized: Vision={self.vision_weight}, Tesseract={self.tesseract_weight}")
    
    def fuse_results(self, vision_result: Dict, tesseract_result: Dict) -> Dict:
        """Fuse results from Google Vision and Tesseract using W-DST"""
        try:
            fused = {
                'full_text': '',
                'blocks': [],
                'confidence': 0.0,
                'source': 'fused',
                'vision_confidence': vision_result.get('confidence', 0),
                'tesseract_confidence': tesseract_result.get('confidence', 0)
            }
            
            vision_conf = vision_result.get('confidence', 0)
            tesseract_conf = tesseract_result.get('confidence', 0)
            
            if vision_conf > tesseract_conf and vision_conf >= self.min_confidence:
                logger.info("Using Google Vision result (higher confidence)")
                fused['full_text'] = vision_result.get('full_text', '')
                fused['blocks'] = vision_result.get('blocks', [])
                fused['confidence'] = vision_conf
                fused['primary_engine'] = 'google_vision'
            elif tesseract_conf >= self.min_confidence:
                logger.info("Using Tesseract result")
                fused['full_text'] = tesseract_result.get('full_text', '')
                fused['blocks'] = tesseract_result.get('blocks', [])
                fused['confidence'] = tesseract_conf
                fused['primary_engine'] = 'tesseract'
            else:
                fused_blocks = self._fuse_blocks(
                    vision_result.get('blocks', []),
                    tesseract_result.get('blocks', [])
                )
                fused['blocks'] = fused_blocks
                fused['full_text'] = ' '.join([b['text'] for b in fused_blocks])
                fused['confidence'] = self._calculate_overall_confidence(fused_blocks)
                fused['primary_engine'] = 'weighted_fusion'
            
            logger.info(f"Fusion completed: confidence={fused['confidence']:.2f}, engine={fused.get('primary_engine')}")
            return fused
            
        except Exception as e:
            logger.error(f"Fusion failed: {e}")
            return vision_result if vision_result.get('confidence', 0) > tesseract_result.get('confidence', 0) else tesseract_result
    
    def _fuse_blocks(self, vision_blocks: List[Dict], tesseract_blocks: List[Dict]) -> List[Dict]:
        """Fuse text blocks using weighted Dempster-Shafer theory"""
        fused_blocks = []
        
        for v_block in vision_blocks:
            best_match = None
            best_similarity = 0
            
            for t_block in tesseract_blocks:
                similarity = self._calculate_similarity(v_block['text'], t_block['text'])
                if similarity > best_similarity and similarity > 0.5:
                    best_similarity = similarity
                    best_match = t_block
            
            if best_match:
                fused_block = self._combine_blocks(v_block, best_match, best_similarity)
            else:
                fused_block = {
                    'text': v_block['text'],
                    'confidence': v_block['confidence'] * self.vision_weight,
                    'source': 'vision_only',
                    'bounding_box': v_block.get('bounding_box')
                }
            
            fused_blocks.append(fused_block)
        
        return fused_blocks
    
    def _combine_blocks(self, vision_block: Dict, tesseract_block: Dict, similarity: float) -> Dict:
        """Combine two blocks using W-DST"""
        v_conf = vision_block['confidence'] * self.vision_weight
        t_conf = tesseract_block['confidence'] * self.tesseract_weight
        
        combined_conf = (v_conf + t_conf * similarity) / (1 + similarity)
        
        if v_conf > t_conf:
            selected_text = vision_block['text']
        else:
            selected_text = tesseract_block['text']
        
        return {
            'text': selected_text,
            'confidence': combined_conf,
            'source': 'combined',
            'vision_confidence': vision_block['confidence'],
            'tesseract_confidence': tesseract_block['confidence'],
            'similarity': similarity,
            'bounding_box': vision_block.get('bounding_box')
        }
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple character-based comparison"""
        if not text1 or not text2:
            return 0.0
        
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        if text1 == text2:
            return 1.0
        
        longer = max(len(text1), len(text2))
        if longer == 0:
            return 0.0
        
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _calculate_overall_confidence(self, blocks: List[Dict]) -> float:
        """Calculate overall confidence from fused blocks"""
        if not blocks:
            return 0.0
        
        total_conf = sum(b['confidence'] for b in blocks)
        return total_conf / len(blocks)
