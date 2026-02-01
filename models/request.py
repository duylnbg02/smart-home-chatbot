from pydantic import BaseModel, Field
from typing import Optional, List

class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="User message")
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")

class ConversationHistory(BaseModel):
    user_id: str
    session_id: str
    messages: List[dict] = Field(default_factory=list)

class IntentRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to detect intent from")

class EntityExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to extract entities from")
