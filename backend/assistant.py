import random
import arrow
import os
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from assistant.pipeline import NLPPipeline
from backend.mqtt_handler import get_mqtt_handler
from pymongo import MongoClient
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# Load API keys
load_dotenv(Path(__file__).parent.parent / ".env")


class ConversationContext:
    
    def __init__(self):
        self.pending_action = None
        self.pending_device = None
        self.pending_location = None
        self.pending_intent = None 
        self.last_question = None
        self.awaiting_confirmation = False
        self.suggested_action = None
        self.last_news_list = []
    
    def clear(self):
        self.pending_action = None
        self.pending_device = None
        self.pending_location = None
        self.pending_intent = None
        self.last_question = None
        self.awaiting_confirmation = False
        self.suggested_action = None
    
    def has_pending(self):
        return (self.pending_device is not None or 
                self.pending_location is not None or
                self.pending_action is not None or
                self.awaiting_confirmation)


class Assistant:
    def __init__(self, mqtt_handler=None):
        print("Khởi tạo Assistant")
        self.nlp = NLPPipeline()
        self.mqtt = mqtt_handler or get_mqtt_handler()
        self.context = ConversationContext()
        self._init_rag()
        from backend.weather_service import get_weather_service
        self.weather_service = get_weather_service()
        
        self.knowledge_base = {
            'xin chào': 'Xin chào! Tôi có thể giúp gì cho bạn!',
            'hello': 'Hello! How can I help you?',
            'tên của bạn': 'Tôi là AI Smart Home Assistant!',
            'bạn là ai': 'Tôi là AI Smart Home Assistant, giúp bạn điều khiển nhà thông minh!',
            'cảm ơn': 'Không có gì! Nếu cần giúp đỡ gì khác thì cứ hỏi tôi!',
            'tạm biệt': 'Tạm biệt! Rất vui được gặp bạn!',
            'bye': 'Goodbye!',
        }
        self.confirm_yes = ['có', 'được', 'ừ', 'đúng', 'bật']
        self.confirm_no = ['không', 'thôi', 'hủy', 'bỏ']
        self.fixed_commands = {
            # ĐÈN
            'bật đèn phòng khách': {'device': 'light', 'location': 'living_room', 'action': True},
            'tắt đèn phòng khách': {'device': 'light', 'location': 'living_room', 'action': False},
            'bật đèn phòng ngủ': {'device': 'light', 'location': 'bedroom', 'action': True},
            'tắt đèn phòng ngủ': {'device': 'light', 'location': 'bedroom', 'action': False},
            'bật đèn phòng tắm': {'device': 'light', 'location': 'bathroom', 'action': True},
            'tắt đèn phòng tắm': {'device': 'light', 'location': 'bathroom', 'action': False},
            
            # ĐIỀU HÒA
            'bật điều hòa phòng ngủ': {'device': 'ac', 'location': 'bedroom', 'action': True},
            'tắt điều hòa phòng ngủ': {'device': 'ac', 'location': 'bedroom', 'action': False},
        }

        # Cached prompt templates (tránh tạo lại mỗi request)
        self._prompt_article_summary = ChatPromptTemplate.from_template(
            "Bạn là trợ lý tin tức thông minh.\n\n"
            "Nội dung bài báo:\n{content}\n\n"
            "Yêu cầu:\n"
            "- KHÔNG bắt đầu bằng lời chào hay giới thiệu bản thân\n"
            "- Bắt đầu ngay bằng tiêu đề bài: \"**{title}**\"\n"
            "- Tóm tắt nội dung chính ngắn gọn, súc tích (2-3 đoạn)\n"
            "- KHÔNG bịa đặt, CHỈ dùng thông tin có trong bài\n\n"
            "Tóm tắt (tiếng Việt):"
        )
        self._prompt_detail = ChatPromptTemplate.from_template(
            "Bạn là trợ lý tin tức thông minh.\n\n"
            "Quy tắc:\n"
            "- KHÔNG bắt đầu bằng lời chào hỏi (\"Chào bạn\", \"Hello\"...)\n"
            "- Trả lời THẲNG VÀO NỘI DUNG — nêu đề tài, sự kiện chính ngay câu đầu tiên\n"
            "- KHÔNG nói \"dựa trên ngữ cảnh\" hay \"theo context\"\n"
            "- CHỈ dùng thông tin trong Context, KHÔNG bịa đặt\n"
            "- Trả lời ĐẦY ĐỦ các điểm chính\n"
            "- Chia thành đoạn nếu dài\n\n"
            "Context:\n{context}\n\n"
            "Câu hỏi: {question}\n\n"
            "Trả lời chi tiết (tiếng Việt):"
        )
        self._prompt_summary = ChatPromptTemplate.from_template(
            "Bạn là trợ lý tin tức thông minh.\n\n"
            "Quy tắc:\n"
            "- KHÔNG bắt đầu bằng lời chào hỏi (\"Chào bạn\", \"Hello\"...)\n"
            "- Trả lời THẲNG VÀO NỘI DUNG — nêu đề tài hoặc sự kiện ngay câu đầu\n"
            "- KHÔNG nói \"dựa trên ngữ cảnh\" hay \"theo context\"\n"
            "- CHỈ dùng thông tin trong Context, KHÔNG bịa đặt\n"
            "- NGẮN GỌN, đủ ý\n\n"
            "Context:\n{context}\n\n"
            "Câu hỏi: {question}\n\n"
            "Trả lời ngắn gọn (tiếng Việt):"
        )
    
    def _get_current_datetime_info(self):
        now = arrow.now('Asia/Ho_Chi_Minh')
        tomorrow = now.shift(days=1)
        yesterday = now.shift(days=-1)

        def weekday_vn(a):
            return a.format('dddd', locale='vi').title()

        return {
            'now': now.datetime,
            'today': now.format('DD/MM/YYYY'),
            'weekday': weekday_vn(now),
            'time': now.format('HH:mm'),
            'tomorrow': tomorrow.format('DD/MM/YYYY'),
            'tomorrow_weekday': weekday_vn(tomorrow),
            'yesterday': yesterday.format('DD/MM/YYYY'),
            'yesterday_weekday': weekday_vn(yesterday),
            'month': now.format('MM/YYYY'),
            'year': now.format('YYYY')
        }
    
    def _handle_datetime_query(self, message: str) -> str:
        message_lower = message.lower()
        if any(word in message_lower for word in ['tin tức', 'bài báo', 'thời sự', 'tin hôm nay', 'mới nhất', 'tóm tắt', 'news']): return None
        dt_info = self._get_current_datetime_info()
        
        if any(word in message_lower for word in ['hôm nay', 'hom nay', 'today']):
            if 'thứ' in message_lower or 'thu' in message_lower:
                return f"Hôm nay là {dt_info['weekday']}, ngày {dt_info['today']}"
            elif 'ngày' in message_lower or 'ngay' in message_lower:
                return f"Hôm nay là ngày {dt_info['today']} ({dt_info['weekday']})"
            elif 'giờ' in message_lower or 'gio' in message_lower or 'mấy giờ' in message_lower:
                return f"Bây giờ là {dt_info['time']}, {dt_info['weekday']} ngày {dt_info['today']}"
            else:
                return f"{dt_info['weekday']}, {dt_info['today']}, {dt_info['time']}"

        if any(word in message_lower for word in ['ngày mai', 'ngay mai', 'tomorrow']):
            return f"Ngày mai là {dt_info['tomorrow_weekday']}, ngày {dt_info['tomorrow']}"
 
        if any(word in message_lower for word in ['hôm qua', 'hom qua', 'yesterday']):
            return f"Hôm qua là {dt_info['yesterday_weekday']}, ngày {dt_info['yesterday']}"
 
        if 'tháng' in message_lower or 'thang' in message_lower:
            return f"Tháng này là tháng {dt_info['month']}"

        if 'năm' in message_lower:
            return f"Năm nay là năm {dt_info['year']}"
        return None

    def _init_rag(self):
        try:
            faiss_index_path = Path(__file__).parent.parent / "assistant" / "data" / "faiss_index"

            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            
            if faiss_index_path.exists() and (faiss_index_path / "index.faiss").exists():
                try:
                    vectorstore = FAISS.load_local(
                        str(faiss_index_path),
                        embeddings,
                        allow_dangerous_deserialization=True
                    )
                    
                    self.rag_retriever = vectorstore.as_retriever(
                        search_type="similarity",
                        search_kwargs={"k": 8}
                    )

                    self.rag_llm = ChatGoogleGenerativeAI(
                        model="gemini-2.5-flash",
                        temperature=0.7,
                        max_output_tokens=2048
                    )
                    
                    metadata_file = faiss_index_path / "metadata.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        total = metadata.get('total_chunks', metadata.get('total_articles', '?'))
                        print(f"RAG sẵn sàng: {total} chunks (built: {metadata.get('build_time', '?')[:10]})")
                    else:
                        print(f"RAG sẵn sàng")
                    
                    _mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
                    self.mongo_client = MongoClient(_mongo_uri)
                    self.mongo_db = self.mongo_client["article-data"]
                    self.articles_collection = self.mongo_db["articles"]
                    
                    return
                    
                except Exception as load_error:
                    print(f"⚠️ Lỗi load FAISS index: {load_error}, rebuild từ MongoDB...")
            
            # Build từ MongoDB (lần đầu hoặc khi index không có)
            print("📚 Build RAG từ MongoDB...")
            
            _mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
            self.mongo_client = MongoClient(_mongo_uri)
            self.mongo_db = self.mongo_client["article-data"]
            self.articles_collection = self.mongo_db["articles"]
            
            chunks = list(self.articles_collection.find().sort('date', -1))
            
            if not chunks:
                print("⚠️ Không có chunks trong database!")
                self.rag_retriever = None
                self.rag_llm = None
                return
            
            documents = []
            for chunk_doc in chunks:
                doc = Document(
                    page_content=chunk_doc.get('chunk', ''),
                    metadata={
                        "title": chunk_doc.get('title', 'Unknown'),
                        "url": chunk_doc.get('url', ''),
                        "date": str(chunk_doc.get('date', '')),
                        "chunk_index": chunk_doc.get('chunk_index', 0),
                        "chunk_id": str(chunk_doc.get('_id'))
                    }
                )
                documents.append(doc)
            
            vectorstore = FAISS.from_documents(documents, embeddings)
            self.rag_retriever = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 8}
            )
            
            self.rag_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.7,
                max_output_tokens=2048
            )
            
            print(f"RAG sẵn sàng: {len(documents)} chunks")
            
            # Auto-save FAISS index
            try:
                faiss_index_path.mkdir(parents=True, exist_ok=True)
                vectorstore.save_local(str(faiss_index_path))
                
                chunk_ids = [chunk['_id'] for chunk in chunks]
                result = self.articles_collection.update_many(
                    {"_id": {"$in": chunk_ids}},
                    {"$set": {"embedded": True, "embedded_at": datetime.now()}}
                )
                
                metadata = {
                    'build_time': datetime.now().isoformat(),
                    'build_mode': 'auto-save',
                    'total_chunks': len(documents),
                    'chunks_marked_embedded': result.modified_count,
                    'embedding_model': "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    'strategy': '1 chunk = 1 vector (granular for precision)'
                }
                with open(faiss_index_path / "metadata.json", 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            except Exception as save_error:
                print(f"⚠️ Không thể lưu FAISS index: {save_error}")
            
        except Exception as e:
            print(f"⚠️ Lỗi khi khởi tạo RAG: {e}")
            self.rag_retriever = None
            self.rag_llm = None
    
    def _is_news_query(self, message: str) -> bool:
        """Kiểm tra có phải câu hỏi về tin tức không"""
        # Dùng cụm từ cụ thể thay vì từ đơn quá ngắn như 'tin', 'ngày'
        # để tránh false positive ("tôi không tin bạn", "mỗi ngày"...)
        news_keywords = [
            'tin tức', 'bài báo', 'thời sự',
            'mới nhất', 'gần đây', 'tin hôm nay',
            'tóm tắt', 'summary', 'news', 'tổng hợp'
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in news_keywords)
    
    def _handle_news_query(self, message: str) -> str:
        """Xử lý câu hỏi về tin tức bằng RAG"""
        if not self.rag_retriever or not self.rag_llm:
            return "Xin lỗi, hệ thống tin tức hiện chưa sẵn sàng"
        
        try:
            # ===== 1. Kiểm tra user hỏi về tin số mấy (từ list vừa show) =====
            number_match = re.search(r'(?:tin|bài)\s*(?:tức|báo)?\s*(\d+)', message.lower())
            if number_match and self.context.last_news_list:
                news_index = int(number_match.group(1)) - 1  
                if 0 <= news_index < len(self.context.last_news_list):
                    article = self.context.last_news_list[news_index]
                    title = article['title']
                    chunks = list(self.articles_collection.find({
                        'title': title
                    }).sort('chunk_index', 1))
                    
                    if not chunks:
                        return f"Không tìm thấy nội dung bài '{title}'"
                    full_content = "\n\n".join([c.get('chunk', '') for c in chunks])
                    try:
                        chain = self._prompt_article_summary | self.rag_llm | StrOutputParser()
                        summary = chain.invoke({
                            "content": full_content[:6000],
                            "title": title
                        })
                        return summary
                    except Exception as llm_error:
                        return f"**{title}**\n\n{full_content[:2048]}"
            is_date_query = any(word in message.lower() for word in [
                'hôm nay', 'hôm qua', 'ngày hôm nay', 'tin tức hôm nay',
                'tin tức ngày', 'bài báo hôm nay', 'tin hôm nay'
            ])
            
            is_latest_query = any(word in message.lower() for word in [
                'mới nhất', 'gần đây', 'vừa rồi', 'đang nóng'
            ]) and not any(word in message.lower() for word in ['như nào', 'thế nào', 'chi tiết', 'nói gì'])
            
            if is_latest_query:
                recent_chunks = list(self.articles_collection.find().sort('date', -1).limit(25))
                articles_by_title = {}
                for chunk in recent_chunks:
                    title = chunk.get('title', 'Unknown')
                    if title not in articles_by_title:
                        articles_by_title[title] = {
                            'title': title,
                            'url': chunk.get('url', ''),
                            'date': chunk.get('date')
                        }
                    if len(articles_by_title) >= 5:
                        break
                
                article_list = list(articles_by_title.values())
                self.context.last_news_list = article_list
                
                latest_date = article_list[0].get('date') if article_list else None
                date_label = latest_date.strftime('%d/%m/%Y') if isinstance(latest_date, datetime) else ''
                
                response = f"**Tin tức mới nhất{' (' + date_label + ')' if date_label else ''}**:\n\n"
                for i, article in enumerate(article_list, 1):
                    response += f"{i}. {article['title']}\n"
                response += f"\n Hỏi 'tin 1', 'tin 2'... để xem chi tiết bài nào!"
                return response
            
            if is_date_query:
                if 'hôm qua' in message.lower():
                    target_date = datetime.now() - timedelta(days=1)
                else:
                    specific_date = None
                    date_pattern = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{4}))?', message)
                    if date_pattern:
                        try:
                            day = int(date_pattern.group(1))
                            month = int(date_pattern.group(2))
                            year = int(date_pattern.group(3)) if date_pattern.group(3) else datetime.now().year
                            specific_date = datetime(year, month, day)
                        except Exception:
                            specific_date = None
                    target_date = specific_date if specific_date else datetime.now()

                date_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                date_end = date_start + timedelta(days=1)

                chunks = list(self.articles_collection.find({
                    'date': {
                        '$gte': date_start,
                        '$lt': date_end
                    }
                }))
                
                if not chunks:
                    recent = list(self.articles_collection.find().sort('date', -1).limit(1))
                    if recent:
                        latest_date = recent[0].get('date')
                        if isinstance(latest_date, datetime):
                            date_str = latest_date.strftime('%d/%m/%Y')
                        else:
                            date_str = str(latest_date)[:10]
                        return f"Không có tin tức {target_date.strftime('%d/%m/%Y')}. Tin mới nhất là ngày {date_str}."
                    else:
                        return "Xin lỗi, không có tin tức trong hệ thống"
                
                articles_by_title = {}
                for chunk in chunks:
                    title = chunk.get('title', 'Unknown')
                    if title not in articles_by_title:
                        articles_by_title[title] = {
                            'title': title,
                            'url': chunk.get('url', ''),
                            'date': chunk.get('date')
                        }
                
                article_list = list(articles_by_title.values())
                display_list = random.sample(article_list, min(5, len(article_list)))
                self.context.last_news_list = display_list
                date_str = target_date.strftime('%d/%m/%Y')
                weekday_vn = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
                day_name = weekday_vn[target_date.weekday()]
                
                response = f"**Tin tức {day_name}, {date_str}**:\n\n"
                
                for i, article in enumerate(display_list, 1):
                    response += f"{i}. {article['title']}\n"
                
                response += f"\n Hỏi 'tin 1', 'tin 2'... để xem chi tiết bài nào!"
                
                return response
            docs = self.rag_retriever.invoke(message)
            
            if not docs:
                return "Xin lỗi, tôi không tìm thấy tin tức phù hợp"
            context = "\n\n".join([doc.page_content for doc in docs])

            is_detailed_question = any(word in message.lower() for word in [
                'như nào', 'thế nào', 'chi tiết', 'cụ thể', 'thông tin', 
                'nội dung', 'diễn biến', 'tình hình', 'giải thích'
            ])

            prompt = self._prompt_detail if is_detailed_question else self._prompt_summary

            rag_chain = (
                {
                    "context": lambda x: context,
                    "question": RunnablePassthrough(),
                }
                | prompt
                | self.rag_llm
                | StrOutputParser()
            )
            try:
                answer = rag_chain.invoke(message)

                if not is_detailed_question:
                    self.context.last_news_list = [
                        {'title': d.metadata.get('title', ''), 'url': d.metadata.get('url', '')}
                        for d in docs[:5]
                    ]
            except Exception as llm_error:
                error_msg = str(llm_error)
                if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                    print(f"Gemini quota exceeded, dùng fallback response với content")
                    
                    is_today_query = any(word in message.lower() for word in ['hôm nay', 'tin hôm nay', 'tin tức hôm nay'])

                    if is_detailed_question or any(word in message.lower() for word in ['tin', 'bài', 'như nào', 'thế nào']):
                        if docs and len(docs) > 0:
                            best_article = docs[0]
                            best_title = best_article.metadata.get('title', 'Tin tức')
                            return f"**{best_title}**\n\n{best_article.page_content[:1500]}\n\n_(Tóm tắt bằng AI tạm thời không khả dụng do giới hạn quota)_"

                    titles = [doc.metadata.get('title', '') for doc in docs[:5] if doc.metadata.get('title')]
                    if titles:
                        self.context.last_news_list = [
                            {'title': d.metadata.get('title', ''), 'url': d.metadata.get('url', '')}
                            for d in docs[:5]
                        ]

                        answer = "Tin tức "
                        if is_today_query:
                            answer += "hôm nay:\n\n"
                        else:
                            answer += "nổi bật:\n\n"
                        for i, title in enumerate(titles, 1):
                            answer += f"{i}. {title}\n"
                        answer += "\n Hỏi 'tin 1 như nào?' hoặc 'bài 2 nói gì?' để xem chi tiết"
                        return answer.strip()
                    else:
                        return "Xin lỗi, không thể tạo tóm tắt lúc này"
                else:
                    raise
            
            return answer
            
        except Exception as e:
            print(f"Lỗi RAG: {e}")
            return "Xin lỗi, có lỗi xảy ra khi tra cứu tin tức"

    def get_response(self, user_message: str) -> str:
        message_lower = user_message.lower().strip()
        datetime_response = self._handle_datetime_query(user_message)
        if datetime_response:
            return datetime_response

        device_control_result = self._handle_device_control(user_message, [])
        if device_control_result:
            return device_control_result

        if self._is_news_query(message_lower):
            return self._handle_news_query(user_message)

        result = self.nlp.process(user_message)
        intent = result['intent']['type']
        confidence = result['intent']['confidence']
        entities = result['entities']

        if intent == 'check_status':
            return self._handle_status_check(user_message, entities)
        
        elif intent == 'query_sensor':
            return self._handle_sensor_query(user_message)
        
        elif intent == 'control_device':
            return """Lệnh không hợp lệ! Vui lòng sử dụng đúng cú pháp """
        elif intent == 'greeting':
            word_count = len(user_message.split())
            if word_count <= 4 or confidence >= 0.5:
                return self._handle_greeting()
            else:
                return self._generate_default_response(user_message)
        
        elif intent == 'farewell':
            return "Tạm biệt! Chúc bạn một ngày tốt lành!"
        
        elif intent == 'gratitude':
            return "Không có gì! Tôi luôn sẵn sàng giúp bạn!"
        
        elif intent == 'set_value':
            return self._handle_set_value(user_message, entities)
        
        else:
            for key, response in self.knowledge_base.items():
                if key in message_lower:
                    return response
            return self._generate_default_response(user_message)

    def _handle_greeting(self) -> str:
        greetings = [
            "Xin chào! Tôi có thể giúp gì cho bạn?",
            "Chào bạn! Bạn muốn tôi giúp gì nào?",
            "Hello! Tôi là Smart Home Assistant!",
        ]
        return random.choice(greetings)

    def _handle_device_control(self, message: str, entities: list) -> str:
        message_lower = message.lower().strip()

        for command_text, command_data in self.fixed_commands.items():
            if command_text in message_lower:
                return self._execute_device_command(
                    command_data['device'],
                    command_data['location'],
                    command_data['action']
                )

        match = re.search(r'(bật|tắt)\s+điều hòa\s+(phòng khách|phòng ngủ|phòng tắm)\s+(\d+)\s*độ', message_lower)
        if match:
            room_vn = match.group(2)
            temp = int(match.group(3))
            room_map = {
                'phòng khách': 'living_room',
                'phòng ngủ': 'bedroom',
                'phòng tắm': 'bathroom'
            }
            location = room_map.get(room_vn, 'living_room')

            if 16 <= temp <= 30:
                if self.mqtt:
                    self.mqtt.send_command('ac', location, True)
                    self.mqtt.send_command('ac_temp', location, temp)
                return f"Đã bật điều hòa {room_vn} ở {temp}°C!"
            else:
                return "Nhiệt độ phải từ 16°C đến 30°C!"

        match = re.search(r'tăng\s+điều hòa\s+(phòng khách|phòng ngủ|phòng tắm)\s+(\d+)\s*độ', message_lower)
        if match:
            room_vn = match.group(1)
            delta = int(match.group(2))
            
            room_map = {'phòng khách': 'living_room', 'phòng ngủ': 'bedroom', 'phòng tắm': 'bathroom'}
            location = room_map.get(room_vn, 'living_room')
            current_temp = 25
            if self.mqtt:
                states = self.mqtt.get_device_states()
                current_temp = states['ac'].get('temperature', 25)
            
            new_temp = min(current_temp + delta, 30)
            
            if self.mqtt:
                self.mqtt.send_command('ac_temp', location, new_temp)
            
            return f"Đã tăng nhiệt độ điều hòa {room_vn} lên {new_temp}°C (+{delta}°C)"

        match = re.search(r'giảm\s+điều hòa\s+(phòng khách|phòng ngủ|phòng tắm)\s+(\d+)\s*độ', message_lower)
        if match:
            room_vn = match.group(1)
            delta = int(match.group(2))
            
            room_map = {'phòng khách': 'living_room', 'phòng ngủ': 'bedroom', 'phòng tắm': 'bathroom'}
            location = room_map.get(room_vn, 'living_room')
            
            current_temp = 25
            if self.mqtt:
                states = self.mqtt.get_device_states()
                current_temp = states['ac'].get('temperature', 25)
            
            new_temp = max(current_temp - delta, 16)
            
            if self.mqtt:
                self.mqtt.send_command('ac_temp', location, new_temp)
            
            return f"Đã giảm nhiệt độ điều hòa {room_vn} xuống {new_temp}°C (-{delta}°C)"
        
        # ==================================================
        # BƯỚC 3: KHÔNG MATCH → TRẢ VỀ None
        # ==================================================
        
        # Không match bất kỳ pattern nào → để các handler khác xử lý
        return None

    def _handle_status_check(self, message: str, entities: list) -> str:
        """Xử lý kiểm tra trạng thái"""
        if not self.mqtt:
            return "❌ Không thể kiểm tra trạng thái - MQTT chưa kết nối!"
        
        # Luôn trả về tất cả trạng thái
        return self._get_all_status()

    def _get_all_status(self) -> str:
        """Lấy trạng thái tất cả thiết bị"""
        if not self.mqtt:
            return "❌ MQTT chưa kết nối!"
        
        states = self.mqtt.get_device_states()
        sensors = self.mqtt.get_sensor_data()
        
        status_lines = ["Trạng thái nhà thông minh:"]
        
        # Lights
        status_lines.append("💡Đèn:")
        for loc, state in states['lights'].items():
            loc_vn = self._get_location_vietnamese(loc)
            status = "Bật" if state else "Tắt"
            status_lines.append(f"  • {loc_vn}: {status}")
        
        # AC
        status_lines.append("❄️ Điều hòa:")
        ac_status = "Bật" if states['ac']['bedroom'] else "Tắt"
        status_lines.append(f"  • Phòng ngủ: {ac_status} ({states['ac']['temperature']}°C)")
        
        # Sensors
        status_lines.append("🌡️ Cảm biến:")
        status_lines.append(f"  • Nhiệt độ: {sensors['temperature']}°C")
        status_lines.append(f"  • Độ ẩm: {sensors['humidity']}%")
        status_lines.append(f"  • Ánh sáng: {sensors['light']} lux")
        
        return "\n".join(status_lines)

    def _get_sensor_data(self) -> dict:
        """Lấy dữ liệu cảm biến: ưu tiên MQTT, fallback sang weather API"""
        if self.mqtt:
            data = self.mqtt.get_sensor_data()
            # Nếu MQTT có dữ liệu thực (không phải 0)
            if data.get('temperature', 0) != 0 or data.get('humidity', 0) != 0:
                return {'source': 'mqtt', **data}

        # Fallback sang weather service
        weather = self.weather_service.get_current() if self.weather_service else None
        if weather:
            return {
                'source': 'weather',
                'temperature': weather['temperature'],
                'humidity': weather['humidity'],
                'light': weather.get('light', 0),
                'city': weather.get('city', ''),
                'condition': weather.get('condition', ''),
            }

        return {'source': 'none', 'temperature': 0, 'humidity': 0, 'light': 0}

    def _handle_sensor_query(self, message: str) -> str:
        """Xử lý truy vấn cảm biến"""
        sensors = self._get_sensor_data()
        message_lower = message.lower()
        source = sensors.get('source', 'none')
        suffix = f" *(dữ liệu thời tiết tại {sensors.get('city', '')})*" if source == 'weather' else ''

        # Kiểm tra độ ẩm TRƯỚC (vì "độ" có thể match với "nhiệt độ")
        if 'độ ẩm' in message_lower or 'ẩm' in message_lower:
            humidity = sensors['humidity']
            if humidity < 40:
                return f"Độ ẩm hiện tại là {humidity}% - Khá khô, nên bật máy tạo ẩm!"
            elif humidity > 70:
                return f"Độ ẩm hiện tại là {humidity}% - Khá ẩm!"
            else:
                return f"Độ ẩm hiện tại là {humidity}% - Mức thoải mái!"

        # Kiểm tra nhiệt độ
        if 'nhiệt độ' in message_lower or 'nóng' in message_lower or 'lạnh' in message_lower or 'bao nhiêu độ' in message_lower:
            temp = sensors['temperature']
            if temp > 30:
                return f"Nhiệt độ hiện tại là {temp}°C - Khá nóng!"
            elif temp < 20:
                return f"Nhiệt độ hiện tại là {temp}°C - Khá lạnh!"
            else:
                return f"Nhiệt độ hiện tại là {temp}°C - Nhiệt độ dễ chịu!"

        # Kiểm tra ánh sáng
        if 'ánh sáng' in message_lower or 'sáng' in message_lower or 'tối' in message_lower:
            light = sensors['light']
            if light < 100:
                return f"Ánh sáng hiện tại là {light} Khá tối!"
            elif light > 500:
                return f"Ánh sáng hiện tại là {light} Rất sáng!{suffix}"
            else:
                return f"Ánh sáng hiện tại là {light} Ánh sáng vừa phải!{suffix}"

        # Trả về tất cả sensor data
        return f"""🌡️ **Dữ liệu cảm biến:**
• Nhiệt độ: {sensors['temperature']}°C
• Độ ẩm: {sensors['humidity']}%
• Ánh sáng: {sensors['light']} lux{suffix}"""

    def _handle_set_value(self, message: str, entities: list) -> str:
        """Xử lý cài đặt giá trị (nhiệt độ điều hòa)"""
        message_lower = message.lower()

        numbers = re.findall(r'\d+', message)
        
        if numbers:
            value = int(numbers[0])
            
            # Cài đặt nhiệt độ điều hòa
            if 'điều hòa' in message_lower:
                if 16 <= value <= 30:
                    if self.mqtt:
                        success = self.mqtt.send_command('ac_temp', 'bedroom', value)
                        if success:
                            return f"Đã cài đặt điều hòa ở {value}°C!"
                        else:
                            return "Không thể cài đặt nhiệt độ!"
                else:
                    return "Nhiệt độ phải từ 16°C đến 30°C!"
        
        return "Bạn muốn cài đặt gì? Ví dụ: 'Đặt điều hòa 25 độ'"

    def _get_location_vietnamese(self, location: str) -> str:
        """Chuyển đổi tên location sang tiếng Việt"""
        mapping = {
            'living_room': 'phòng khách',
            'bedroom': 'phòng ngủ',
            'bathroom': 'phòng tắm',
        }
        return mapping.get(location, location)

    def _execute_device_command(self, device_type: str, location: str, action: bool) -> str:
        status = "bật" if action else "tắt"
        location_vn = self._get_location_vietnamese(location)
        
        # Map device names
        device_map = {
            'light': 'đèn',
            'ac': 'điều hòa'
        }
        device_vn = device_map.get(device_type, device_type)
        
        # Ngữ điệu tự nhiên hơn
        responses = [
            f"Tôi đã {status} {device_vn} {location_vn} cho bạn rồi ạ ",
            f"Đã {status} {device_vn} {location_vn} rồi nhé! ",
            f"Dạ, {device_vn} {location_vn} đã được {status} rồi ạ "
        ]
        
        # Gửi lệnh MQTT nếu có kết nối
        if self.mqtt:
            try:
                self.mqtt.send_command(device_type, location, action)
            except Exception as mqtt_err:
                print(f"⚠️ MQTT send_command thất bại ({device_type}/{location}): {mqtt_err}")
                return f"⚠️ Lệnh đã gửi nhưng thiết bị không phản hồi. Kiểm tra kết nối MQTT!"
        
        return random.choice(responses)

    def _generate_default_response(self, user_message: str) -> str:
        msg = user_message.lower()
        question_signals = [
            'là gì', 'như nào', 'thế nào', 'tại sao', 'vì sao',
            'ở đâu', 'bao nhiêu', 'khi nào', 'có không', 'what', 'how', 'why',
            'tin tức', 'bài báo', 'thông tin', 'giải thích', 'cho biết'
        ]
        is_question = any(s in msg for s in question_signals) or len(user_message.split()) >= 6
        if is_question and self.rag_retriever and self.rag_llm:
            try:
                docs = self.rag_retriever.invoke(user_message)
                if docs:
                    answer = self._handle_news_query(user_message)
                    if "có lỗi xảy ra" not in answer.lower():
                        return answer
            except Exception as e:
                error_msg = str(e)
                if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                    print(f"⚠️ RAG quota exceeded, dùng fallback response")
                else:
                    print(f"⚠️ RAG error in default response: {e}")
        responses = [
            "Tôi chưa hiểu ý bạn. Bạn có thể nói rõ hơn không?",
            "Bạn có muốn xem tin tức ngày hôm nay không? ",
            "Bạn có cần tôi giúp gì không?",
        ]
        return random.choice(responses)

_assistant_instance = None

def get_assistant(mqtt_handler=None):
    global _assistant_instance
    if _assistant_instance is None:
        _assistant_instance = Assistant(mqtt_handler)
    return _assistant_instance
