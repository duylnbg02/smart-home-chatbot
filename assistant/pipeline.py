from typing import Dict, List, Any
from assistant.preprocess import TextPreprocessor
from assistant.intent import IntentDetector
from assistant.entities import EntityExtractor

class NLPPipeline:
    def __init__(self):
        self.preprocessor = TextPreprocessor()
        self.intent_detector = IntentDetector()
        self.entity_extractor = EntityExtractor()
    
    def process(self, text: str) -> Dict[str, Any]:
        tokens = self.preprocessor.preprocess(text)
        intent, intent_confidence = self.intent_detector.detect(text)
        entities = self.entity_extractor.extract(text)
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
        return self.process(text)
    
    def get_intent_only(self, text: str) -> Dict[str, Any]:
        intent, confidence = self.intent_detector.detect(text)
        return {
            'intent': intent,
            'confidence': round(confidence, 2)
        }
    
    def get_entities_only(self, text: str) -> List[Dict[str, Any]]:
        return self.entity_extractor.extract(text)
