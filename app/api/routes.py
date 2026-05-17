"""
API routes for the documentation chatbot.
"""

import secrets
import time
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from app.models import (
    QueryRequest,
    QueryResponse,
    HealthResponse,
    ErrorResponse,
    SlackEventPayload,
    AgentRunRequest,
    AgentRunResponse,
)
from app.config import settings
from app.utils.logger import logger
from app.utils.text_cleaner import clean_slack_message
from app.services.rag_service import RAGService
from app.services.vector_store import use_pinecone
from app.services.llm_service import LLMService
from app.services.memory_service import conversation_memory
from app.services.agent_service import DocumentationAgentService
from app.services.agent_working_memory import agent_working_memory
from app.utils.agent_rate_limit import agent_rate_limiter

router = APIRouter()

# Service instances
rag_service = RAGService()
documentation_agent = DocumentationAgentService(rag_service)
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
        index_loaded=rag_service.is_ready,
        vector_store="pinecone" if use_pinecone() else "local",
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


def _clamp_agent_limits(
    max_iterations: Optional[int], max_tool_calls: Optional[int]
) -> Tuple[int, int]:
    mi = max_iterations if max_iterations is not None else settings.AGENT_MAX_ITERATIONS
    mt = max_tool_calls if max_tool_calls is not None else settings.AGENT_MAX_TOOL_CALLS
    mi = min(max(mi, 1), 50)
    mt = min(max(mt, 0), 100)
    return mi, mt


def _client_ip(http_request: Request) -> str:
    forwarded = http_request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if http_request.client:
        return http_request.client.host
    return "unknown"


def _agent_working_memory_key(req: AgentRunRequest, http_request: Request) -> str:
    if req.agent_session_id and req.agent_session_id.strip():
        return f"session:{req.agent_session_id.strip()}"
    if req.user_id and req.user_id.strip():
        return f"user:{req.user_id.strip()}"
    return f"ip:{_client_ip(http_request)}"


@router.post(
    "/agent/run",
    response_model=AgentRunResponse,
    responses={500: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Agent"],
)
async def run_documentation_agent(
    request: AgentRunRequest, http_request: Request
):
    """
    Autonomous agent with tools: ``search_docs``, ``update_working_memory``, optional
    allowlisted ``http_get``, optional ``slack_post_message`` (gated by approval secret).
    Traces are persisted under ``AGENT_TRACE_DIR`` when enabled. Requires ``OPENAI_API_KEY``.
    """
    start_time = time.time()
    cleaned = clean_slack_message(request.query)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Empty query after cleaning")

    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Agent mode requires OPENAI_API_KEY in the environment.",
        )

    rate_key = (
        request.user_id.strip()
        if request.user_id and request.user_id.strip()
        else _client_ip(http_request)
    )
    try:
        agent_rate_limiter.check(f"agent:{rate_key}")
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    max_iter, max_tools = _clamp_agent_limits(
        request.max_iterations, request.max_tool_calls
    )

    wm_key = _agent_working_memory_key(request, http_request)
    sec = settings.AGENT_APPROVAL_SECRET or ""
    tok = request.approval_secret or ""
    sensitive_ok = False
    if request.allow_sensitive_tools and sec and tok and len(tok) == len(sec):
        sensitive_ok = secrets.compare_digest(tok, sec)

    history = None
    if request.user_id and settings.ENABLE_MEMORY:
        history = conversation_memory.get_formatted_history(request.user_id)

    try:
        answer, sources, trace_id, iterations_used, tools_used, steps = (
            await documentation_agent.run(
                cleaned,
                working_memory_key=wm_key,
                conversation_history=history,
                max_iterations=max_iter,
                max_tool_calls=max_tools,
                include_step_logs=request.include_steps,
                sensitive_tools_approved=sensitive_ok,
            )
        )
    except RuntimeError as e:
        logger.error("Agent runtime error: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Agent error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    if request.user_id and settings.ENABLE_MEMORY:
        conversation_memory.add_message(request.user_id, "user", cleaned)
        conversation_memory.add_message(request.user_id, "assistant", answer)

    elapsed_ms = (time.time() - start_time) * 1000
    return AgentRunResponse(
        answer=answer,
        query=cleaned,
        sources=sources if request.include_sources else [],
        trace_id=trace_id,
        iterations=iterations_used,
        tool_calls=tools_used,
        timestamp=datetime.utcnow(),
        processing_time_ms=elapsed_ms,
        steps=steps if request.include_steps else None,
    )


@router.delete("/agent/working-memory", tags=["Agent"])
async def clear_agent_working_memory(
    agent_session_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """Clear agent working memory (goals/subtasks/findings) for a session or user key."""
    if agent_session_id and agent_session_id.strip():
        key = f"session:{agent_session_id.strip()}"
    elif user_id and user_id.strip():
        key = f"user:{user_id.strip()}"
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide query param agent_session_id or user_id",
        )
    agent_working_memory.clear(key)
    return {"status": "cleared", "working_memory_key": key}


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
            # URL verification. Message processing is done by n8n calling
            # /api/v1/agent/run or /api/v1/query (see n8n/workflow.json).
            
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
        "agent_working_memory": agent_working_memory.stats(),
        "config": {
            "llm_provider": settings.LLM_PROVIDER,
            "vector_store": settings.VECTOR_STORE,
            "pinecone_index": settings.PINECONE_INDEX_NAME
            if settings.PINECONE_API_KEY
            else None,
            "chunk_size": settings.CHUNK_SIZE,
            "top_k": settings.TOP_K_RESULTS,
            "agent_max_iterations": settings.AGENT_MAX_ITERATIONS,
            "agent_max_tool_calls": settings.AGENT_MAX_TOOL_CALLS,
            "agent_rate_limit_per_minute": settings.AGENT_RATE_LIMIT_PER_MINUTE,
            "agent_trace_persist": settings.AGENT_TRACE_PERSIST,
            "agent_trace_dir": settings.AGENT_TRACE_DIR,
            "agent_http_allowlist_configured": bool(
                (settings.AGENT_HTTP_ALLOWLIST_HOSTS or "").strip()
            ),
            "agent_slack_post_configured": bool(
                settings.SLACK_BOT_TOKEN
                and (settings.SLACK_POST_CHANNEL_ALLOWLIST or "").strip()
            ),
            "agent_approval_secret_configured": bool(settings.AGENT_APPROVAL_SECRET),
        }
    }
