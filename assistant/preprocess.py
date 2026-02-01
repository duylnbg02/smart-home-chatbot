import re
import string
from typing import List

class TextPreprocessor:
    @staticmethod
    def clean_text(text: str) -> str:
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs
        text = re.sub(r'http\S+|www\S+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove special characters but keep spaces and basic punctuation
        text = re.sub(r'[^a-z0-9\s\.\,\!\?]', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        return text.split()
    
    @staticmethod
    def remove_stopwords(tokens: List[str], stopwords: List[str] = None) -> List[str]:
        if stopwords is None:
            stopwords = [
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                'could', 'should', 'may', 'might', 'can', 'must', 'shall', 'tôi', 'là',
                'này', 'cái', 'nào', 'được', 'có', 'không', 'và', 'hay', 'mà', 'khi'
            ]
        
        return [token for token in tokens if token.lower() not in stopwords]
    
    @staticmethod
    def preprocess(text: str) -> List[str]:
        cleaned = TextPreprocessor.clean_text(text)
        tokens = TextPreprocessor.tokenize(cleaned)
        tokens = TextPreprocessor.remove_stopwords(tokens)
        return tokens
