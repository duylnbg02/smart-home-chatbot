from typing import Dict, Tuple

class IntentDetector:
    def __init__(self):
        self.intents = {
            'greeting': {
                'keywords': ['xin chào', 'hello', 'hi', 'chào', 'hey', 'halo']
            },
            'control_device': {
                'keywords': ['bật', 'tắt', 'bat', 'tat', 'mở', 'mo', 'turn on', 'turn off']
            },
            'check_status': {
                'keywords': ['trạng thái', 'trang thai', 'kiểm tra', 'kiem tra', 'status', 'đang bật', 'dang bat']
            },
            'query_sensor': {
                'keywords': ['nhiệt độ', 'nhiet do', 'độ ẩm', 'do am', 'ánh sáng', 'anh sang', 'độ', 'temperature', 'humidity', 'light']
            },
            'set_value': {
                'keywords': ['đặt', 'dat', 'cài đặt', 'cai dat', 'độ', 'độC', 'độ c', 'độ C']
            },
            'farewell': {
                'keywords': ['tạm biệt', 'bye', 'goodbye', 'see you', 'bye bye']
            },
            'gratitude': {
                'keywords': ['cảm ơn', 'thanks', 'thank you', 'appreciate', 'merci']
            },
            'question': {
                'keywords': ['là ai', 'tên là gì', 'làm gì', 'như thế nào', 'tại sao', 'what', 'why', 'how']
            },
            'help': {
                'keywords': ['giúp', 'help', 'hỗ trợ', 'support', 'assist']
            },
            'unknown': {
                'keywords': [],
                'confidence_threshold': 0.0
            }
        }
    
    def detect(self, text: str) -> Tuple[str, float]:
        text_lower = text.lower()
        
        intent_scores = {}
        for intent, data in self.intents.items():
            if intent == 'unknown':
                continue
            
            keywords = data['keywords']
            matched = sum(1 for keyword in keywords if keyword in text_lower)
            
            if matched > 0:
                confidence = min(1.0, matched / len(keywords)) if keywords else 0.0
                intent_scores[intent] = confidence

        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            confidence = intent_scores[best_intent]
            return best_intent, confidence
        
        return 'unknown', 0.0
    
    def get_all_intents(self) -> Dict[str, list]:

        return {
            intent: data['keywords'] 
            for intent, data in self.intents.items() 
            if intent != 'unknown'
        }
