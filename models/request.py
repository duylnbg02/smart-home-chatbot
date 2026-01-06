"""
Pydantic models for API requests
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class ChatMessage(BaseModel):
    """
    Chat message request model
    """
    message: str = Field(..., min_length=1, max_length=1000, description="User message")
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")

class ConversationHistory(BaseModel):
    """
    Conversation history model
    """
    user_id: str
    session_id: str
    messages: List[dict] = Field(default_factory=list)

class IntentRequest(BaseModel):
    """
    Intent detection request
    """
    text: str = Field(..., min_length=1, description="Text to detect intent from")

class EntityExtractionRequest(BaseModel):
    """
    Entity extraction request
    """
    text: str = Field(..., min_length=1, description="Text to extract entities from")
