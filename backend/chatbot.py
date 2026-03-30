import random
import os
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
load_dotenv(r"D:\AI\.env")


class ConversationContext:
    
    def __init__(self):
        self.pending_action = None      # Action đang chờ (on/off)
        self.pending_device = None      # Device đang chờ (light/ac)
        self.pending_location = None    # Location đang chờ
        self.pending_intent = None      # Intent đang chờ xác nhận
        self.last_question = None       # Câu hỏi cuối cùng bot hỏi
        self.awaiting_confirmation = False  # Đang chờ xác nhận có/không
        self.suggested_action = None    # Hành động gợi ý (bật đèn khi tối)
        self.last_news_list = []        # Lưu list tin tức vừa show (để trả lời "tin 1", "tin 2"...)
    
    def clear(self):
        """Xóa context sau khi hoàn thành"""
        self.pending_action = None
        self.pending_device = None
        self.pending_location = None
        self.pending_intent = None
        self.last_question = None
        self.awaiting_confirmation = False
        self.suggested_action = None
        # Giữ last_news_list để user có thể hỏi tiếp
    
    def has_pending(self):
        """Kiểm tra có context đang chờ không"""
        return (self.pending_device is not None or 
                self.pending_location is not None or
                self.pending_action is not None or
                self.awaiting_confirmation)


class Chatbot:
    def __init__(self, mqtt_handler=None):
        print("🤖 Đang khởi tạo Chatbot...")
        self.nlp = NLPPipeline()
        self.mqtt = mqtt_handler or get_mqtt_handler()
        self.context = ConversationContext()
        
        # Khởi tạo RAG system
        print("📚 Đang tải RAG system...")
        self._init_rag()
        
        print("✅ Chatbot đã sẵn sàng!")
        
        # Knowledge base cho các câu hỏi thông thường
        self.knowledge_base = {
            'xin chào': 'Xin chào! 👋 Tôi có thể giúp bạn điều khiển nhà thông minh!',
            'hello': 'Hello! 👋 How can I help you?',
            'tên của bạn': 'Tôi là AI Smart Home Assistant!',
            'bạn là ai': 'Tôi là AI Smart Home Assistant, giúp bạn điều khiển nhà thông minh!',
            'cảm ơn': 'Không có gì! 😊 Nếu cần giúp đỡ gì khác thì cứ hỏi tôi!',
            'tạm biệt': 'Tạm biệt! 👋 Rất vui được gặp bạn!',
            'bye': 'Goodbye! 👋',
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
            'bật đèn nhà tắm': {'device': 'light', 'location': 'bathroom', 'action': True},
            'tắt đèn nhà tắm': {'device': 'light', 'location': 'bathroom', 'action': False},
            
            # ĐIỀU HÒA
            'bật điều hòa phòng khách': {'device': 'ac', 'location': 'living_room', 'action': True},
            'tắt điều hòa phòng khách': {'device': 'ac', 'location': 'living_room', 'action': False},
            'bật điều hòa phòng ngủ': {'device': 'ac', 'location': 'bedroom', 'action': True},
            'tắt điều hòa phòng ngủ': {'device': 'ac', 'location': 'bedroom', 'action': False},
        }
    
    def _get_current_datetime_info(self):
        """Lấy thông tin ngày giờ hiện tại chi tiết"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        weekday_vn = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
        
        tomorrow = now + timedelta(days=1)
        yesterday = now - timedelta(days=1)
        
        return {
            'now': now,
            'today': now.strftime('%d/%m/%Y'),
            'weekday': weekday_vn[now.weekday()],
            'time': now.strftime('%H:%M'),
            'tomorrow': tomorrow.strftime('%d/%m/%Y'),
            'tomorrow_weekday': weekday_vn[tomorrow.weekday()],
            'yesterday': yesterday.strftime('%d/%m/%Y'),
            'yesterday_weekday': weekday_vn[yesterday.weekday()],
            'month': now.strftime('%m/%Y'),
            'year': now.strftime('%Y')
        }
    
    def _handle_datetime_query(self, message: str) -> str:
        """Xử lý câu hỏi về ngày tháng"""
        message_lower = message.lower()
        
        # ⚠️ KHÔNG trả lời nếu câu hỏi về TIN TỨC (tránh xung đột)
        # Dùng cùng danh sách cụm từ với _is_news_query để đồng nhất
        if any(word in message_lower for word in ['tin tức', 'bài báo', 'thời sự', 'tin hôm nay', 'mới nhất', 'tóm tắt', 'news']):
            return None
        
        dt_info = self._get_current_datetime_info()
        
        # Hôm nay
        if any(word in message_lower for word in ['hôm nay', 'hom nay', 'today']):
            if 'thứ' in message_lower or 'thu' in message_lower:
                return f"📅 Hôm nay là {dt_info['weekday']}, ngày {dt_info['today']}"
            elif 'ngày' in message_lower or 'ngay' in message_lower:
                return f"📅 Hôm nay là ngày {dt_info['today']} ({dt_info['weekday']})"
            elif 'giờ' in message_lower or 'gio' in message_lower or 'mấy giờ' in message_lower:
                return f"🕐 Bây giờ là {dt_info['time']}, {dt_info['weekday']} ngày {dt_info['today']}"
            else:
                return f"📅 {dt_info['weekday']}, {dt_info['today']}, {dt_info['time']}"
        
        # Ngày mai
        if any(word in message_lower for word in ['ngày mai', 'ngay mai', 'mai', 'tomorrow']):
            return f"📅 Ngày mai là {dt_info['tomorrow_weekday']}, ngày {dt_info['tomorrow']}"
        
        # Hôm qua
        if any(word in message_lower for word in ['hôm qua', 'hom qua', 'qua', 'yesterday']):
            return f"📅 Hôm qua là {dt_info['yesterday_weekday']}, ngày {dt_info['yesterday']}"
        
        # Tháng này
        if 'tháng' in message_lower or 'thang' in message_lower:
            return f"📅 Tháng này là tháng {dt_info['month']}"
        
        # Năm nay
        if 'năm' in message_lower or 'nam' in message_lower:
            return f"📅 Năm nay là năm {dt_info['year']}"
        
        return None

    def _init_rag(self):
        """Khởi tạo RAG system từ MongoDB hoặc load từ FAISS index đã build"""
        try:
            import os
            from pathlib import Path
            
            # Path to pre-built FAISS index
            faiss_index_path = Path(__file__).parent.parent / "assistant" / "data" / "faiss_index"
            
            # Khởi tạo embeddings model (cần cho cả load và build)
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            
            # ✅ OPTION 1: Load từ pre-built FAISS index (NHANH)
            if faiss_index_path.exists() and (faiss_index_path / "index.faiss").exists():
                print("📚 Đang tải RAG từ FAISS index đã build...")
                try:
                    vectorstore = FAISS.load_local(
                        str(faiss_index_path), 
                        embeddings,
                        allow_dangerous_deserialization=True  # Required for FAISS
                    )
                    
                    self.rag_retriever = vectorstore.as_retriever(
                        search_type="similarity",
                        search_kwargs={"k": 8}  # Tăng vì mỗi chunk nhỏ hơn
                    )
                    
                    # Khởi tạo LLM
                    self.rag_llm = ChatGoogleGenerativeAI(
                        model="gemini-2.5-flash",
                        temperature=0.7,
                        max_output_tokens=2048
                    )
                    
                    # Load metadata
                    import json
                    metadata_file = faiss_index_path / "metadata.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        total = metadata.get('total_chunks', metadata.get('total_articles', '?'))
                        print(f"✅ RAG sẵn sàng với {total} chunks ({metadata.get('strategy', 'loaded from index')})")
                        print(f"   📅 Built: {metadata.get('build_time', 'Unknown')[:10]}")
                        print(f"   ⚡ Mode: {metadata.get('build_mode', 'unknown')}")
                        # Cảnh báo nếu index cũ hơn 7 ngày
                        from datetime import datetime, timezone
                        build_time_str = metadata.get('build_time', '')
                        if build_time_str:
                            try:
                                build_dt = datetime.fromisoformat(build_time_str)
                                age_days = (datetime.now() - build_dt).days
                                if age_days > 7:
                                    print(f"   ⚠️ FAISS index đã {age_days} ngày tuổi! Hãy rebuild: python build_faiss_index.py")
                            except Exception:
                                pass
                    else:
                        print(f"✅ RAG sẵn sàng (loaded from {faiss_index_path})")
                    
                    # Connect MongoDB for today's news queries
                    from pymongo import MongoClient
                    _mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
                    self.mongo_client = MongoClient(_mongo_uri)
                    self.mongo_db = self.mongo_client["article-data"]
                    self.articles_collection = self.mongo_db["articles"]
                    
                    return
                    
                except Exception as load_error:
                    print(f"⚠️ Lỗi load FAISS index: {load_error}")
                    print("🔄 Falling back to rebuild from MongoDB...")
            
            # ✅ OPTION 2: Build từ MongoDB (LẦN ĐẦU hoặc khi index không có)
            print("📚 Đang build RAG từ MongoDB...")
            print("💡 Tip: Chạy 'python build_faiss_index.py' để build trước, chatbot sẽ khởi động nhanh hơn!")
            
            # MongoDB connection
            from pymongo import MongoClient
            _mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
            self.mongo_client = MongoClient(_mongo_uri)
            self.mongo_db = self.mongo_client["article-data"]
            self.articles_collection = self.mongo_db["articles"]
            
            # ✅ LẤY TOÀN BỘ DỮ LIỆU (không giới hạn), sắp xếp theo ngày mới nhất
            print("📰 Đang tải TOÀN BỘ dữ liệu từ MongoDB...")
            chunks = list(self.articles_collection.find().sort('date', -1))
            
            if not chunks:
                print("⚠️ Không có chunks trong database!")
                self.rag_retriever = None
                self.rag_llm = None
                return
            
            print(f"📊 Tổng số chunks: {len(chunks)}")
            if chunks and chunks[0].get('date'):
                from datetime import datetime
                latest = chunks[0].get('date')
                oldest = chunks[-1].get('date')
                if isinstance(latest, datetime):
                    print(f"   → Từ {oldest.strftime('%d/%m/%Y')} đến {latest.strftime('%d/%m/%Y')}")
            
            # ✅ MỖI CHUNK = 1 DOCUMENT (KHÔNG merge) → Precision cao
            print("📝 Đang tạo documents (1 chunk = 1 vector)...")
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
            
            print(f"✅ Created {len(documents)} granular documents (high precision)")
            
            # Tạo embeddings và vector store
            print("🧠 Đang tạo embeddings...")
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            
            print("🔍 Đang xây dựng FAISS vector store...")
            vectorstore = FAISS.from_documents(documents, embeddings)
            self.rag_retriever = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 8}  # Tăng lên vì giờ mỗi chunk nhỏ hơn
            )
            
            # Khởi tạo LLM
            self.rag_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.7,
                max_output_tokens=2048
            )
            
            print(f"✅ RAG đã sẵn sàng với {len(documents)} chunks (granular vectors)!")
            
            # 💾 Auto-save FAISS index + mark as embedded
            try:
                from pathlib import Path
                faiss_index_path = Path(__file__).parent.parent / "assistant" / "data" / "faiss_index"
                faiss_index_path.mkdir(parents=True, exist_ok=True)
                
                print(f"💾 Đang lưu FAISS index vào disk...")
                vectorstore.save_local(str(faiss_index_path))
                
                # Mark all chunks as embedded
                chunk_ids = [chunk['_id'] for chunk in chunks]
                result = self.articles_collection.update_many(
                    {"_id": {"$in": chunk_ids}},
                    {"$set": {"embedded": True, "embedded_at": datetime.now()}}
                )
                
                # Save metadata
                import json
                from datetime import datetime
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
                
                print(f"   ✅ Saved to {faiss_index_path}")
                print(f"   ✅ Marked {result.modified_count} chunks as embedded")
                print(f"   💡 Next run: python build_faiss_index.py (incremental)")
            except Exception as save_error:
                print(f"   ⚠️ Could not save index: {save_error}")
                print(f"   ℹ️ Chatbot will work but will rebuild on next restart")
            
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
            return "Xin lỗi, hệ thống tin tức hiện chưa sẵn sàng 😢"
        
        try:
            import re
            from datetime import datetime, timedelta
            
            # ===== 1. Kiểm tra user hỏi về tin số mấy (từ list vừa show) =====
            number_match = re.search(r'(?:tin|bài)\s*(?:tức|báo)?\s*(\d+)', message.lower())
            if number_match and self.context.last_news_list:
                news_index = int(number_match.group(1)) - 1  # Convert to 0-based index
                if 0 <= news_index < len(self.context.last_news_list):
                    # Lấy article data từ list
                    article = self.context.last_news_list[news_index]
                    title = article['title']
                    
                    # Tìm tất cả chunks của bài này từ MongoDB
                    chunks = list(self.articles_collection.find({
                        'title': title
                    }).sort('chunk_index', 1))
                    
                    if not chunks:
                        return f"❌ Không tìm thấy nội dung bài '{title}'"
                    
                    # Merge chunks thành full content
                    full_content = "\n\n".join([c.get('chunk', '') for c in chunks])
                    
                    # Tóm tắt bằng Gemini
                    prompt = ChatPromptTemplate.from_template("""
Bạn là trợ lý tin tức thông minh.

Nội dung bài báo:
{content}

Yêu cầu:
- KHÔNG bắt đầu bằng lời chào hay giới thiệu bản thân
- Bắt đầu ngay bằng tiêu đề bài: "📰 **{title}**"
- Tóm tắt CHI TIẾT (3-5 đoạn): điểm chính, thông tin quan trọng, diễn biến
- Dùng emoji phù hợp 📰 📊 🇻🇳

Tóm tắt (tiếng Việt):""")
                    
                    try:
                        chain = prompt | self.rag_llm | StrOutputParser()
                        summary = chain.invoke({
                            "content": full_content[:6000],
                            "title": title
                        })
                        return summary
                    except Exception as llm_error:
                        # Fallback: Trả content trực tiếp
                        return f"📰 **{title}**\n\n{full_content[:2048]}"
            # ===== 2. Kiểm tra query theo ngày (hôm nay, hôm qua, ngày X) =====
            is_date_query = any(word in message.lower() for word in [
                'hôm nay', 'hôm qua', 'ngày hôm nay', 'tin tức hôm nay',
                'tin tức ngày', 'bài báo hôm nay', 'tin hôm nay'
            ])
            
            # Kiểm tra "mới nhất" → hiển thị 5 bài mới nhất
            is_latest_query = any(word in message.lower() for word in [
                'mới nhất', 'gần đây', 'vừa rồi', 'đang nóng'
            ]) and not any(word in message.lower() for word in ['như nào', 'thế nào', 'chi tiết', 'nói gì'])
            
            if is_latest_query:
                # Lấy 5 bài mới nhất
                recent_chunks = list(self.articles_collection.find().sort('date', -1).limit(50))
                articles_by_title = {}
                for chunk in recent_chunks:
                    title = chunk.get('title', 'Unknown')
                    if title not in articles_by_title:
                        articles_by_title[title] = {
                            'title': title,
                            'url': chunk.get('url', ''),
                            'date': chunk.get('date')
                        }
                    if len(articles_by_title) >= 10:
                        break
                
                article_list = list(articles_by_title.values())
                display_list = random.sample(article_list, min(5, len(article_list)))
                self.context.last_news_list = display_list
                
                # Lấy ngày của bài mới nhất
                latest_date = article_list[0].get('date') if article_list else None
                date_label = latest_date.strftime('%d/%m/%Y') if isinstance(latest_date, datetime) else ''
                
                response = f"📰 **Tin tức mới nhất{' (' + date_label + ')' if date_label else ''}**:\n\n"
                for i, article in enumerate(display_list, 1):
                    response += f"{i}. {article['title']}\n"
                response += f"\n💡 Hỏi 'tin 1', 'tin 2'... để xem chi tiết bài nào!"
                return response
            
            if is_date_query:
                # Xác định ngày cần query
                if 'hôm qua' in message.lower():
                    target_date = datetime.now() - timedelta(days=1)
                else:
                    # Thử parse ngày cụ thể: dd/mm/yyyy hoặc dd/mm
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
                
                # Query MongoDB theo ngày
                date_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                date_end = date_start + timedelta(days=1)
                
                # Lấy tất cả chunks của ngày đó
                chunks = list(self.articles_collection.find({
                    'date': {
                        '$gte': date_start,
                        '$lt': date_end
                    }
                }))
                
                if not chunks:
                    # Fallback: Lấy tin mới nhất
                    recent = list(self.articles_collection.find().sort('date', -1).limit(1))
                    if recent:
                        latest_date = recent[0].get('date')
                        if isinstance(latest_date, datetime):
                            date_str = latest_date.strftime('%d/%m/%Y')
                        else:
                            date_str = str(latest_date)[:10]
                        return f"⚠️ Không có tin tức {target_date.strftime('%d/%m/%Y')}. Tin mới nhất là ngày {date_str}."
                    else:
                        return "Xin lỗi, không có tin tức trong hệ thống 😢"
                
                # Group theo title (vì 1 article = nhiều chunks)
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
                
                # Chọn ngẫu nhiên tối đa 5 bài
                display_list = random.sample(article_list, min(5, len(article_list)))
                
                # Lưu vào context để user có thể hỏi "tin 1", "tin 2"
                self.context.last_news_list = display_list
                
                # Format response: List titles
                date_str = target_date.strftime('%d/%m/%Y')
                weekday_vn = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
                day_name = weekday_vn[target_date.weekday()]
                
                response = f"📰 **Tin tức {day_name}, {date_str}**:\n\n"
                
                for i, article in enumerate(display_list, 1):
                    response += f"{i}. {article['title']}\n"
                
                response += f"\n💡 Hỏi 'tin 1', 'tin 2'... để xem chi tiết bài nào!"
                
                return response
            
            # ===== 3. RAG query thông thường (không phải date-based) =====
            # Nếu đến đây là các query RAG bình thường
            
            # Retrieve từ vectorstore tổng hợp
            docs = self.rag_retriever.invoke(message)
            
            if not docs:
                return "Xin lỗi, tôi không tìm thấy tin tức phù hợp 😢"
            
            # Format context
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Phân tích độ chi tiết của câu hỏi
            is_detailed_question = any(word in message.lower() for word in [
                'như nào', 'thế nào', 'chi tiết', 'cụ thể', 'thông tin', 
                'nội dung', 'diễn biến', 'tình hình', 'giải thích'
            ])
            
            # Lấy thông tin ngày giờ hiện tại
            from datetime import datetime
            import locale
            try:
                locale.setlocale(locale.LC_TIME, 'vi_VN.UTF-8')
            except:
                pass
            
            # Create prompt (điều chỉnh theo loại câu hỏi)
            if is_detailed_question:
                prompt = ChatPromptTemplate.from_template("""
Bạn là trợ lý tin tức thông minh.

Quy tắc:
- KHÔNG bắt đầu bằng lời chào hỏi ("Chào bạn", "Hello"...)
- Trả lời THẲNG VÀO NỘI DUNG — nêu đề tài, sự kiện chính ngay câu đầu tiên
- KHÔNG nói "dựa trên ngữ cảnh" hay "theo context"
- CHỈ dùng thông tin trong Context, KHÔNG bịa đặt
- Trả lời ĐẦY ĐỦ các điểm chính
- Chia thành đoạn nếu dài

Context:
{context}

Câu hỏi: {question}

Trả lời chi tiết (tiếng Việt):""")
            else:
                prompt = ChatPromptTemplate.from_template("""
Bạn là trợ lý tin tức thông minh.

Quy tắc:
- KHÔNG bắt đầu bằng lời chào hỏi ("Chào bạn", "Hello"...)
- Trả lời THẲNG VÀO NỘI DUNG — nêu đề tài hoặc sự kiện ngay câu đầu
- KHÔNG nói "dựa trên ngữ cảnh" hay "theo context"
- CHỈ dùng thông tin trong Context, KHÔNG bịa đặt
- NGẮN GỌN, đủ ý

Context:
{context}

Câu hỏi: {question}

Trả lời ngắn gọn (tiếng Việt):""")
            
            # Create RAG chain
            rag_chain = (
                {
                    "context": lambda x: context,
                    "question": RunnablePassthrough(),
                }
                | prompt
                | self.rag_llm
                | StrOutputParser()
            )
            
            # Get answer
            try:
                answer = rag_chain.invoke(message)
                
                # Lưu list docs để user có thể hỏi "tin 1", "tin 2"...
                if not is_detailed_question:
                    self.context.last_news_list = docs[:5]
                    
            except Exception as llm_error:
                # Nếu quota exceeded, trả về CONTENT thay vì chỉ titles
                error_msg = str(llm_error)
                if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                    print(f"⚠️ Gemini quota exceeded, dùng fallback response với content")
                    
                    is_today_query = any(word in message.lower() for word in ['hôm nay', 'tin hôm nay', 'tin tức hôm nay'])
                    
                    # Nếu hỏi chi tiết → Hiển thị nội dung raw của bài đầu tiên
                    if is_detailed_question or any(word in message.lower() for word in ['tin', 'bài', 'như nào', 'thế nào']):
                        if docs and len(docs) > 0:
                            best_article = docs[0]
                            best_title = best_article.metadata.get('title', 'Tin tức')
                            return f"📰 **{best_title}**\n\n{best_article.page_content[:1500]}\n\n_(Tóm tắt bằng AI tạm thời không khả dụng do giới hạn quota)_"
                    
                    # Nếu hỏi tổng quan → List titles như cũ
                    titles = [doc.metadata.get('title', '') for doc in docs[:5] if doc.metadata.get('title')]
                    if titles:
                        # Lưu list để user có thể hỏi "tin 1", "tin 2"...
                        self.context.last_news_list = docs[:5]
                        
                        answer = "📰 Tin tức "
                        if is_today_query:
                            answer += "hôm nay:\n\n"
                        else:
                            answer += "nổi bật:\n\n"
                        for i, title in enumerate(titles, 1):
                            answer += f"{i}. {title}\n"
                        answer += "\n💡 Hỏi 'tin 1 như nào?' hoặc 'bài 2 nói gì?' để xem chi tiết"
                        return answer.strip()
                    else:
                        return "Xin lỗi, không thể tạo tóm tắt lúc này 😢"
                else:
                    raise  # Re-raise nếu không phải quota error
            
            return answer
            
        except Exception as e:
            print(f"❌ Lỗi RAG: {e}")
            return "Xin lỗi, có lỗi xảy ra khi tra cứu tin tức 😢"

    def get_response(self, user_message: str) -> str:
        message_lower = user_message.lower().strip()
        
        # ✅ 1. XÁC NHẬN (ưu tiên tuyệt đối - user đang trả lời câu hỏi của bot)
        #    Phải đứng đầu để không bị datetime/news handler tranh mất
        if self.context.awaiting_confirmation:
            return self._handle_confirmation(message_lower)
        
        # ✅ 2. DATETIME (hôm nay thứ mấy, ngày mai...)
        datetime_response = self._handle_datetime_query(user_message)
        if datetime_response:
            return datetime_response
        
        # ✅ 3. FIXED COMMANDS (exact match lệnh điều khiển thiết bị)
        device_control_result = self._handle_device_control(user_message, [])
        if device_control_result:
            return device_control_result
        
        # ✅ 4. TIN TỨC / RAG (sau smart home để tránh xung đột)
        if self._is_news_query(message_lower):
            return self._handle_news_query(user_message)

        result = self.nlp.process(user_message)
        intent = result['intent']['type']
        confidence = result['intent']['confidence']
        entities = result['entities']
        
        print(f"🧠 Intent: {intent} ({confidence})")
        print(f"📦 Entities: {entities}")

        # Kiểm tra status/sensor
        if intent == 'check_status':
            return self._handle_status_check(user_message, entities)
        
        elif intent == 'query_sensor':
            return self._handle_sensor_query(user_message)
        
        elif intent == 'control_device':
            # Nếu đến đây nghĩa là intent là control_device nhưng không match fixed_commands
            # → Lệnh không hợp lệ
            return """⚠️ Lệnh không hợp lệ! Vui lòng sử dụng đúng cú pháp:

💡 Điều khiển thiết bị:
• "Bật đèn phòng khách"
• "Tắt đèn phòng ngủ"
• "Bật điều hòa phòng khách"

🌡️ Điều chỉnh nhiệt độ:
• "Bật điều hòa phòng khách 25 độ"
• "Tăng điều hòa phòng ngủ 2 độ"
• "Giảm điều hòa phòng khách 1 độ"

📍 Phòng: phòng khách, phòng ngủ, phòng tắm (hoặc nhà tắm)
"""
        
        elif intent == 'greeting':
            # Chỉ greeting nếu câu ngắn (1-4 từ) hoặc confidence cao
            word_count = len(user_message.split())
            if word_count <= 4 or confidence >= 0.5:
                return self._handle_greeting()
            else:
                # Câu dài → Có thể là câu hỏi → Thử RAG
                return self._generate_default_response(user_message)
        
        elif intent == 'farewell':
            return "Tạm biệt! 👋 Chúc bạn một ngày tốt lành!"
        
        elif intent == 'gratitude':
            return "Không có gì! 😊 Tôi luôn sẵn sàng giúp bạn!"
        
        elif intent == 'set_value':
            return self._handle_set_value(user_message, entities)
        
        elif intent == 'help':
            return self._get_help_message()
        
        else:
            # Check knowledge base trước
            message_lower = user_message.lower()
            for key, response in self.knowledge_base.items():
                if key in message_lower:
                    return response
            
            # Thử RAG cho mọi câu hỏi còn lại
            return self._generate_default_response(user_message)

    def _handle_greeting(self) -> str:
        greetings = [
            "Xin chào! 👋 Tôi có thể giúp bạn điều khiển nhà thông minh!",
            "Chào bạn! 😊 Bạn muốn tôi giúp gì nào?",
            "Hello! 👋 Tôi là Smart Home Assistant!",
        ]
        return random.choice(greetings)

    def _handle_device_control(self, message: str, entities: list) -> str:
        message_lower = message.lower().strip()
        
        # ==================================================
        # BƯỚC 1: KIỂM TRA LỆNH FIX CỨNG TRƯỚC
        # ==================================================
        
        # Check exact match với fixed commands
        for command_text, command_data in self.fixed_commands.items():
            if command_text in message_lower:
                return self._execute_device_command(
                    command_data['device'],
                    command_data['location'],
                    command_data['action']
                )
        
        # ==================================================
        # BƯỚC 2: XỬ LÝ ĐIỀU CHỈNH NHIỆT ĐỘ
        # ==================================================
        
        import re
        
        # Pattern: "bật điều hòa phòng khách 25 độ"
        match = re.search(r'(bật|tắt)\s+điều hòa\s+(phòng khách|phòng ngủ|phòng tắm)\s+(\d+)\s*độ', message_lower)
        if match:
            action_word = match.group(1)
            room_vn = match.group(2)
            temp = int(match.group(3))
            
            # Map room
            room_map = {
                'phòng khách': 'living_room',
                'phòng ngủ': 'bedroom',
                'phòng tắm': 'bathroom'
            }
            location = room_map.get(room_vn, 'living_room')
            
            # Validate nhiệt độ
            if 16 <= temp <= 30:
                # Bật điều hòa với nhiệt độ cụ thể
                if self.mqtt:
                    self.mqtt.send_command('ac', location, True)
                    self.mqtt.send_command('ac_temp', location, temp)
                return f"✅ Đã bật điều hòa {room_vn} ở {temp}°C!"
            else:
                return "⚠️ Nhiệt độ phải từ 16°C đến 30°C!"
        
        # Pattern: "tăng điều hòa phòng khách 2 độ"
        match = re.search(r'tăng\s+điều hòa\s+(phòng khách|phòng ngủ|phòng tắm)\s+(\d+)\s*độ', message_lower)
        if match:
            room_vn = match.group(1)
            delta = int(match.group(2))
            
            room_map = {'phòng khách': 'living_room', 'phòng ngủ': 'bedroom', 'phòng tắm': 'bathroom'}
            location = room_map.get(room_vn, 'living_room')
            
            # Lấy nhiệt độ hiện tại (giả sử 25°C)
            current_temp = 25
            if self.mqtt:
                states = self.mqtt.get_device_states()
                current_temp = states['ac'].get('temperature', 25)
            
            new_temp = min(current_temp + delta, 30)
            
            if self.mqtt:
                self.mqtt.send_command('ac_temp', location, new_temp)
            
            return f"✅ Đã tăng nhiệt độ điều hòa {room_vn} lên {new_temp}°C (+{delta}°C)"
        
        # Pattern: "giảm điều hòa phòng khách 1 độ"
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
            
            return f"✅ Đã giảm nhiệt độ điều hòa {room_vn} xuống {new_temp}°C (-{delta}°C)"
        
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
        
        status_lines = ["📊 Trạng thái nhà thông minh:"]
        
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

    def _handle_sensor_query(self, message: str) -> str:
        """Xử lý truy vấn cảm biến"""
        if not self.mqtt:
            return "❌ Không thể đọc cảm biến - MQTT chưa kết nối!"
        
        sensors = self.mqtt.get_sensor_data()
        message_lower = message.lower()
        
        # Kiểm tra độ ẩm TRƯỚC (vì "độ" có thể match với "nhiệt độ")
        if 'độ ẩm' in message_lower or 'ẩm' in message_lower:
            humidity = sensors['humidity']
            if humidity < 40:
                return f"💧 Độ ẩm hiện tại: **{humidity}%** - Khá khô, nên bật máy tạo ẩm!"
            elif humidity > 70:
                return f"💧 Độ ẩm hiện tại: **{humidity}%** - Khá ẩm, nên chế độ tải sươi!"
            else:
                return f"💧 Độ ẩm hiện tại: **{humidity}%** - Mức thoải mái!"
        
        # Kiểm tra nhiệt độ
        if 'nhiệt độ' in message_lower or 'nóng' in message_lower or 'lạnh' in message_lower or 'bao nhiêu độ' in message_lower:
            temp = sensors['temperature']
            if temp > 30:
                # Gợi ý bật điều hòa và chờ xác nhận
                self.context.awaiting_confirmation = True
                self.context.suggested_action = {'type': 'turn_on_ac'}
                return f"🌡️ Nhiệt độ hiện tại: **{temp}°C** - Khá nóng! Bạn có muốn bật điều hòa không? (có/không)"
            elif temp < 20:
                return f"🌡️ Nhiệt độ hiện tại: **{temp}°C** - Khá lạnh!"
            else:
                return f"🌡️ Nhiệt độ hiện tại: **{temp}°C** - Nhiệt độ dễ chịu!"
        
        # Kiểm tra ánh sáng
        if 'ánh sáng' in message_lower or 'sáng' in message_lower or 'tối' in message_lower:
            light = sensors['light']
            if light < 100:
                # Gợi ý bật đèn và chờ xác nhận
                self.context.awaiting_confirmation = True
                self.context.suggested_action = {'type': 'turn_on_light'}
                return f"☀️ Ánh sáng hiện tại: **{light} lux** - Khá tối! Bạn có muốn bật đèn không? (có/không)"
            elif light > 500:
                return f"☀️ Ánh sáng hiện tại: **{light} lux** - Rất sáng!"
            else:
                return f"☀️ Ánh sáng hiện tại: **{light} lux** - Ánh sáng vừa phải!"
        
        # Trả về tất cả sensor data
        return f"""🌡️ **Dữ liệu cảm biến:**
• Nhiệt độ: {sensors['temperature']}°C
• Độ ẩm: {sensors['humidity']}%
• Ánh sáng: {sensors['light']} lux"""

    def _handle_set_value(self, message: str, entities: list) -> str:
        """Xử lý cài đặt giá trị (nhiệt độ điều hòa)"""
        message_lower = message.lower()
        
        # Tìm giá trị số trong message
        import re
        numbers = re.findall(r'\d+', message)
        
        if numbers:
            value = int(numbers[0])
            
            # Cài đặt nhiệt độ điều hòa
            if 'điều hòa' in message_lower:
                if 16 <= value <= 30:
                    if self.mqtt:
                        success = self.mqtt.send_command('ac_temp', 'bedroom', value)
                        if success:
                            return f"✅ Đã cài đặt điều hòa ở {value}°C!"
                        else:
                            return "❌ Không thể cài đặt nhiệt độ!"
                else:
                    return "⚠️ Nhiệt độ phải từ 16°C đến 30°C!"
        
        return "🤔 Bạn muốn cài đặt gì? Ví dụ: 'Đặt điều hòa 25 độ'"

    def _get_location_vietnamese(self, location: str) -> str:
        """Chuyển đổi tên location sang tiếng Việt"""
        mapping = {
            'living_room': 'phòng khách',
            'bedroom': 'phòng ngủ',
            'bathroom': 'phòng tắm',
        }
        return mapping.get(location, location)

    def _get_help_message(self) -> str:
        """Trả về hướng dẫn sử dụng"""
        return """🏠 Hướng dẫn sử dụng Smart Home:
💡 Bật/Tắt thiết bị:
• "Bật đèn phòng khách"
• "Tắt đèn phòng ngủ"
• "Bật điều hòa phòng khách"
• "Tắt điều hòa phòng ngủ"
• "Bật đèn nhà tắm"

🌡️ Điều chỉnh nhiệt độ điều hòa:
• "Bật điều hòa phòng khách 25 độ"
• "Tăng điều hòa phòng ngủ 2 độ"
• "Giảm điều hòa phòng khách 1 độ"

📊 Kiểm tra trạng thái:
• "Trạng thái nhà"

🌡️ Xem cảm biến:
• "Nhiệt độ bao nhiêu?"
• "Độ ẩm hiện tại"

📰 Hỏi tin tức:
• "Tin tức hôm nay"
• "Thông tin về [chủ đề]"
"""

    def _handle_context_response(self, message: str) -> str:
        """Xử lý câu trả lời dựa trên context trước đó"""
        # Giờ không còn cần context vì dùng fixed commands
        return None

    def _handle_confirmation(self, message: str) -> str:
        """Xử lý xác nhận có/không"""
        
        # Kiểm tra YES
        if any(word in message for word in self.confirm_yes):
            if self.context.suggested_action:
                action = self.context.suggested_action
                self.context.clear()
                
                # Thực hiện hành động gợi ý
                if action.get('type') == 'turn_on_light':
                    # Bật tất cả đèn
                    results = []
                    for loc in ['living_room', 'bedroom', 'bathroom']:
                        if self.mqtt:
                            self.mqtt.send_command('light', loc, True)
                            results.append(self._get_location_vietnamese(loc))
                    return f"✅ Đã bật đèn {', '.join(results)}!"
                
                elif action.get('type') == 'turn_on_ac':
                    if self.mqtt:
                        self.mqtt.send_command('ac', 'bedroom', True)
                    return "✅ Đã bật điều hòa phòng ngủ!"
            
            self.context.clear()
            return "👍 OK!"
        
        # Kiểm tra NO
        elif any(word in message for word in self.confirm_no):
            self.context.clear()
            return "👌 Đã hủy. Bạn cần gì khác không?"
        
        # Không hiểu
        self.context.clear()
        return "🤔 Xin lỗi, tôi không hiểu. Bạn có thể nói 'có' hoặc 'không'."

    def _execute_device_command(self, device_type: str, location: str, action: bool) -> str:
        """Thực hiện lệnh điều khiển thiết bị"""
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
            f"Tôi đã {status} {device_vn} {location_vn} cho bạn rồi ạ 😊",
            f"Đã {status} {device_vn} {location_vn} rồi nhé! ✅",
            f"Dạ, {device_vn} {location_vn} đã được {status} rồi ạ 😊"
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
        """Tạo câu trả lời mặc định hoặc dùng RAG"""
        # Thử dùng RAG cho mọi câu hỏi
        if self.rag_retriever and self.rag_llm:
            try:
                # Retrieve docs để check xem có kết quả không
                docs = self.rag_retriever.invoke(user_message)
                
                # Nếu tìm thấy docs với similarity tốt → Dùng RAG
                if docs:
                    answer = self._handle_news_query(user_message)
                    # Chỉ fallback nếu có lỗi hệ thống
                    if "có lỗi xảy ra" not in answer.lower():
                        return answer
            except Exception as e:
                error_msg = str(e)
                # Kiểm tra quota exceeded
                if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                    print(f"⚠️ RAG quota exceeded, dùng fallback response")
                else:
                    print(f"⚠️ RAG error in default response: {e}")
        
        # Fallback responses
        responses = [
            "🤔 Tôi chưa hiểu ý bạn. Bạn có thể nói rõ hơn không?",
            "Bạn có muốn xem tin tức ngày hôm nay không? 📰",
            "Bạn có cần tôi giúp gì không? 😊",
        ]
        return random.choice(responses)


# Global chatbot instance
_chatbot_instance = None

def get_chatbot(mqtt_handler=None):
    """Lấy global chatbot instance"""
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = Chatbot(mqtt_handler)
    return _chatbot_instance
