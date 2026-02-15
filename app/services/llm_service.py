"""
LLM Service for generating responses using OpenAI or Gemini.
"""

from typing import Optional, List
from app.config import settings
from app.utils.logger import logger


class LLMService:
    """Service for interacting with LLM providers."""
    
    def __init__(self):
        """Initialize LLM service based on configured provider."""
        self.provider = settings.LLM_PROVIDER
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the appropriate LLM client."""
        if self.provider == "openai":
            self._initialize_openai()
        elif self.provider == "gemini":
            self._initialize_gemini()
        elif self.provider == "local":
            logger.info("Using local mode - responses will be based on retrieved context only")
            self._client = "local"
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _initialize_openai(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            
            if not settings.OPENAI_API_KEY:
                logger.warning("OpenAI API key not configured")
                return
            
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized successfully")
        except ImportError:
            logger.error("OpenAI package not installed")
            raise
    
    def _initialize_gemini(self):
        """Initialize Google Gemini client."""
        try:
            import google.generativeai as genai
            
            if not settings.GOOGLE_API_KEY:
                logger.warning("Google API key not configured")
                return
            
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            self._client = genai.GenerativeModel(settings.GEMINI_MODEL)
            logger.info("Gemini client initialized successfully")
        except ImportError:
            logger.error("Google GenerativeAI package not installed")
            raise
    
    async def generate_response(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[dict]] = None
    ) -> str:
        """
        Generate a response using the configured LLM.
        
        Args:
            query: User's question
            context: Retrieved documentation context
            conversation_history: Optional conversation history for context
            
        Returns:
            Generated response string
        """
        if self.provider == "openai":
            return await self._generate_openai(query, context, conversation_history)
        elif self.provider == "gemini":
            return await self._generate_gemini(query, context, conversation_history)
        elif self.provider == "local":
            return await self._generate_local(query, context)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _generate_local(self, query: str, context: str) -> str:
        """Generate response using retrieved context only (no LLM API)."""
        if not context or context == "No relevant documentation found for this query.":
            return "I couldn't find relevant information in the documentation for your query."
        
        return f"""Based on the documentation, here's what I found:

{context}

---
*Note: This response is from retrieved documentation. For AI-generated answers, configure an OpenAI or Gemini API key.*"""
    
    async def _generate_openai(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[dict]] = None
    ) -> str:
        """Generate response using OpenAI."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(query, context)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if available
        if conversation_history:
            for msg in conversation_history[-settings.MAX_CONVERSATION_HISTORY:]:
                messages.append(msg)
        
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            response = self._client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def _generate_gemini(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[dict]] = None
    ) -> str:
        """Generate response using Google Gemini."""
        prompt = f"""You are a helpful developer documentation assistant. 
Answer questions based on the provided documentation context.
Be concise, accurate, and developer-friendly.
If the answer is not in the context, say so clearly.

Documentation Context:
{context}

Question: {query}

Answer:"""
        
        try:
            response = self._client.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM."""
        return """You are an expert developer documentation assistant. Your role is to:

1. Answer technical questions accurately based on the provided documentation context
2. Be concise and developer-friendly in your responses
3. Include code examples when relevant
4. If the answer is not found in the context, clearly state that
5. Never make up information - only use what's in the documentation
6. Format responses with proper markdown for readability

Always prioritize accuracy over completeness. If you're unsure, say so."""
    
    def _build_user_prompt(self, query: str, context: str) -> str:
        """Build the user prompt with context."""
        return f"""Based on the following documentation context, please answer the question.

Documentation Context:
---
{context}
---

Question: {query}

Please provide a clear, accurate answer based only on the documentation above."""
