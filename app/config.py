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
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

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
