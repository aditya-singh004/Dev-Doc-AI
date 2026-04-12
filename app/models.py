"""
Pydantic models for request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
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


class AgentRunRequest(BaseModel):
    """Request for autonomous agent (OpenAI tool loop + tools)."""

    query: str = Field(..., description="User goal or question")
    user_id: Optional[str] = Field(None, description="Optional id for conversation memory")
    agent_session_id: Optional[str] = Field(
        None,
        description="Stable id for agent working memory (goals/subtasks). "
        "If unset, key is derived from user_id or client IP.",
    )
    channel_id: Optional[str] = Field(None, description="Optional channel id (metadata only)")
    max_iterations: Optional[int] = Field(
        None,
        ge=1,
        le=50,
        description="LLM round-trips (default from AGENT_MAX_ITERATIONS)",
    )
    max_tool_calls: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Budget for search_docs + http_get + slack_post_message per run",
    )
    include_sources: bool = Field(True, description="Return deduplicated source snippets")
    include_steps: bool = Field(
        False,
        description="If true, include step logs (LLM rounds and tool previews)",
    )
    allow_sensitive_tools: bool = Field(
        False,
        description="Must be true with a valid approval_secret to run slack_post_message",
    )
    approval_secret: Optional[str] = Field(
        None,
        description="Must match server AGENT_APPROVAL_SECRET when allow_sensitive_tools is true",
    )


class AgentRunResponse(BaseModel):
    """Response from the autonomous agent run."""

    answer: str = Field(..., description="Final assistant message")
    query: str = Field(..., description="User message after cleaning")
    sources: List[SourceDocument] = Field(default_factory=list)
    trace_id: str = Field(..., description="Correlation id for logs")
    iterations: int = Field(..., description="Number of LLM completions used")
    tool_calls: int = Field(
        ...,
        description="Budget tools used: search_docs + http_get + slack_post_message",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[float] = None
    steps: Optional[List[Dict[str, Any]]] = Field(
        None, description="Present when include_steps was true"
    )
