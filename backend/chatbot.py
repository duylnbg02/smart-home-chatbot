class Chatbot:
    def __init__(self):
        self.knowledge_base = {
            'xin chào': 'Xin chào! 👋 Tôi có thể giúp bạn gì?',
            'hello': 'Hello! 👋 How can I help you?',
            'ai là cái tên của bạn': 'Tôi là một AI Chatbot được tạo ra để hỗ trợ bạn!',
            'bạn là ai': 'Tôi là một AI Chatbot thông minh!',
            'cảm ơn': 'Không có gì! 😊 Nếu cần giúp đỡ gì khác thì cứ hỏi tôi!',
            'cảm ơn bạn': 'Vui lòng! 😊',
            'tạm biệt': 'Tạm biệt! 👋 Rất vui được gặp bạn!',
            'bye': 'Goodbye! 👋',
            'hôm nay thế nào': '😊 Tôi là một chatbot, nên mỗi ngày đều tốt! Còn bạn thì sao?',
            'bạn khỏe không': 'Cảm ơn bạn! Tôi khỏe! 😊 Bạn thì sao?',
        }

    def get_response(self, user_message: str) -> str:
        """
        Lấy câu trả lời dựa trên tin nhắn của người dùng
        """
        message_lower = user_message.lower().strip()
        
        # Tìm kiếm trong knowledge base
        for key, response in self.knowledge_base.items():
            if key in message_lower:
                return response
        
        # Nếu không tìm thấy, trả về câu trả lời mặc định
        return self._generate_default_response(user_message)

    def _generate_default_response(self, user_message: str) -> str:
        """
        Tạo câu trả lời mặc định
        """
        responses = [
            f"Đó là một câu hỏi thú vị! Bạn có thể giải thích thêm về '{user_message}' không?",
            f"Tôi chưa hiểu rõ về '{user_message}'. Bạn có thể hỏi cách khác được không?",
            "Đó là một chủ đề thú vị! 🤔 Tôi vẫn đang học về nó.",
            "Hmm, tôi cần thêm thông tin để trả lời câu hỏi này. 😊",
        ]
        
        import random
        return random.choice(responses)
