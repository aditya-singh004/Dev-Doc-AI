"""
Configuration settings for the AI Documentation Chatbot.
Uses environment variables for sensitive data.
"""

import os
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Settings
    APP_NAME: str = "AI Documentation Chatbot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # OpenAI Settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    
    # Google Gemini Settings (alternative)
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-pro"
    
    # LLM Provider Selection
    LLM_PROVIDER: str = "local"
    
    # LlamaIndex Settings
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K_RESULTS: int = 5
    
    # Vector store: local (disk) | pinecone | auto (pinecone if API key + index name set)
    VECTOR_STORE: str = "local"
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_INDEX_NAME: str = "dda-docs"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    PINECONE_DIMENSION: Optional[int] = None
    PINECONE_METRIC: str = "cosine"
    PINECONE_NAMESPACE: str = ""
    PINECONE_CREATE_INDEX: bool = True

    # Documentation Settings
    DOCS_DIRECTORY: str = "./docs"
    INDEX_STORAGE_PATH: str = "./storage/index"
    AUTO_INGEST_ON_STARTUP: bool = True
    
    # Slack Settings
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None
    
    # Conversation Memory
    ENABLE_MEMORY: bool = True
    MAX_CONVERSATION_HISTORY: int = 10

    # Autonomous agent (/api/v1/agent/run) — uses OpenAI tool calling; requires OPENAI_API_KEY
    AGENT_MAX_ITERATIONS: int = 10
    # Budget for "expensive" tools: search_docs, http_get, slack_post_message
    AGENT_MAX_TOOL_CALLS: int = 20
    AGENT_MAX_WORKING_MEMORY_UPDATES: int = 10
    AGENT_OPENAI_MODEL: Optional[str] = None  # defaults to OPENAI_MODEL if unset
    AGENT_TOOL_TIMEOUT_SEC: float = 30.0
    AGENT_RATE_LIMIT_PER_MINUTE: int = 30
    AGENT_TRACE_PERSIST: bool = True
    AGENT_TRACE_DIR: str = "./logs/agent_traces"
    # Required with allow_sensitive_tools + matching approval_secret to run slack_post_message
    AGENT_APPROVAL_SECRET: Optional[str] = None
    # Comma-separated hostnames (e.g. api.example.com,localhost). Empty disables http_get tool.
    AGENT_HTTP_ALLOWLIST_HOSTS: str = ""
    AGENT_HTTP_MAX_BYTES: int = 524288
    # Comma-separated Slack channel IDs allowed for slack_post_message (e.g. C0123...)
    SLACK_POST_CHANNEL_ALLOWLIST: str = ""
    AGENT_WORKING_MEMORY_ENABLED: bool = True
    AGENT_WORKING_MEMORY_TTL_HOURS: int = 2

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @field_validator("PINECONE_DIMENSION", mode="before")
    @classmethod
    def parse_pinecone_dimension(cls, value):
        if value in (None, "", "0"):
            return None
        return int(value)

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        """Accept common non-boolean DEBUG values used in deployments."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value


# Global settings instance
settings = Settings()
