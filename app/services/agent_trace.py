"""
Persist structured agent run traces to disk (JSON) for debugging and dashboards.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.logger import logger


def persist_agent_trace(trace_id: str, record: Dict[str, Any]) -> Optional[Path]:
    """
    Write trace JSON to AGENT_TRACE_DIR/{trace_id}.json.
    Returns path if written, else None.
    """
    if not settings.AGENT_TRACE_PERSIST:
        return None
    try:
        base = Path(settings.AGENT_TRACE_DIR)
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{trace_id}.json"
        payload = dict(record)
        payload.setdefault("trace_id", trace_id)
        payload.setdefault("persisted_at", datetime.utcnow().isoformat() + "Z")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("Agent trace persisted: %s", path)
        return path
    except Exception as e:
        logger.error("Failed to persist agent trace %s: %s", trace_id, e)
        return None


def merge_spans(spans: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Lightweight tree: single root span holding children for simple viewers."""
    return {
        "name": "agent.run",
        "children": spans,
    }
