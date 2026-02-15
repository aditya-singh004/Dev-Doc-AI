"""
Text cleaning utilities for processing Slack messages.
"""

import re
from typing import Optional


def clean_slack_message(text: str) -> str:
    """
    Clean and preprocess Slack message text.
    
    Removes:
    - User mentions (<@U12345>)
    - Channel mentions (<#C12345|channel-name>)
    - Emoji codes (:emoji_name:)
    - URLs (optional, keeps them by default)
    - Extra whitespace
    - Bot mentions
    
    Args:
        text: Raw Slack message text
        
    Returns:
        Cleaned text suitable for query processing
    """
    if not text:
        return ""
    
    # Remove user mentions (<@U12345678>)
    text = re.sub(r'<@[A-Z0-9]+>', '', text)
    
    # Remove channel mentions (<#C12345678|channel-name>)
    text = re.sub(r'<#[A-Z0-9]+\|[^>]+>', '', text)
    text = re.sub(r'<#[A-Z0-9]+>', '', text)
    
    # Remove emoji codes (:emoji_name:)
    text = re.sub(r':[a-zA-Z0-9_+-]+:', '', text)
    
    # Remove Slack special links but keep the text
    # Format: <URL|display_text> -> display_text
    text = re.sub(r'<([^|>]+)\|([^>]+)>', r'\2', text)
    
    # Remove bare URLs in angle brackets
    text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_code_blocks(text: str) -> tuple[str, list[str]]:
    """
    Extract code blocks from message text.
    
    Args:
        text: Message text potentially containing code blocks
        
    Returns:
        Tuple of (text without code blocks, list of code blocks)
    """
    code_blocks = []
    
    # Match triple backtick code blocks
    pattern = r'```(?:\w+)?\n?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    code_blocks.extend(matches)
    
    # Remove code blocks from text
    text_without_code = re.sub(pattern, '[CODE_BLOCK]', text, flags=re.DOTALL)
    
    # Match single backtick inline code
    inline_pattern = r'`([^`]+)`'
    inline_matches = re.findall(inline_pattern, text_without_code)
    code_blocks.extend(inline_matches)
    
    return text_without_code, code_blocks


def is_question(text: str) -> bool:
    """
    Determine if the text is likely a question.
    
    Args:
        text: Cleaned message text
        
    Returns:
        True if text appears to be a question
    """
    question_indicators = [
        '?',
        'how',
        'what',
        'why',
        'when',
        'where',
        'which',
        'who',
        'can i',
        'could you',
        'is it',
        'are there',
        'does',
        'do i',
        'help me',
        'explain',
        'tell me'
    ]
    
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in question_indicators)


def truncate_text(text: str, max_length: int = 4000) -> str:
    """
    Truncate text to maximum length while preserving word boundaries.
    
    Args:
        text: Text to truncate
        max_length: Maximum character length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:
        truncated = truncated[:last_space]
    
    return truncated + "..."
