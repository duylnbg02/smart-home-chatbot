import re
from typing import List, Dict

class EntityExtractor:
    def __init__(self):
        self.patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b(?:\d{3}[-.]?\d{3}[-.]?\d{4}|\d{10})\b',
            'date': r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',
            'time': r'\b(?:\d{1,2}:\d{2}(?::\d{2})?(?:\s?(?:AM|PM|am|pm))?)\b',
            'number': r'\b\d+(?:\.\d+)?\b',
            'currency': r'[$€£¥]\s?\d+(?:\.\d{2})?',
            'url': r'https?://\S+',
            'temperature': r'\b\d{1,2}\s*(?:độ|do|°C|°|degree)',
        }
        
        # Note: Smart home entity extraction removed - now using fixed_commands pattern in chatbot.py
        
        self.entity_types = list(self.patterns.keys())
    
    def extract(self, text: str) -> List[Dict[str, any]]:
        entities = []

        for entity_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append({
                    'type': entity_type,
                    'value': match.group(),
                    'normalized': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })

        seen = set()
        unique_entities = []
        for e in entities:
            key = (e['type'], e['normalized'], e['start'])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)
        
        unique_entities.sort(key=lambda x: x['start'])
        return unique_entities
    
    def extract_by_type(self, text: str, entity_type: str) -> List[Dict[str, any]]:
        """Extract entities of a specific type (patterns only)"""
        if entity_type in self.patterns:
            pattern = self.patterns[entity_type]
            entities = []
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append({
                    'type': entity_type,
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })
            return entities
        
        return []
    
    def get_supported_types(self) -> List[str]:
        return self.entity_types
