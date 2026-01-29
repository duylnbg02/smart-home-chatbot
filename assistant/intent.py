"""
Intent detection module
"""
from typing import Dict, Tuple

class IntentDetector:
    """
    Intent detection using keyword matching
    """
    
    def __init__(self):
        """
        Initialize intent patterns
        """
        self.intents = {
            'greeting': {
                'keywords': ['xin chào', 'hello', 'hi', 'chào', 'hey', 'halo'],
                'confidence_threshold': 0.7
            },
            'control_device': {
                'keywords': ['bật', 'tắt', 'bat', 'tat', 'mở', 'mo', 'turn on', 'turn off'],
                'confidence_threshold': 0.6
            },
            'check_status': {
                'keywords': ['trạng thái', 'trang thai', 'kiểm tra', 'kiem tra', 'status', 'đang bật', 'dang bat'],
                'confidence_threshold': 0.6
            },
            'query_sensor': {
                'keywords': ['nhiệt độ', 'nhiet do', 'độ ẩm', 'do am', 'ánh sáng', 'anh sang', 'độ', 'temperature', 'humidity', 'light'],
                'confidence_threshold': 0.6
            },
            'set_value': {
                'keywords': ['đặt', 'dat', 'cài đặt', 'cai dat', 'độ', 'độC', 'độ c', 'độ C'],
                'confidence_threshold': 0.6
            },
            'farewell': {
                'keywords': ['tạm biệt', 'bye', 'goodbye', 'see you', 'bye bye'],
                'confidence_threshold': 0.7
            },
            'gratitude': {
                'keywords': ['cảm ơn', 'thanks', 'thank you', 'appreciate', 'merci'],
                'confidence_threshold': 0.7
            },
            'question': {
                'keywords': ['là ai', 'tên là gì', 'làm gì', 'như thế nào', 'tại sao', 'what', 'why', 'how'],
                'confidence_threshold': 0.6
            },
            'help': {
                'keywords': ['giúp', 'help me', 'hỗ trợ', 'support', 'assist'],
                'confidence_threshold': 0.7
            },
            'unknown': {
                'keywords': [],
                'confidence_threshold': 0.0
            }
        }
    
    def detect(self, text: str) -> Tuple[str, float]:
        """
        Detect intent from text
        Returns: (intent, confidence)
        """
        text_lower = text.lower()
        
        # Calculate intent scores
        intent_scores = {}
        for intent, data in self.intents.items():
            if intent == 'unknown':
                continue
            
            keywords = data['keywords']
            matched = sum(1 for keyword in keywords if keyword in text_lower)
            
            if matched > 0:
                confidence = min(1.0, matched / len(keywords)) if keywords else 0.0
                intent_scores[intent] = confidence
        
        # Get best intent
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            confidence = intent_scores[best_intent]
            return best_intent, confidence
        
        return 'unknown', 0.0
    
    def get_all_intents(self) -> Dict[str, list]:
        """
        Get all available intents and their keywords
        """
        return {
            intent: data['keywords'] 
            for intent, data in self.intents.items() 
            if intent != 'unknown'
        }
