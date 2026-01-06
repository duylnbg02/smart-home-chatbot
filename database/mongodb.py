"""
MongoDB connection module
"""
import os
from pymongo import MongoClient
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MongoDBConnection:
    _instance: Optional[MongoClient] = None
    
    def __init__(self, uri: str = None):
        """
        Initialize MongoDB connection
        uri: MongoDB connection string (default from env or local)
        """
        if MongoDBConnection._instance is None:
            if uri is None:
                # Try to get from environment, or use local
                uri = os.getenv(
                    'MONGODB_URI',
                    os.getenv('MONGO_URL', 'mongodb://localhost:27017')
                )
            
            try:
                MongoDBConnection._instance = MongoClient(uri, serverSelectionTimeoutMS=5000)
                # Test connection
                MongoDBConnection._instance.admin.command('ping')
                print(f"✅ Connected to MongoDB: {uri}")
            except Exception as e:
                print(f"❌ MongoDB connection failed: {e}")
                MongoDBConnection._instance = None
    
    @staticmethod
    def get_client() -> MongoClient:
        """
        Get MongoDB client instance
        """
        if MongoDBConnection._instance is None:
            MongoDBConnection()
        return MongoDBConnection._instance
    
    @staticmethod
    def get_database(db_name: str):
        """
        Get database instance
        """
        client = MongoDBConnection.get_client()
        if client is None:
            raise Exception("MongoDB is not connected")
        return client[db_name]
    
    @staticmethod
    def close():
        """
        Close MongoDB connection
        """
        if MongoDBConnection._instance:
            MongoDBConnection._instance.close()
            MongoDBConnection._instance = None

# Convenience functions
def get_db(db_name: str = "chatbot"):
    """
    Get database connection
    """
    return MongoDBConnection.get_database(db_name)

def get_collection(collection_name: str, db_name: str = "chatbot"):
    """
    Get collection from database
    """
    db = get_db(db_name)
    return db[collection_name]
