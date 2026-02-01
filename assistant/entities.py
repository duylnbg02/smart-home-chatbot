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
        
        # Smart Home entity dictionaries
        self.smart_home_entities = {
            'device': {
                'đèn': 'light', 'den': 'light', 'light': 'light', 'bóng đèn': 'light',
                'điều hòa': 'ac', 'dieu hoa': 'ac', 'máy lạnh': 'ac', 'may lanh': 'ac', 'ac': 'ac',
                'quạt': 'fan', 'quat': 'fan', 'fan': 'fan',
            },
            'room': {
                'phòng khách': 'living_room', 'phong khach': 'living_room', 'living room': 'living_room',
                'phòng ngủ': 'bedroom', 'phong ngu': 'bedroom', 'bedroom': 'bedroom',
                'phòng tắm': 'bathroom', 'phong tam': 'bathroom', 'bathroom': 'bathroom',
            },
            'action': {
                'bật': 'on', 'bat': 'on', 'mở': 'on', 'mo': 'on', 'turn on': 'on', 'on': 'on',
                'tắt': 'off', 'tat': 'off', 'đóng': 'off', 'dong': 'off', 'turn off': 'off', 'off': 'off',
                'tăng': 'increase', 'tang': 'increase', 'increase': 'increase',
                'giảm': 'decrease', 'giam': 'decrease', 'decrease': 'decrease',
            },
            'sensor': {
                'nhiệt độ': 'temperature', 'nhiet do': 'temperature', 'temperature': 'temperature',
                'độ ẩm': 'humidity', 'do am': 'humidity', 'humidity': 'humidity', 'ẩm': 'humidity',
                'ánh sáng': 'light_level', 'anh sang': 'light_level', 'sáng': 'light_level',
            }
        }
        
        self.entity_types = list(self.patterns.keys()) + list(self.smart_home_entities.keys())
    
    def extract(self, text: str) -> List[Dict[str, any]]:
        entities = []
        text_lower = text.lower()

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

        for entity_type, entity_dict in self.smart_home_entities.items():
            for keyword, normalized in entity_dict.items():
                # Tìm vị trí của keyword trong text
                start = text_lower.find(keyword)
                if start != -1:
                    entities.append({
                        'type': entity_type,
                        'value': keyword,
                        'normalized': normalized,
                        'start': start,
                        'end': start + len(keyword)
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
    
    def extract_smart_home(self, text: str) -> Dict[str, str]:
        text_lower = text.lower()
        result = {}
        
        for entity_type, entity_dict in self.smart_home_entities.items():
            for keyword, normalized in entity_dict.items():
                if keyword in text_lower:
                    result[entity_type] = normalized
                    break  
        
        return result
    
    def extract_by_type(self, text: str, entity_type: str) -> List[Dict[str, any]]:
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
        
        elif entity_type in self.smart_home_entities:
            text_lower = text.lower()
            entities = []
            for keyword, normalized in self.smart_home_entities[entity_type].items():
                start = text_lower.find(keyword)
                if start != -1:
                    entities.append({
                        'type': entity_type,
                        'value': keyword,
                        'normalized': normalized,
                        'start': start,
                        'end': start + len(keyword)
                    })
            return entities
        
        return []
    
    def get_supported_types(self) -> List[str]:
        return self.entity_types
