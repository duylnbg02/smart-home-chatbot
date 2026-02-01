import os
import json
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient, errors


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_json(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def connect_mongo(uri: str):
    client = MongoClient(uri)
    # quick ping to verify connection
    client.admin.command('ping')
    return client


def ensure_indexes(coll):
    # unique on hash to prevent duplicates
    coll.create_index('hash', unique=True)
    coll.create_index('url')
    coll.create_index('crawled_at')
    coll.create_index('published_at')


def ingest_file_to_mongo(input_file: str, mongo_uri: str, db_name: str = 'data', collection_name: str = 'articles', upsert: bool = False):
    data = load_json(input_file)

    # Normalize data shapes: accept list of items or a single item dict
    if isinstance(data, dict):
        # If top-level dict contains a list under common keys, use it
        for key in ('articles', 'data', 'final_data', 'items'):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # wrap single dict into list
            data = [data]

    if not isinstance(data, list):
        raise ValueError(f"Unexpected JSON root type: {type(data)}. Expected list or dict.")

    total = len(data)
    print(f"Ingesting {total} items from {input_file}")

    client = connect_mongo(mongo_uri)
    db = client[db_name]
    coll = db[collection_name]
    ensure_indexes(coll)

    inserted = 0
    skipped = 0
    updated = 0
    processed = 0

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            print(f"Skipping item {idx}: expected dict but got {type(item)} - preview: {repr(item)[:200]}")
            continue

        url = item.get('url')
        title = item.get('title', '')
        chunks = item.get('chunks', [])
        # try to get published date from item (e.g., 'date' or 'published_at')
        published_str = item.get('date') or item.get('published_at') or item.get('pub_date')
        def parse_date(s):
            if not s:
                return None
            try:
                # ISO formats
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                try:
                    # common date only format YYYY-MM-DD
                    dt = datetime.strptime(s, '%Y-%m-%d')
                    return dt.replace(tzinfo=timezone.utc)
                except Exception:
                    return None

        published_at = parse_date(published_str)

        for i, chunk in enumerate(chunks):
            payload = {
                'url': url,
                'title': title,
                'chunk_index': i,
                'chunk': chunk,
                'crawled_at': datetime.now(timezone.utc),
                'published_at': published_at,
            }
            payload['hash'] = sha256((url or '') + title + chunk)

            processed += 1

            try:
                if upsert:
                    result = coll.update_one({'hash': payload['hash']}, {'$set': payload}, upsert=True)
                    if getattr(result, 'upserted_id', None) is not None:
                        inserted += 1
                    else:
                        updated += 1
                else:
                    coll.insert_one(payload)
                    inserted += 1
            except errors.DuplicateKeyError:
                skipped += 1
            except Exception as e:
                print(f"Error inserting/updating document: {e}")

    print(f"Ingest completed. Processed: {processed}, Inserted: {inserted}, Updated: {updated}, Skipped (dup): {skipped}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Ingest crawled JSON into MongoDB')
    parser.add_argument('--input', '-i', default=os.path.join(os.path.dirname(__file__), 'dulieu.json'), help='Input JSON file')
    parser.add_argument('--mongo-uri', default=None, help='MongoDB URI (overrides .env)')
    parser.add_argument('--db', default='article-data', help='MongoDB database name')
    parser.add_argument('--collection', default='articles', help='MongoDB collection name')
    parser.add_argument('--upsert', action='store_true', help='Upsert documents (update existing, insert new)')

    args = parser.parse_args()

    load_dotenv()
    mongo_uri = args.mongo_uri or os.getenv('MONGODB_URI') or 'mongodb://localhost:27017'

    try:
        ingest_file_to_mongo(args.input, mongo_uri, args.db, args.collection, upsert=args.upsert)
    except Exception as e:
        print(f"Failed to ingest to MongoDB: {e}")


if __name__ == '__main__':
    main()
