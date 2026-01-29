"""
Smart Home Chatbot với NLP và Context Memory
"""
import random
from assistant.pipeline import NLPPipeline
from backend.mqtt_handler import get_mqtt_handler


class ConversationContext:
    """Lưu trữ context của cuộc hội thoại"""
    
    def __init__(self):
        self.pending_action = None      # Action đang chờ (on/off)
        self.pending_device = None      # Device đang chờ (light/ac)
        self.pending_location = None    # Location đang chờ
        self.pending_intent = None      # Intent đang chờ xác nhận
        self.last_question = None       # Câu hỏi cuối cùng bot hỏi
        self.awaiting_confirmation = False  # Đang chờ xác nhận có/không
        self.suggested_action = None    # Hành động gợi ý (bật đèn khi tối)
    
    def clear(self):
        """Xóa context sau khi hoàn thành"""
        self.pending_action = None
        self.pending_device = None
        self.pending_location = None
        self.pending_intent = None
        self.last_question = None
        self.awaiting_confirmation = False
        self.suggested_action = None
    
    def has_pending(self):
        """Kiểm tra có context đang chờ không"""
        return (self.pending_device is not None or 
                self.pending_location is not None or
                self.pending_action is not None or
                self.awaiting_confirmation)


class Chatbot:
    def __init__(self, mqtt_handler=None):
        """
        Khởi tạo chatbot với NLP Pipeline và MQTT
        """
        print("🤖 Đang khởi tạo Chatbot...")
        self.nlp = NLPPipeline()
        self.mqtt = mqtt_handler or get_mqtt_handler()
        self.context = ConversationContext()  # Context Memory
        print("✅ Chatbot đã sẵn sàng!")
        
        # Knowledge base cho các câu hỏi thông thường
        self.knowledge_base = {
            'xin chào': 'Xin chào! 👋 Tôi có thể giúp bạn điều khiển nhà thông minh!',
            'hello': 'Hello! 👋 How can I help you?',
            'ai là cái tên của bạn': 'Tôi là AI Smart Home Assistant!',
            'bạn là ai': 'Tôi là AI Smart Home Assistant, giúp bạn điều khiển nhà thông minh!',
            'cảm ơn': 'Không có gì! 😊 Nếu cần giúp đỡ gì khác thì cứ hỏi tôi!',
            'tạm biệt': 'Tạm biệt! 👋 Rất vui được gặp bạn!',
            'bye': 'Goodbye! 👋',
        }
        
        # Device name mapping
        self.device_names = {
            'đèn': 'light',
            'den': 'light',
            'light': 'light',
            'điều hòa': 'ac',
            'dieu hoa': 'ac',
            'máy lạnh': 'ac',
            'may lanh': 'ac',
            'ac': 'ac',
        }
        
        # Location mapping
        self.location_names = {
            'phòng khách': 'living_room',
            'phong khach': 'living_room',
            'living room': 'living_room',
            'phòng ngủ': 'bedroom',
            'phong ngu': 'bedroom',
            'bedroom': 'bedroom',
            'phòng tắm': 'bathroom',
            'phong tam': 'bathroom',
            'bathroom': 'bathroom',
            'nhà tắm': 'bathroom',
            'nha tam': 'bathroom',
        }
        
        # Confirmation words
        self.confirm_yes = ['có', 'co', 'yes', 'ok', 'được', 'duoc', 'ừ', 'u', 'đúng', 'dung', 'bật', 'bat', 'mở', 'mo']
        self.confirm_no = ['không', 'khong', 'no', 'thôi', 'thoi', 'hủy', 'huy', 'cancel']

    def get_response(self, user_message: str) -> str:
        """
        Xử lý tin nhắn và trả về phản hồi
        """
        message_lower = user_message.lower().strip()
        
        # Kiểm tra xem có đang chờ xác nhận không
        if self.context.awaiting_confirmation:
            return self._handle_confirmation(message_lower)
        
        # Kiểm tra context - user đang trả lời câu hỏi trước đó
        if self.context.has_pending():
            context_response = self._handle_context_response(message_lower)
            if context_response:
                return context_response
        
        # Phân tích bằng NLP Pipeline
        result = self.nlp.process(user_message)
        intent = result['intent']['type']
        confidence = result['intent']['confidence']
        entities = result['entities']
        
        print(f"🧠 Intent: {intent} ({confidence})")
        print(f"📦 Entities: {entities}")
        
        # Xử lý theo intent
        if intent == 'control_device':
            return self._handle_device_control(user_message, entities)
        
        elif intent == 'check_status':
            return self._handle_status_check(user_message, entities)
        
        elif intent == 'query_sensor':
            return self._handle_sensor_query(user_message)
        
        elif intent == 'set_value':
            return self._handle_set_value(user_message, entities)
        
        elif intent == 'greeting':
            return self._handle_greeting()
        
        elif intent == 'farewell':
            return "Tạm biệt! 👋 Chúc bạn một ngày tốt lành!"
        
        elif intent == 'gratitude':
            return "Không có gì! 😊 Tôi luôn sẵn sàng giúp bạn!"
        
        elif intent == 'help':
            return self._get_help_message()
        
        else:
            # Kiểm tra knowledge base
            message_lower = user_message.lower()
            for key, response in self.knowledge_base.items():
                if key in message_lower:
                    return response
            
            return self._generate_default_response(user_message)

    def _handle_greeting(self) -> str:
        """Xử lý lời chào"""
        greetings = [
            "Xin chào! 👋 Tôi có thể giúp bạn điều khiển nhà thông minh!",
            "Chào bạn! 😊 Bạn muốn tôi giúp gì nào?",
            "Hello! 👋 Tôi là Smart Home Assistant!",
        ]
        return random.choice(greetings)

    def _handle_device_control(self, message: str, entities: list) -> str:
        """Xử lý điều khiển thiết bị"""
        message_lower = message.lower()
        
        # Tìm device và location từ message
        device_type = None
        location = None
        action = None
        
        # Tìm device
        for name, dtype in self.device_names.items():
            if name in message_lower:
                device_type = dtype
                break
        
        # Tìm location
        for name, loc in self.location_names.items():
            if name in message_lower:
                location = loc
                break
        
        # Tìm action
        if any(word in message_lower for word in ['bật', 'bat', 'mở', 'mo', 'on', 'turn on']):
            action = True
        elif any(word in message_lower for word in ['tắt', 'tat', 'off', 'turn off', 'đóng', 'dong']):
            action = False
        
        # Nếu thiếu thông tin - lưu context và hỏi
        if not device_type:
            self.context.pending_action = action
            self.context.pending_intent = 'control_device'
            self.context.last_question = 'device'
            return "🤔 Bạn muốn điều khiển thiết bị gì? (đèn, điều hòa...)"
        
        if location is None:
            self.context.pending_device = device_type
            self.context.pending_action = action
            self.context.pending_intent = 'control_device'
            self.context.last_question = 'location'
            device_vn = "đèn" if device_type == 'light' else "điều hòa"
            return f"🤔 Bạn muốn điều khiển {device_vn} ở phòng nào? (phòng khách, phòng ngủ, phòng tắm)"
        
        if action is None:
            self.context.pending_device = device_type
            self.context.pending_location = location
            self.context.pending_intent = 'control_device'
            self.context.last_question = 'action'
            device_vn = "đèn" if device_type == 'light' else "điều hòa"
            return f"🤔 Bạn muốn bật hay tắt {device_vn}?"
        
        # Đã đủ thông tin - thực hiện lệnh
        return self._execute_device_command(device_type, location, action)

    def _handle_status_check(self, message: str, entities: list) -> str:
        """Xử lý kiểm tra trạng thái"""
        if not self.mqtt:
            return "❌ Không thể kiểm tra trạng thái - MQTT chưa kết nối!"
        
        states = self.mqtt.get_device_states()
        message_lower = message.lower()
        
        # Kiểm tra thiết bị cụ thể
        for name, dtype in self.device_names.items():
            if name in message_lower:
                for loc_name, loc in self.location_names.items():
                    if loc_name in message_lower:
                        if dtype == 'light':
                            status = states['lights'].get(loc, False)
                            status_text = "đang bật 💡" if status else "đang tắt 🌙"
                            return f"Đèn {self._get_location_vietnamese(loc)} {status_text}"
                        elif dtype == 'ac':
                            status = states['ac'].get(loc, False)
                            temp = states['ac'].get('temperature', 20)
                            status_text = f"đang bật ({temp}°C) ❄️" if status else "đang tắt"
                            return f"Điều hòa {self._get_location_vietnamese(loc)} {status_text}"
        
        # Trả về tất cả trạng thái
        return self._get_all_status()

    def _get_all_status(self) -> str:
        """Lấy trạng thái tất cả thiết bị"""
        if not self.mqtt:
            return "❌ MQTT chưa kết nối!"
        
        states = self.mqtt.get_device_states()
        sensors = self.mqtt.get_sensor_data()
        
        status_lines = ["📊 **Trạng thái nhà thông minh:**\n"]
        
        # Lights
        status_lines.append("💡 **Đèn:**")
        for loc, state in states['lights'].items():
            loc_vn = self._get_location_vietnamese(loc)
            status = "Bật ✓" if state else "Tắt"
            status_lines.append(f"  • {loc_vn}: {status}")
        
        # AC
        status_lines.append("\n❄️ **Điều hòa:**")
        ac_status = "Bật ✓" if states['ac']['bedroom'] else "Tắt"
        status_lines.append(f"  • Phòng ngủ: {ac_status} ({states['ac']['temperature']}°C)")
        
        # Sensors
        status_lines.append("\n🌡️ **Cảm biến:**")
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
        if any(word in message_lower for word in ['độ ẩm', 'do am', 'ẩm', 'am', 'humidity']):
            humidity = sensors['humidity']
            if humidity < 40:
                return f"💧 Độ ẩm hiện tại: **{humidity}%** - Khá khô, nên bật máy tạo ẩm!"
            elif humidity > 70:
                return f"💧 Độ ẩm hiện tại: **{humidity}%** - Khá ẩm, nên bật quạt thông gió!"
            else:
                return f"💧 Độ ẩm hiện tại: **{humidity}%** - Mức thoải mái!"
        
        # Kiểm tra nhiệt độ
        if any(word in message_lower for word in ['nhiệt độ', 'nhiet do', 'nóng', 'nong', 'lạnh', 'lanh', 'temperature', 'bao nhiêu độ', 'bao nhieu do']):
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
        if any(word in message_lower for word in ['ánh sáng', 'anh sang', 'sáng', 'tối', 'sang', 'toi', 'light', 'lux']):
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
            if any(word in message_lower for word in ['điều hòa', 'dieu hoa', 'máy lạnh', 'may lanh', 'ac']):
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
        return """🏠 **Hướng dẫn sử dụng Smart Home:**

**💡 Điều khiển đèn:**
• "Bật đèn phòng khách"
• "Tắt đèn phòng ngủ"

**❄️ Điều khiển điều hòa:**
• "Bật điều hòa phòng ngủ"
• "Đặt điều hòa 25 độ"

**📊 Kiểm tra trạng thái:**
• "Trạng thái nhà"
• "Đèn phòng khách đang bật hay tắt?"

**🌡️ Xem cảm biến:**
• "Nhiệt độ bao nhiêu?"
• "Độ ẩm hiện tại"
• "Ánh sáng trong nhà"
"""

    def _handle_context_response(self, message: str) -> str:
        """Xử lý câu trả lời dựa trên context trước đó"""
        
        # Nếu đang chờ location
        if self.context.last_question == 'location':
            location = None
            for name, loc in self.location_names.items():
                if name in message:
                    location = loc
                    break
            
            if location:
                device_type = self.context.pending_device
                action = self.context.pending_action
                
                # Nếu chưa có action, hỏi tiếp
                if action is None:
                    self.context.pending_location = location
                    self.context.last_question = 'action'
                    device_vn = "đèn" if device_type == 'light' else "điều hòa"
                    return f"🤔 Bạn muốn bật hay tắt {device_vn}?"
                
                # Đã đủ thông tin
                self.context.clear()
                return self._execute_device_command(device_type, location, action)
        
        # Nếu đang chờ device
        elif self.context.last_question == 'device':
            device_type = None
            for name, dtype in self.device_names.items():
                if name in message:
                    device_type = dtype
                    break
            
            if device_type:
                action = self.context.pending_action
                self.context.pending_device = device_type
                self.context.last_question = 'location'
                device_vn = "đèn" if device_type == 'light' else "điều hòa"
                return f"🤔 Bạn muốn điều khiển {device_vn} ở phòng nào? (phòng khách, phòng ngủ, phòng tắm)"
        
        # Nếu đang chờ action
        elif self.context.last_question == 'action':
            action = None
            if any(word in message for word in ['bật', 'bat', 'mở', 'mo', 'on', 'có', 'co']):
                action = True
            elif any(word in message for word in ['tắt', 'tat', 'off', 'không', 'khong']):
                action = False
            
            if action is not None:
                device_type = self.context.pending_device
                location = self.context.pending_location
                self.context.clear()
                return self._execute_device_command(device_type, location, action)
        
        return None  # Không xử lý được trong context

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
        if self.mqtt:
            success = self.mqtt.send_command(device_type, location, action)
            if success:
                status = "bật" if action else "tắt"
                location_vn = self._get_location_vietnamese(location)
                device_vn = "Đèn" if device_type == 'light' else "Điều hòa"
                return f"✅ Đã {status} {device_vn} {location_vn}!"
            else:
                return "❌ Không thể gửi lệnh. Vui lòng kiểm tra kết nối!"
        
        return "❌ MQTT chưa được kết nối!"

    def _generate_default_response(self, user_message: str) -> str:
        """Tạo câu trả lời mặc định"""
        responses = [
            "🤔 Tôi chưa hiểu ý bạn. Bạn có thể nói rõ hơn không?",
            "💡 Gợi ý: Hãy thử nói 'Bật đèn phòng khách' hoặc 'Nhiệt độ bao nhiêu?'",
            "🏠 Tôi có thể giúp bạn điều khiển đèn, điều hòa, và xem cảm biến. Hãy thử nhé!",
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
