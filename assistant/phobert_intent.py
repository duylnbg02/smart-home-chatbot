"""
PhoBERT-based Intent Detection using Sentence Similarity
Sử dụng PhoBERT embeddings để so sánh ngữ nghĩa câu hỏi với các intent mẫu
"""
import torch
from transformers import AutoModel, AutoTokenizer
from typing import Dict, Tuple, List
import numpy as np


class PhoBERTIntentDetector:
    """
    Intent detection using PhoBERT sentence embeddings
    """
    
    def __init__(self, model_name: str = "vinai/phobert-base"):
        """
        Initialize PhoBERT model and intent examples
        """
        print("🔄 Đang tải PhoBERT model...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()  # Set to evaluation mode
        
        # Định nghĩa các intent với câu mẫu tiếng Việt
        self.intent_examples = {
            'control_device': [
                'bật đèn phòng khách',
                'tắt đèn phòng ngủ',
                'mở quạt',
                'đóng cửa',
                'bật điều hòa',
                'tắt tivi',
                'turn on the light',
                'turn off fan',
                'bật đèn',
                'tắt quạt',
                'mở đèn',
                'đóng đèn',
            ],
            'check_status': [
                'kiểm tra đèn phòng khách',
                'trạng thái điều hòa',
                'đèn có đang bật không',
                'quạt đang tắt hay bật',
                'xem trạng thái thiết bị',
                'check device status',
            ],
            'query_sensor': [
                'nhiệt độ bao nhiêu',
                'độ ẩm là bao nhiêu',
                'nhiệt độ phòng khách',
                'trời sáng hay tối',
                'ánh sáng như thế nào',
                'thời tiết thế nào',
                'môi trường trong nhà',
                'nóng không',
                'lạnh không',
                'temperature',
                'humidity',
                'nhiet do',
                'do am',
            ],
            'set_value': [
                'đặt nhiệt độ 25 độ',
                'chỉnh điều hòa 26 độ',
                'tăng độ sáng',
                'giảm nhiệt độ',
                'set temperature to 25',
            ],
            'greeting': [
                'xin chào',
                'chào bạn',
                'hello',
                'hi there',
                'chào buổi sáng',
                'chào buổi tối',
            ],
            'farewell': [
                'tạm biệt',
                'bye bye',
                'goodbye',
                'hẹn gặp lại',
                'chào nhé',
            ],
            'gratitude': [
                'cảm ơn',
                'cảm ơn bạn',
                'thanks',
                'thank you',
                'cám ơn nhiều',
            ],
            'help': [
                'giúp tôi',
                'hướng dẫn sử dụng',
                'bạn có thể làm gì',
                'help me',
                'tôi cần trợ giúp',
                'làm sao để',
            ],
            'question': [
                'bạn là ai',
                'tên bạn là gì',
                'bạn có thể làm gì',
                'what can you do',
                'who are you',
            ],
        }
        
        # Pre-compute embeddings cho tất cả intent examples
        print("🔄 Đang tính toán embeddings cho intent examples...")
        self.intent_embeddings = {}
        for intent, examples in self.intent_examples.items():
            embeddings = [self._get_embedding(ex) for ex in examples]
            self.intent_embeddings[intent] = torch.stack(embeddings)
        
        print("✅ PhoBERT Intent Detector đã sẵn sàng!")
    
    def _get_embedding(self, text: str) -> torch.Tensor:
        """
        Get sentence embedding using PhoBERT (mean pooling)
        """
        with torch.no_grad():
            # Tokenize
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=128
            )
            
            # Get model output
            outputs = self.model(**inputs)
            
            # Mean pooling - lấy trung bình của tất cả token embeddings
            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state
            
            # Mask padding tokens
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            
            # Return normalized embedding
            embedding = sum_embeddings / sum_mask
            return embedding.squeeze()
    
    def _cosine_similarity(self, a: torch.Tensor, b: torch.Tensor) -> float:
        """
        Calculate cosine similarity between two vectors
        """
        return torch.nn.functional.cosine_similarity(
            a.unsqueeze(0), 
            b.unsqueeze(0)
        ).item()
    
    def detect(self, text: str) -> Tuple[str, float]:
        """
        Detect intent from text using PhoBERT similarity
        Returns: (intent, confidence)
        """
        # Get embedding for input text
        input_embedding = self._get_embedding(text)
        
        # Calculate similarity with each intent
        intent_scores = {}
        for intent, embeddings in self.intent_embeddings.items():
            # Calculate similarity with all examples of this intent
            similarities = []
            for emb in embeddings:
                sim = self._cosine_similarity(input_embedding, emb)
                similarities.append(sim)
            
            # Take max similarity as the score for this intent
            max_sim = max(similarities)
            intent_scores[intent] = max_sim
        
        # Get best intent
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = intent_scores[best_intent]
        
        # If confidence is too low, return unknown
        if confidence < 0.5:
            return 'unknown', confidence
        
        return best_intent, confidence
    
    def detect_all(self, text: str) -> List[Dict]:
        """
        Get all intent scores (for debugging)
        """
        input_embedding = self._get_embedding(text)
        
        results = []
        for intent, embeddings in self.intent_embeddings.items():
            similarities = []
            for emb in embeddings:
                sim = self._cosine_similarity(input_embedding, emb)
                similarities.append(sim)
            
            max_sim = max(similarities)
            results.append({
                'intent': intent,
                'confidence': round(max_sim, 3),
                'max_similarity': round(max_sim, 3)
            })
        
        # Sort by confidence
        results.sort(key=lambda x: -x['confidence'])
        return results
    
    def add_example(self, intent: str, example: str):
        """
        Add new example to an intent (for online learning)
        """
        if intent not in self.intent_examples:
            self.intent_examples[intent] = []
            self.intent_embeddings[intent] = torch.empty(0)
        
        self.intent_examples[intent].append(example)
        new_embedding = self._get_embedding(example)
        
        if len(self.intent_embeddings[intent]) == 0:
            self.intent_embeddings[intent] = new_embedding.unsqueeze(0)
        else:
            self.intent_embeddings[intent] = torch.cat([
                self.intent_embeddings[intent],
                new_embedding.unsqueeze(0)
            ])
    
    def get_all_intents(self) -> Dict[str, List[str]]:
        """
        Get all available intents and their examples
        """
        return self.intent_examples.copy()


# Singleton instance
_phobert_detector = None

def get_phobert_detector() -> PhoBERTIntentDetector:
    """
    Get singleton PhoBERT detector instance
    """
    global _phobert_detector
    if _phobert_detector is None:
        _phobert_detector = PhoBERTIntentDetector()
    return _phobert_detector
