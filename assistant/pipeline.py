"""
NLP Pipeline - Orchestrates all NLP components
"""
from typing import Dict, List, Any
from assistant.preprocess import TextPreprocessor
from assistant.intent import IntentDetector
from assistant.entities import EntityExtractor

class NLPPipeline:
    """
    Complete NLP pipeline orchestrator
    """
    
    def __init__(self):
        """
        Initialize all NLP components
        """
        self.preprocessor = TextPreprocessor()
        self.intent_detector = IntentDetector()
        self.entity_extractor = EntityExtractor()
    
    def process(self, text: str) -> Dict[str, Any]:
        """
        Process text through complete NLP pipeline
        """
        # Step 1: Preprocess text
        tokens = self.preprocessor.preprocess(text)
        
        # Step 2: Detect intent
        intent, intent_confidence = self.intent_detector.detect(text)
        
        # Step 3: Extract entities
        entities = self.entity_extractor.extract(text)
        
        # Return structured result
        return {
            'original_text': text,
            'cleaned_text': ' '.join(tokens),
            'tokens': tokens,
            'intent': {
                'type': intent,
                'confidence': round(intent_confidence, 2)
            },
            'entities': entities,
            'entity_count': len(entities),
            'token_count': len(tokens)
        }
    
    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Detailed analysis of text (alias for process)
        """
        return self.process(text)
    
    def get_intent_only(self, text: str) -> Dict[str, Any]:
        """
        Get intent only (faster processing)
        """
        intent, confidence = self.intent_detector.detect(text)
        return {
            'intent': intent,
            'confidence': round(confidence, 2)
        }
    
    def get_entities_only(self, text: str) -> List[Dict[str, Any]]:
        """
        Get entities only
        """
        return self.entity_extractor.extract(text)
