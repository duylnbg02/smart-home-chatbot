"""
Entity extraction module
"""
import re
from typing import List, Dict

class EntityExtractor:
    """
    Named Entity Recognition (NER) using patterns
    """
    
    def __init__(self):
        """
        Initialize entity patterns
        """
        self.patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b(?:\d{3}[-.]?\d{3}[-.]?\d{4}|\d{10})\b',
            'date': r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',
            'time': r'\b(?:\d{1,2}:\d{2}(?::\d{2})?(?:\s?(?:AM|PM|am|pm))?)\b',
            'number': r'\b\d+(?:\.\d+)?\b',
            'currency': r'[$€£¥]\s?\d+(?:\.\d{2})?',
            'url': r'https?://\S+',
        }
        
        self.entity_types = list(self.patterns.keys())
    
    def extract(self, text: str) -> List[Dict[str, any]]:
        """
        Extract entities from text
        Returns list of dicts with entity info
        """
        entities = []
        
        for entity_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, text)
            
            for match in matches:
                entities.append({
                    'type': entity_type,
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })
        
        # Sort by position in text
        entities.sort(key=lambda x: x['start'])
        
        return entities
    
    def extract_by_type(self, text: str, entity_type: str) -> List[Dict[str, any]]:
        """
        Extract entities of specific type
        """
        if entity_type not in self.patterns:
            return []
        
        pattern = self.patterns[entity_type]
        entities = []
        
        matches = re.finditer(pattern, text)
        for match in matches:
            entities.append({
                'type': entity_type,
                'value': match.group(),
                'start': match.start(),
                'end': match.end()
            })
        
        return entities
    
    def get_supported_types(self) -> List[str]:
        """
        Get list of supported entity types
        """
        return self.entity_types
