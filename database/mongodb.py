import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class MongoDB:
    _client = None

    @classmethod
    def get_db(cls, name="chatbot"):
        if cls._client is None:
            uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
            try:
                cls._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
                cls._client.admin.command('ping')
            except Exception as e:
                print(f"❌ MongoDB Error: {e}")
                return None
        return cls._client[name]
    
def get_db(name="chatbot"):
    return MongoDB.get_db(name)

def get_col(col_name, db_name="chatbot"):
    db = get_db(db_name)
    return db[col_name] if db is not None else None