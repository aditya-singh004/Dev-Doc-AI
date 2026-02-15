"""
API routes for the documentation chatbot.
"""

import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from app.models import (
    QueryRequest,
    QueryResponse,
    HealthResponse,
    ErrorResponse,
    SlackEventPayload
)
from app.config import settings
from app.utils.logger import logger
from app.utils.text_cleaner import clean_slack_message
from app.services.rag_service import RAGService
from app.services.llm_service import LLMService
from app.services.memory_service import conversation_memory

router = APIRouter()

# Service instances
rag_service = RAGService()
llm_service = None


def get_llm_service() -> LLMService:
    """Dependency to get LLM service instance."""
    global llm_service
    if llm_service is None:
        llm_service = LLMService()
    return llm_service


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and index availability.
    """
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        timestamp=datetime.utcnow(),
        index_loaded=rag_service.is_ready
    )


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={500: {"model": ErrorResponse}},
    tags=["Query"]
)
async def query_documentation(
    request: QueryRequest,
    llm: LLMService = Depends(get_llm_service)
):
    """
    Query the documentation and get an AI-generated response.
    
    This endpoint:
    1. Cleans the incoming query
    2. Retrieves relevant documentation
    3. Generates an AI response
    4. Returns the response with sources
    """
    start_time = time.time()
    
    try:
        # Clean the query
        cleaned_query = clean_slack_message(request.query)
        
        if not cleaned_query:
            raise HTTPException(status_code=400, detail="Empty query after cleaning")
        
        logger.info(f"Processing query: {cleaned_query[:100]}...")
        
        # Get conversation history if user_id provided
        conversation_history = None
        if request.user_id and settings.ENABLE_MEMORY:
            conversation_history = conversation_memory.get_formatted_history(request.user_id)
        
        # Retrieve relevant documentation
        context, sources = await rag_service.retrieve(cleaned_query)
        
        if not context:
            logger.warning("No relevant documentation found")
            context = "No relevant documentation found for this query."
        
        # Generate response
        answer = await llm.generate_response(
            query=cleaned_query,
            context=context,
            conversation_history=conversation_history
        )
        
        # Store in conversation memory
        if request.user_id and settings.ENABLE_MEMORY:
            conversation_memory.add_message(request.user_id, "user", cleaned_query)
            conversation_memory.add_message(request.user_id, "assistant", answer)
        
        processing_time = (time.time() - start_time) * 1000
        
        response = QueryResponse(
            answer=answer,
            sources=sources if request.include_sources else [],
            query=cleaned_query,
            timestamp=datetime.utcnow(),
            processing_time_ms=processing_time
        )
        
        logger.info(f"Query processed in {processing_time:.2f}ms")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slack/events", tags=["Slack"])
async def handle_slack_events(payload: SlackEventPayload):
    """
    Handle Slack event webhooks.
    
    This endpoint handles:
    - URL verification challenges
    - Message events (for direct Slack integration)
    """
    # Handle URL verification challenge
    if payload.type == "url_verification":
        return {"challenge": payload.challenge}
    
    # Handle event callbacks
    if payload.type == "event_callback" and payload.event:
        event = payload.event
        event_type = event.get("type")
        
        if event_type == "message" and "subtype" not in event:
            # This is a regular message
            text = event.get("text", "")
            user = event.get("user", "")
            channel = event.get("channel", "")
            
            logger.info(f"Received Slack message from {user} in {channel}")
            
            # Note: For n8n integration, this endpoint mainly handles
            # URL verification. The actual message processing happens
            # through the /query endpoint called by n8n.
            
            return {"status": "received"}
    
    return {"status": "ok"}


@router.delete("/memory/{user_id}", tags=["Memory"])
async def clear_user_memory(user_id: str):
    """
    Clear conversation memory for a specific user.
    
    Args:
        user_id: The user's unique identifier
    """
    conversation_memory.clear_history(user_id)
    return {"status": "cleared", "user_id": user_id}


@router.get("/stats", tags=["Stats"])
async def get_stats():
    """
    Get service statistics.
    
    Returns information about:
    - Index status
    - Memory usage
    - Configuration
    """
    return {
        "index": rag_service.get_index_stats(),
        "memory": conversation_memory.get_stats(),
        "config": {
            "llm_provider": settings.LLM_PROVIDER,
            "chunk_size": settings.CHUNK_SIZE,
            "top_k": settings.TOP_K_RESULTS
        }
    }
