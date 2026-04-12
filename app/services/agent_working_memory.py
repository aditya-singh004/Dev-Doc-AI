"""
Per-session working memory for the agent (separate from chat transcript memory).
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.logger import logger

# Sentinel: field omitted from tool call (do not overwrite stored value)
WORKING_MEMORY_UNSET = object()


class AgentWorkingMemoryStore:
    """In-memory goal/subtask/finding store keyed by agent memory key (session/user/ip)."""

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        self._ts: Dict[str, datetime] = {}
        self._lock = threading.Lock()

    def _ttl(self) -> timedelta:
        return timedelta(hours=settings.AGENT_WORKING_MEMORY_TTL_HOURS)

    def _purge_if_expired(self, memory_key: str) -> None:
        last = self._ts.get(memory_key)
        if last and datetime.utcnow() - last > self._ttl():
            self._data.pop(memory_key, None)
            self._ts.pop(memory_key, None)
            logger.debug("Expired agent working memory for %s", memory_key)

    def get_snapshot(self, memory_key: str) -> Dict[str, Any]:
        with self._lock:
            self._purge_if_expired(memory_key)
            base = {"goal": None, "subtasks": [], "recent_findings": []}
            cur = self._data.get(memory_key)
            if not cur:
                return dict(base)
            return {
                "goal": cur.get("goal"),
                "subtasks": list(cur.get("subtasks") or [])[:20],
                "recent_findings": list(cur.get("recent_findings") or [])[-15:],
            }

    def update_from_tool(
        self,
        memory_key: str,
        *,
        goal: Any = WORKING_MEMORY_UNSET,
        subtasks: Any = WORKING_MEMORY_UNSET,
        note: Optional[str] = None,
    ) -> None:
        if not settings.AGENT_WORKING_MEMORY_ENABLED:
            return
        with self._lock:
            self._purge_if_expired(memory_key)
            cur = self._data.setdefault(
                memory_key,
                {"goal": None, "subtasks": [], "recent_findings": []},
            )
            if goal is not WORKING_MEMORY_UNSET:
                if goal is None:
                    cur["goal"] = None
                else:
                    g = str(goal).strip()
                    cur["goal"] = g[:2000] if g else None
            if subtasks is not WORKING_MEMORY_UNSET:
                if subtasks is None:
                    cur["subtasks"] = []
                else:
                    cleaned = [
                        s.strip()[:500]
                        for s in subtasks
                        if s and str(s).strip()
                    ][:20]
                    cur["subtasks"] = cleaned
            if note:
                note = note.strip()[:500]
                if note:
                    rf = cur.setdefault("recent_findings", [])
                    rf.append(note)
                    cur["recent_findings"] = rf[-15:]
            self._ts[memory_key] = datetime.utcnow()

    def append_finding(self, memory_key: str, text: str) -> None:
        t = (text or "").strip()[:400]
        if t:
            self.update_from_tool(memory_key, note=t)

    def clear(self, memory_key: str) -> None:
        with self._lock:
            self._data.pop(memory_key, None)
            self._ts.pop(memory_key, None)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "sessions": len(self._data),
                "ttl_hours": settings.AGENT_WORKING_MEMORY_TTL_HOURS,
                "enabled": settings.AGENT_WORKING_MEMORY_ENABLED,
            }


agent_working_memory = AgentWorkingMemoryStore()
