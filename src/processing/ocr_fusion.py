"""Weighted probabilistic fusion algorithm for combining OCR results"""

import logging
from typing import Dict, List, Tuple
import numpy as np

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class OCRFusion:
    """Weighted probabilistic fusion for combining OCR engine results"""
    
    def __init__(self):
        self.config = get_config()
        self.vision_weight = self.config.get('ocr.fusion.google_vision_weight', 0.7)
        self.tesseract_weight = self.config.get('ocr.fusion.tesseract_weight', 0.3)
        self.min_confidence = self.config.get('ocr.fusion.min_confidence_threshold', 0.5)
        logger.info(f"OCR Fusion initialized: Vision={self.vision_weight}, Tesseract={self.tesseract_weight}")
    
    def fuse_results(self, vision_result: Dict, tesseract_result: Dict) -> Dict:
        """Fuse results from Google Vision and Tesseract using weighted probabilistic fusion"""
        try:
            fused = {
                'full_text': '',
                'blocks': [],
                'confidence': 0.0,
                'source': 'fused',
                'vision_confidence': vision_result.get('confidence', 0),
                'tesseract_confidence': tesseract_result.get('confidence', 0)
            }
            
            fused_blocks = self._fuse_blocks_dempster_shafer(
                vision_result.get('blocks', []),
                tesseract_result.get('blocks', [])
            )
            
            fused['blocks'] = fused_blocks
            fused['full_text'] = ' '.join([b['text'] for b in fused_blocks])
            fused['confidence'] = self._calculate_overall_confidence(fused_blocks)
            fused['primary_engine'] = 'weighted_dempster_shafer'
            
            logger.info(f"Weighted fusion completed: confidence={fused['confidence']:.2f}")
            return fused
            
        except Exception as e:
            logger.error(f"Fusion failed: {e}")
            vision_conf = vision_result.get('confidence', 0)
            tesseract_conf = tesseract_result.get('confidence', 0)
            return vision_result if vision_conf > tesseract_conf else tesseract_result
    
    def _fuse_blocks_dempster_shafer(self, vision_blocks: List[Dict], tesseract_blocks: List[Dict]) -> List[Dict]:
        """Fuse text blocks using weighted probabilistic fusion"""
        fused_blocks = []
        used_tesseract = set()
        
        for v_block in vision_blocks:
            best_match = None
            best_similarity = 0
            best_idx = -1
            
            for idx, t_block in enumerate(tesseract_blocks):
                if idx in used_tesseract:
                    continue
                similarity = self._calculate_similarity(v_block['text'], t_block['text'])
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = t_block
                    best_idx = idx
            
            if best_match and best_similarity > 0.3:
                fused_block = self._dempster_shafer_combine(v_block, best_match, best_similarity)
                used_tesseract.add(best_idx)
            else:
                m_vision = v_block['confidence'] * self.vision_weight
                m_uncertainty = 1 - m_vision
                fused_block = {
                    'text': v_block['text'],
                    'confidence': m_vision / (m_vision + m_uncertainty * 0.5),
                    'source': 'vision_only',
                    'bounding_box': v_block.get('bounding_box')
                }
            
            fused_blocks.append(fused_block)
        
        for idx, t_block in enumerate(tesseract_blocks):
            if idx not in used_tesseract:
                m_tesseract = t_block['confidence'] * self.tesseract_weight
                m_uncertainty = 1 - m_tesseract
                fused_blocks.append({
                    'text': t_block['text'],
                    'confidence': m_tesseract / (m_tesseract + m_uncertainty * 0.5),
                    'source': 'tesseract_only',
                    'bounding_box': t_block.get('bounding_box')
                })
        
        return fused_blocks
    
    def _dempster_shafer_combine(self, vision_block: Dict, tesseract_block: Dict, similarity: float) -> Dict:
        """Combine two blocks using weighted probabilistic fusion with conflict handling"""
        c1 = vision_block['confidence']
        c2 = tesseract_block['confidence']
        w1 = self.vision_weight
        w2 = self.tesseract_weight
        
        if similarity >= 0.8:
            combined_conf = min(1.0, (c1 * w1 + c2 * w2) * (1 + similarity * 0.2))
        elif similarity >= 0.5:
            combined_conf = (c1 * w1 + c2 * w2) / (w1 + w2)
        else:
            conflict_penalty = (1 - similarity) * min(c1 * w1, c2 * w2)
            combined_conf = max(c1 * w1, c2 * w2) * (1 - conflict_penalty * 0.5)
        
        combined_conf = min(max(combined_conf, 0.0), 1.0)
        
        if c1 * w1 > c2 * w2:
            selected_text = vision_block['text']
        else:
            selected_text = tesseract_block['text']
        
        return {
            'text': selected_text,
            'confidence': combined_conf,
            'source': 'weighted_fusion_combined',
            'vision_confidence': c1,
            'tesseract_confidence': c2,
            'similarity': similarity,
            'weighted_vision': c1 * w1,
            'weighted_tesseract': c2 * w2,
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
