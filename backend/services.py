"""
Chat history service with MongoDB
"""
from datetime import datetime
from typing import List, Dict, Optional
try:
    from bson.objectid import ObjectId
except ImportError:
    ObjectId = str

class ChatHistoryService:
    """
    Service for managing chat history in MongoDB
    """
    
    def __init__(self, db_connection):
        """
        Initialize chat history service
        db_connection: MongoDB database instance
        """
        self.db = db_connection
        self.collection = self.db['chat_history']
        
        # Create indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """
        Create database indexes for better performance
        """
        self.collection.create_index('user_id')
        self.collection.create_index('session_id')
        self.collection.create_index('created_at')
    
    def save_message(self, user_id: str, session_id: str, 
                    user_message: str, bot_reply: str,
                    intent: Optional[str] = None,
                    entities: Optional[List] = None) -> str:
        """
        Save chat message to database
        Returns: message_id
        """
        message_doc = {
            'user_id': user_id,
            'session_id': session_id,
            'user_message': user_message,
            'bot_reply': bot_reply,
            'intent': intent,
            'entities': entities or [],
            'created_at': datetime.utcnow(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        result = self.collection.insert_one(message_doc)
        return str(result.inserted_id)
    
    def get_conversation(self, user_id: str, session_id: str, 
                        limit: int = 50) -> List[Dict]:
        """
        Get conversation history for a session
        """
        messages = list(self.collection.find(
            {'user_id': user_id, 'session_id': session_id},
            {'_id': 1, 'user_message': 1, 'bot_reply': 1, 'created_at': 1, 'intent': 1}
        ).sort('created_at', 1).limit(limit))
        
        # Convert ObjectId to string
        for msg in messages:
            msg['_id'] = str(msg['_id'])
        
        return messages
    
    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """
        Get all sessions for a user
        """
        sessions = self.collection.aggregate([
            {'$match': {'user_id': user_id}},
            {'$group': {
                '_id': '$session_id',
                'message_count': {'$sum': 1},
                'first_message': {'$min': '$created_at'},
                'last_message': {'$max': '$created_at'}
            }},
            {'$sort': {'last_message': -1}}
        ])
        
        return list(sessions)
    
    def delete_conversation(self, user_id: str, session_id: str) -> int:
        """
        Delete a conversation
        """
        result = self.collection.delete_many({
            'user_id': user_id,
            'session_id': session_id
        })
        
        return result.deleted_count
    
    def get_statistics(self, user_id: str) -> Dict:
        """
        Get user statistics
        """
        stats = self.collection.aggregate([
            {'$match': {'user_id': user_id}},
            {'$group': {
                '_id': None,
                'total_messages': {'$sum': 1},
                'total_sessions': {'$addToSet': '$session_id'},
                'first_message': {'$min': '$created_at'},
                'last_message': {'$max': '$created_at'},
                'intents': {'$addToSet': '$intent'}
            }}
        ])
        
        result = next(stats, None)
        if result:
            result['total_sessions'] = len(result['total_sessions'])
            result.pop('_id', None)
            return result
        
        return {
            'total_messages': 0,
            'total_sessions': 0,
            'intents': []
        }
