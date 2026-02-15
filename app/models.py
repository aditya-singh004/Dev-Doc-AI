"""
Pydantic models for request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class QueryRequest(BaseModel):
    """Request model for documentation queries."""
    
    query: str = Field(..., description="The user's question or query")
    user_id: Optional[str] = Field(None, description="Slack user ID for conversation tracking")
    channel_id: Optional[str] = Field(None, description="Slack channel ID")
    include_sources: bool = Field(True, description="Whether to include source references")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How do I authenticate with the API?",
                "user_id": "U12345678",
                "channel_id": "C12345678",
                "include_sources": True
            }
        }


class SourceDocument(BaseModel):
    """Model for source document references."""
    
    content: str = Field(..., description="Relevant content snippet")
    source: str = Field(..., description="Source file or document name")
    score: Optional[float] = Field(None, description="Relevance score")


class QueryResponse(BaseModel):
    """Response model for documentation queries."""
    
    answer: str = Field(..., description="AI-generated answer")
    sources: List[SourceDocument] = Field(default_factory=list, description="Source documents used")
    query: str = Field(..., description="Original query")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "To authenticate with the API, you need to...",
                "sources": [
                    {
                        "content": "Authentication requires an API key...",
                        "source": "auth.md",
                        "score": 0.95
                    }
                ],
                "query": "How do I authenticate with the API?",
                "timestamp": "2024-01-15T10:30:00Z",
                "processing_time_ms": 1250.5
            }
        }


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    index_loaded: bool = Field(..., description="Whether documentation index is loaded")


class SlackMessage(BaseModel):
    """Model for incoming Slack messages."""
    
    text: str = Field(..., description="Message text")
    user: str = Field(..., description="User ID")
    channel: str = Field(..., description="Channel ID")
    ts: str = Field(..., description="Message timestamp")
    
    
class SlackEventPayload(BaseModel):
    """Model for Slack event webhook payload."""
    
    type: str
    challenge: Optional[str] = None
    event: Optional[dict] = None
    token: Optional[str] = None
    team_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
