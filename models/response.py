"""
Pydantic models for API responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class ChatResponse(BaseModel):
    """
    Chat response model
    """
    reply: str = Field(..., description="Bot reply")
    intent: Optional[str] = Field(None, description="Detected intent")
    entities: Optional[List[Dict]] = Field(None, description="Extracted entities")
    confidence: Optional[float] = Field(None, description="Response confidence score")

class ErrorResponse(BaseModel):
    """
    Error response model
    """
    error: str = Field(..., description="Error message")
    code: int = Field(default=400, description="Error code")

class HealthResponse(BaseModel):
    """
    Health check response
    """
    status: str = Field("running", description="Service status")
    version: Optional[str] = Field(None, description="API version")

class IntentResponse(BaseModel):
    """
    Intent detection response
    """
    intent: str
    confidence: float = Field(..., ge=0.0, le=1.0)

class EntityExtractionResponse(BaseModel):
    """
    Entity extraction response
    """
    entities: List[Dict[str, any]] = Field(default_factory=list)
    text: str
