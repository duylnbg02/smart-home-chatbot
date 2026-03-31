from datetime import datetime

class ChatHistoryService:
    def __init__(self, db):
        self.col = db['chat_history']
        self.col.create_index([('user_id', 1), ('session_id', 1), ('created_at', 1)])

    def save_message(self, uid, sid, msg, reply, intent=None, entities=None):
        doc = {
            'user_id': uid, 'session_id': sid, 'user_message': msg,
            'bot_reply': reply, 'intent': intent, 'entities': entities or [],
            'created_at': datetime.utcnow()
        }
        return str(self.col.insert_one(doc).inserted_id)

    def get_conversation(self, uid, sid, limit=50):
        messages = list(self.col.find(
            {'user_id': uid, 'session_id': sid},
            {'_id': 1, 'user_message': 1, 'bot_reply': 1, 'created_at': 1}
        ).sort('created_at', 1).limit(limit))
        
        for m in messages: m['_id'] = str(m['_id'])
        return messages

    def get_user_sessions(self, uid):
        return list(self.col.aggregate([
            {'$match': {'user_id': uid}},
            {'$group': {
                '_id': '$session_id',
                'count': {'$sum': 1},
                'last': {'$max': '$created_at'}
            }},
            {'$sort': {'last': -1}}
        ]))

    def delete_conversation(self, uid, sid):
        return self.col.delete_many({'user_id': uid, 'session_id': sid}).deleted_count

    def get_statistics(self, uid):
        stats = list(self.col.aggregate([
            {'$match': {'user_id': uid}},
            {'$group': {
                '_id': None,
                'total_msg': {'$sum': 1},
                'sessions': {'$addToSet': '$session_id'},
                'intents': {'$addToSet': '$intent'}
            }}
        ]))
        if not stats: return {'total_msg': 0, 'total_sess': 0, 'intents': []}
        res = stats[0]
        return {
            'total_msg': res['total_msg'],
            'total_sess': len(res['sessions']),
            'intents': [i for i in res['intents'] if i]
        }