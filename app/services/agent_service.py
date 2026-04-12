"""
Autonomous agent: OpenAI tool-calling loop with docs search, allowlisted HTTP,
approval-gated Slack post, and working memory.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import time
import uuid
from typing import Any, Coroutine, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.models import SourceDocument
from app.services.agent_trace import merge_spans, persist_agent_trace
from app.services.agent_working_memory import (
    WORKING_MEMORY_UNSET,
    agent_working_memory,
)
from app.services.rag_service import RAGService
from app.utils.logger import logger

SEARCH_DOCS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_docs",
        "description": (
            "Search indexed developer documentation for facts, APIs, setup steps, "
            "and examples. Prefer this for anything that might be in your docs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Focused search query or keywords.",
                }
            },
            "required": ["query"],
        },
    },
}

HTTP_GET_TOOL = {
    "type": "function",
    "function": {
        "name": "http_get",
        "description": (
            "Fetch a public HTTP(S) URL (GET only). Only hosts listed in the "
            "server allowlist are permitted. Use for internal APIs or trusted docs endpoints."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Absolute http(s) URL to fetch.",
                }
            },
            "required": ["url"],
        },
    },
}

SLACK_POST_TOOL = {
    "type": "function",
    "function": {
        "name": "slack_post_message",
        "description": (
            "Post a short message to an allowlisted Slack channel. Requires human approval "
            "on the API request (allow_sensitive_tools + approval_secret). Use sparingly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "Slack channel ID (e.g. C01234...).",
                },
                "text": {
                    "type": "string",
                    "description": "Message text (plain).",
                },
            },
            "required": ["channel_id", "text"],
        },
    },
}

UPDATE_WORKING_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "update_working_memory",
        "description": (
            "Update your working plan: current goal, subtasks, or a brief note. "
            "Use to track multi-step work; this is separate from user chat history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Single sentence describing the current objective.",
                },
                "subtasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered subtasks still to do.",
                },
                "note": {
                    "type": "string",
                    "description": "Short note or finding to remember for this session.",
                },
            },
        },
    },
}

AGENT_SYSTEM_PROMPT_BASE = """You are an autonomous assistant with tools.

Use search_docs for anything that may be in local documentation.
Use http_get only for allowlisted hosts when an HTTP fetch is truly needed.
Use slack_post_message only when the user explicitly wants a Slack post and the channel is correct; it requires human approval on the API side.
Use update_working_memory to keep track of goals, subtasks, and short notes across steps.

Rules:
- Prefer tools over guessing when facts matter.
- After enough evidence, reply with a clear final message (no more tool calls).
- Never invent documentation citations; only cite what tools returned."""


def _http_host_allowlist() -> Set[str]:
    raw = settings.AGENT_HTTP_ALLOWLIST_HOSTS or ""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def _slack_channel_allowlist() -> Set[str]:
    raw = settings.SLACK_POST_CHANNEL_ALLOWLIST or ""
    return {p.strip() for p in raw.split(",") if p.strip()}


def _dedupe_sources(sources: List[SourceDocument]) -> List[SourceDocument]:
    seen: set = set()
    out: List[SourceDocument] = []
    for s in sources:
        key = (s.source, (s.content or "")[:200])
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _format_working_memory_block(snapshot: Dict[str, Any]) -> str:
    if not settings.AGENT_WORKING_MEMORY_ENABLED:
        return ""
    lines = ["## Working memory (session; not user-visible unless you reveal it)"]
    g = snapshot.get("goal")
    if g:
        lines.append(f"- Goal: {g}")
    st = snapshot.get("subtasks") or []
    if st:
        lines.append("- Subtasks:")
        for i, t in enumerate(st, 1):
            lines.append(f"  {i}. {t}")
    rf = snapshot.get("recent_findings") or []
    if rf:
        lines.append("- Recent findings:")
        for t in rf[-8:]:
            lines.append(f"  - {t}")
    if len(lines) == 1:
        lines.append("- (empty)")
    return "\n".join(lines)


def _build_openai_tools() -> List[dict]:
    tools: List[dict] = [SEARCH_DOCS_TOOL, UPDATE_WORKING_MEMORY_TOOL]
    if _http_host_allowlist():
        tools.append(HTTP_GET_TOOL)
    if settings.SLACK_BOT_TOKEN and _slack_channel_allowlist():
        tools.append(SLACK_POST_TOOL)
    return tools


def _validate_http_url(url: str, allow: Set[str]) -> Optional[str]:
    if not allow:
        return "http_get is disabled (empty AGENT_HTTP_ALLOWLIST_HOSTS)."
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return "Invalid URL."
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if not host:
        return "URL must include a hostname."
    if scheme not in ("http", "https"):
        return "Only http and https are allowed."
    if scheme == "http" and host not in ("localhost", "127.0.0.1"):
        return "Only https is allowed except for localhost."
    if host not in allow:
        return f"Host not allowlisted: {host}"
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private and host not in allow:
            return "Private IP hosts must be explicitly allowlisted by hostname/IP."
    except ValueError:
        pass
    return None


class DocumentationAgentService:
    """Bounded tool loop with working memory, timeouts, spans, and trace persistence."""

    def __init__(self, rag: RAGService):
        self._rag = rag

    def _client(self):
        if not settings.OPENAI_API_KEY:
            return None
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def _tool_http_get(self, url: str) -> str:
        allow = _http_host_allowlist()
        err = _validate_http_url(url, allow)
        if err:
            return err
        timeout = httpx.Timeout(settings.AGENT_TOOL_TIMEOUT_SEC)
        max_b = settings.AGENT_HTTP_MAX_BYTES
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "DDA-Agent/1.0"},
            )
        ctype = resp.headers.get("content-type", "")
        body = resp.content[:max_b]
        if len(resp.content) > max_b:
            tail = f"\n... truncated to {max_b} bytes"
        else:
            tail = ""
        if "application/json" in ctype.lower():
            try:
                text = json.dumps(json.loads(body.decode("utf-8", errors="replace")), indent=2)
            except Exception:
                text = body.decode("utf-8", errors="replace")
        else:
            text = body.decode("utf-8", errors="replace")
        return f"HTTP {resp.status_code}\nContent-Type: {ctype}\n\n{text}{tail}"

    async def _tool_slack_post_execute(self, channel_id: str, text: str) -> str:
        """Post to Slack; caller must enforce approval gate and allowlists."""
        cid = (channel_id or "").strip()
        ch_allow = _slack_channel_allowlist()
        if not settings.SLACK_BOT_TOKEN:
            return "Slack is not configured (SLACK_BOT_TOKEN)."
        if not ch_allow:
            return "No Slack channels allowlisted (SLACK_POST_CHANNEL_ALLOWLIST)."
        if cid not in ch_allow:
            return "Channel not allowlisted for slack_post_message."
        payload = {"channel": cid, "text": (text or "")[:4000]}
        timeout = httpx.Timeout(settings.AGENT_TOOL_TIMEOUT_SEC)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json=payload,
            )
        try:
            data = resp.json()
        except Exception:
            return f"Slack response not JSON: {resp.text[:500]}"
        if not data.get("ok"):
            return f"Slack API error: {data.get('error', resp.text[:500])}"
        return f"Posted to Slack channel {cid} (ts={data.get('ts')})."

    def _tool_update_working_memory(
        self,
        memory_key: str,
        args: dict,
        wm_updates_used: int,
    ) -> Tuple[str, int]:
        max_wm = settings.AGENT_MAX_WORKING_MEMORY_UPDATES
        if wm_updates_used >= max_wm:
            return (
                f"update_working_memory limit reached ({max_wm} updates per run).",
                wm_updates_used,
            )
        has_goal = "goal" in args
        has_subtasks = "subtasks" in args
        has_note = "note" in args
        if not has_goal and not has_subtasks and not has_note:
            return "Provide at least one of goal, subtasks, or note.", wm_updates_used

        goal_kw: Any = WORKING_MEMORY_UNSET
        if has_goal:
            gv = args.get("goal")
            if gv is None:
                goal_kw = None
            else:
                g = str(gv).strip()
                goal_kw = g[:2000] if g else None

        sub_kw: Any = WORKING_MEMORY_UNSET
        if has_subtasks:
            st = args.get("subtasks")
            if st is None:
                sub_kw = None
            elif not isinstance(st, list):
                return "subtasks must be a list of strings.", wm_updates_used
            else:
                sub_kw = [str(s).strip()[:500] for s in st if s and str(s).strip()][
                    :20
                ]

        n: Optional[str] = None
        if has_note:
            nv = args.get("note")
            if nv is not None:
                n = str(nv).strip()[:500] or None

        agent_working_memory.update_from_tool(
            memory_key,
            goal=goal_kw,
            subtasks=sub_kw,
            note=n,
        )
        return "Working memory updated.", wm_updates_used + 1

    async def run(
        self,
        user_message: str,
        *,
        working_memory_key: str,
        conversation_history: Optional[List[dict]] = None,
        max_iterations: Optional[int] = None,
        max_tool_calls: Optional[int] = None,
        include_step_logs: bool = False,
        sensitive_tools_approved: bool = False,
    ) -> Tuple[
        str,
        List[SourceDocument],
        str,
        int,
        int,
        List[Dict[str, Any]],
    ]:
        client = self._client()
        if client is None:
            raise RuntimeError(
                "Agent mode requires OPENAI_API_KEY. Set it in the environment."
            )

        trace_id = str(uuid.uuid4())
        max_iter = max_iterations or settings.AGENT_MAX_ITERATIONS
        max_budget_tools = max_tool_calls or settings.AGENT_MAX_TOOL_CALLS
        model = settings.AGENT_OPENAI_MODEL or settings.OPENAI_MODEL
        tools = _build_openai_tools()

        wm_snapshot = agent_working_memory.get_snapshot(working_memory_key)
        system_content = (
            AGENT_SYSTEM_PROMPT_BASE + "\n\n" + _format_working_memory_block(wm_snapshot)
        )

        messages: List[dict] = [{"role": "system", "content": system_content}]
        if conversation_history:
            for msg in conversation_history[-(settings.MAX_CONVERSATION_HISTORY * 2):]:
                role = msg.get("role")
                content = msg.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        all_sources: List[SourceDocument] = []
        step_logs: List[Dict[str, Any]] = []
        spans: List[Dict[str, Any]] = []
        budget_tools_used = 0
        wm_updates_used = 0
        iterations_used = 0
        t_run_start = time.perf_counter()

        def refresh_system_prompt() -> None:
            snap = agent_working_memory.get_snapshot(working_memory_key)
            messages[0]["content"] = (
                AGENT_SYSTEM_PROMPT_BASE + "\n\n" + _format_working_memory_block(snap)
            )

        async def run_budget_tool(
            name: str, coro: Coroutine[Any, Any, str]
        ) -> str:
            nonlocal budget_tools_used
            if budget_tools_used >= max_budget_tools:
                return (
                    "Tool budget exhausted for this run; use prior results and finish without "
                    "more search_docs/http_get/slack_post_message."
                )
            budget_tools_used += 1
            t0 = time.perf_counter()
            try:
                out = await asyncio.wait_for(
                    coro, timeout=settings.AGENT_TOOL_TIMEOUT_SEC
                )
                ok = True
                err = None
            except asyncio.TimeoutError:
                out = f"Tool {name} timed out after {settings.AGENT_TOOL_TIMEOUT_SEC}s."
                ok = False
                err = "timeout"
            except Exception as e:
                logger.exception("[agent trace=%s] tool %s failed", trace_id, name)
                out = f"Tool {name} failed: {e}"
                ok = False
                err = str(e)
            dur_ms = (time.perf_counter() - t0) * 1000
            spans.append(
                {
                    "name": f"tool.{name}",
                    "duration_ms": round(dur_ms, 2),
                    "ok": ok,
                    "error": err,
                }
            )
            return out

        final_answer: Optional[str] = None
        error_out: Optional[str] = None

        try:
            for iteration in range(max_iter):
                iterations_used = iteration + 1
                refresh_system_prompt()

                t0 = time.perf_counter()
                logger.info(
                    "[agent trace=%s] iteration=%s/%s",
                    trace_id,
                    iterations_used,
                    max_iter,
                )

                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=2000,
                )
                msg = response.choices[0].message
                llm_ms = (time.perf_counter() - t0) * 1000
                spans.append(
                    {
                        "name": "llm.completion",
                        "iteration": iterations_used,
                        "duration_ms": round(llm_ms, 2),
                        "has_tool_calls": bool(msg.tool_calls),
                    }
                )

                if include_step_logs:
                    step_logs.append(
                        {
                            "kind": "llm",
                            "iteration": iterations_used,
                            "latency_ms": round(llm_ms, 2),
                            "has_tool_calls": bool(msg.tool_calls),
                        }
                    )

                if not msg.tool_calls:
                    text = (msg.content or "").strip()
                    if not text:
                        text = "I could not produce a final answer."
                    if include_step_logs:
                        step_logs.append({"kind": "final", "iteration": iterations_used})
                    final_answer = text
                    break

                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
                messages.append(assistant_msg)

                budget_hit = False
                for tc in msg.tool_calls:
                    name = tc.function.name
                    raw_args = tc.function.arguments or "{}"
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}

                    result_text: str

                    if name == "update_working_memory":
                        result_text, wm_updates_used = self._tool_update_working_memory(
                            working_memory_key, args, wm_updates_used
                        )
                    elif name == "search_docs":
                        q = (args.get("query") or "").strip()
                        if not q:
                            result_text = "Missing query parameter for search_docs."
                        elif budget_tools_used >= max_budget_tools:
                            budget_hit = True
                            result_text = (
                                "Documentation search limit reached for this request."
                            )
                        else:

                            async def _search() -> str:
                                logger.info(
                                    "[agent trace=%s] search_docs query=%r",
                                    trace_id,
                                    q[:200],
                                )
                                ctx, srcs = await self._rag.retrieve(q)
                                all_sources.extend(srcs)
                                agent_working_memory.append_finding(
                                    working_memory_key,
                                    f"search_docs: {q[:120]}",
                                )
                                return ctx or "No relevant documentation found."

                            result_text = await run_budget_tool(
                                "search_docs", _search()
                            )
                    elif name == "http_get":
                        url = (args.get("url") or "").strip()
                        allow = _http_host_allowlist()
                        verr = _validate_http_url(url, allow)
                        if verr:
                            result_text = verr
                        elif budget_tools_used >= max_budget_tools:
                            budget_hit = True
                            result_text = (
                                "Tool budget exhausted; cannot run http_get."
                            )
                        else:
                            result_text = await run_budget_tool(
                                "http_get", self._tool_http_get(url)
                            )
                            if result_text.startswith("HTTP 2"):
                                agent_working_memory.append_finding(
                                    working_memory_key,
                                    f"http_get: {url[:160]}",
                                )
                    elif name == "slack_post_message":
                        cid = (args.get("channel_id") or "").strip()
                        st = (args.get("text") or "").strip()
                        if not cid:
                            result_text = "Missing channel_id for slack_post_message."
                        elif not st:
                            result_text = "Missing text for slack_post_message."
                        elif not settings.AGENT_APPROVAL_SECRET:
                            result_text = (
                                "slack_post_message is disabled until "
                                "AGENT_APPROVAL_SECRET is set on the server."
                            )
                        elif not sensitive_tools_approved:
                            result_text = (
                                "slack_post_message refused: set allow_sensitive_tools=true "
                                "and pass approval_secret matching the server (human approval)."
                            )
                        elif budget_tools_used >= max_budget_tools:
                            budget_hit = True
                            result_text = (
                                "Tool budget exhausted; cannot post to Slack."
                            )
                        else:
                            result_text = await run_budget_tool(
                                "slack_post_message",
                                self._tool_slack_post_execute(cid, st),
                            )
                    else:
                        result_text = f"Unknown tool: {name}"

                    if include_step_logs:
                        preview = result_text[:400] + (
                            "..." if len(result_text) > 400 else ""
                        )
                        step_logs.append(
                            {
                                "kind": "tool",
                                "iteration": iterations_used,
                                "tool": name,
                                "input": args,
                                "output_preview": preview,
                            }
                        )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_text,
                        }
                    )

                if budget_hit or budget_tools_used >= max_budget_tools:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You have reached the tool budget for this run "
                                "(search_docs / http_get / slack_post_message). "
                                "Summarize and answer without further such tools."
                            ),
                        }
                    )

            if final_answer is None:
                final_answer = (
                    "I ran out of steps while using tools. "
                    "Please try a narrower question or try again."
                )
        except Exception as e:
            error_out = str(e)
            logger.error("[agent trace=%s] agent run error: %s", trace_id, e)
            final_answer = f"Agent failed: {e}"
        finally:
            elapsed_ms = (time.perf_counter() - t_run_start) * 1000
            trace_record = {
                "trace_id": trace_id,
                "working_memory_key": working_memory_key,
                "query": user_message[:2000],
                "sensitive_tools_approved": sensitive_tools_approved,
                "iterations": iterations_used,
                "budget_tools_used": budget_tools_used,
                "wm_updates_used": wm_updates_used,
                "duration_ms": round(elapsed_ms, 2),
                "answer_preview": (final_answer or "")[:2000],
                "error": error_out,
                "spans": merge_spans(spans),
                "steps": step_logs if include_step_logs else [],
            }
            persist_agent_trace(trace_id, trace_record)

        return (
            final_answer or "",
            _dedupe_sources(all_sources),
            trace_id,
            iterations_used,
            budget_tools_used,
            step_logs,
        )
