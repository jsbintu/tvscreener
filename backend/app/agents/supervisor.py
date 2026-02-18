"""
Bubby Vision — LangGraph Supervisor (Agent Orchestrator)

Multi-agent orchestration using LangGraph. Routes user messages to the
appropriate specialist agent based on intent classification.

Architecture: Supervisor (router) → Specialist Agents → Tools → Engines → Data
"""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Literal, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent

from app.agents.prompts import (
    BREAKOUT_AGENT_PROMPT,
    MASTER_SYSTEM_PROMPT,
    NEWS_AGENT_PROMPT,
    OPTIONS_AGENT_PROMPT,
    PORTFOLIO_AGENT_PROMPT,
    TA_AGENT_PROMPT,
    VISION_AGENT_PROMPT,
)
from app.agents.tools import (
    ALL_TOOLS,
    BREAKOUT_TOOLS,
    NEWS_TOOLS,
    OPTIONS_TOOLS,
    PORTFOLIO_TOOLS,
    TA_TOOLS,
    VISION_TOOLS,
)
from app.config import get_settings


# ──────────────────────────────────────────────
# State
# ──────────────────────────────────────────────

class AgentState(TypedDict):
    """State passed between nodes in the LangGraph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str
    conversation_id: str
    tools_called: list[str]


# ──────────────────────────────────────────────
# LLM Factory
# ──────────────────────────────────────────────

def _create_llm(model: str = "gemini-3.0-flash", temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """Create a Gemini 3 Flash LLM instance."""
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.google_api_key,
        temperature=temperature,
        max_output_tokens=4096,
        convert_system_message_to_human=True,
    )


# ──────────────────────────────────────────────
# Intent Router
# ──────────────────────────────────────────────

ROUTER_PROMPT = """You are a routing agent for Bubby Vision. Classify the user's message
and decide which specialist agent should handle it.

Available agents:
- **ta_agent**: Technical analysis, chart patterns, indicators, support/resistance, trend analysis
- **options_agent**: Options chains, Greeks, GEX, IV, options strategies, put/call ratios
- **breakout_agent**: Breakout detection, precursor signals, volume analysis, failed breakouts
- **news_agent**: News, sentiment, Fear & Greed, Reddit/WSB, earnings, SEC filings
- **portfolio_agent**: Position sizing, risk management, trailing stops, portfolio review
- **vision_agent**: Deep pattern analysis, chart health checks, chart comparison, candle narration

Respond with ONLY the agent name. If unsure, use "ta_agent" as default.
If the question is general or multi-topic, use "ta_agent".

Examples:
- "Analyze AAPL" → ta_agent
- "What's the RSI for TSLA?" → ta_agent
- "Show me NVDA options chain" → options_agent
- "What's the GEX on SPY?" → options_agent
- "Is AAPL about to break out?" → breakout_agent
- "What's the sentiment on GME?" → news_agent
- "Size my position for TSLA at $250" → portfolio_agent
- "What patterns does AAPL have?" → vision_agent
- "Check chart health for NVDA" → vision_agent
- "Compare AAPL vs MSFT vs GOOGL" → vision_agent
"""


def route_intent(state: AgentState) -> AgentState:
    """Route the user's message to the appropriate specialist agent."""
    llm = _create_llm(temperature=0.0)

    last_message = state["messages"][-1].content if state["messages"] else ""

    response = llm.invoke([
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=f"Route this message: {last_message}"),
    ])

    agent_name = response.content.strip().lower()
    valid_agents = {"ta_agent", "options_agent", "breakout_agent", "news_agent", "portfolio_agent", "vision_agent"}

    if agent_name not in valid_agents:
        agent_name = "ta_agent"

    return {**state, "next_agent": agent_name}


# ──────────────────────────────────────────────
# Agent Nodes — Lazy LLM initialization
# ──────────────────────────────────────────────

def _build_agent_node(system_prompt: str, tools: list, agent_name: str):
    """Factory: create a LangGraph node for a specialist agent.

    LLM and ReAct agent are created lazily on first invocation
    so that the graph can be built without API credentials present.
    """
    _cached_agent = {}

    def _get_or_create_agent():
        if "agent" not in _cached_agent:
            llm = _create_llm()
            _cached_agent["agent"] = create_react_agent(
                model=llm,
                tools=tools,
                state_modifier=SystemMessage(content=f"{MASTER_SYSTEM_PROMPT}\n\n{system_prompt}"),
            )
        return _cached_agent["agent"]

    def node_fn(state: AgentState) -> AgentState:
        agent = _get_or_create_agent()
        result = agent.invoke({"messages": state["messages"]})
        tools_called = list(state.get("tools_called", []))
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    tools_called.append(tc.get("name", "unknown"))
        return {
            "messages": result["messages"],
            "next_agent": state["next_agent"],
            "conversation_id": state["conversation_id"],
            "tools_called": tools_called,
        }

    node_fn.__name__ = agent_name
    return node_fn


def _decide_next(state: AgentState) -> str:
    """Decide which agent node to run based on the router's decision."""
    return state.get("next_agent", "ta_agent")


# ──────────────────────────────────────────────
# Graph Construction
# ──────────────────────────────────────────────

def build_graph():
    """Build the LangGraph multi-agent workflow.

    The graph is built WITHOUT creating any LLM instances.
    LLMs are created lazily when nodes are first invoked.

    Flow:
    1. User message → Router (intent classification)
    2. Router → Specialist Agent (with tools)
    3. Specialist Agent → Response
    """
    workflow = StateGraph(AgentState)

    # Add nodes (no LLM creation happens here)
    workflow.add_node("router", route_intent)
    workflow.add_node("ta_agent", _build_agent_node(TA_AGENT_PROMPT, TA_TOOLS, "ta_agent"))
    workflow.add_node("options_agent", _build_agent_node(OPTIONS_AGENT_PROMPT, OPTIONS_TOOLS, "options_agent"))
    workflow.add_node("breakout_agent", _build_agent_node(BREAKOUT_AGENT_PROMPT, BREAKOUT_TOOLS, "breakout_agent"))
    workflow.add_node("news_agent", _build_agent_node(NEWS_AGENT_PROMPT, NEWS_TOOLS, "news_agent"))
    workflow.add_node("portfolio_agent", _build_agent_node(PORTFOLIO_AGENT_PROMPT, PORTFOLIO_TOOLS, "portfolio_agent"))
    workflow.add_node("vision_agent", _build_agent_node(VISION_AGENT_PROMPT, VISION_TOOLS, "vision_agent"))

    # Entry point
    workflow.set_entry_point("router")

    # Conditional routing after classification
    workflow.add_conditional_edges(
        "router",
        _decide_next,
        {
            "ta_agent": "ta_agent",
            "options_agent": "options_agent",
            "breakout_agent": "breakout_agent",
            "news_agent": "news_agent",
            "portfolio_agent": "portfolio_agent",
            "vision_agent": "vision_agent",
        },
    )

    # All agents go to END after responding
    workflow.add_edge("ta_agent", END)
    workflow.add_edge("options_agent", END)
    workflow.add_edge("breakout_agent", END)
    workflow.add_edge("news_agent", END)
    workflow.add_edge("portfolio_agent", END)
    workflow.add_edge("vision_agent", END)

    return workflow


# ──────────────────────────────────────────────
# Public Interface
# ──────────────────────────────────────────────

_compiled_graph = None


def get_graph():
    """Get or create the compiled LangGraph."""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_graph()
        _compiled_graph = workflow.compile()
    return _compiled_graph


async def chat(message: str, conversation_id: Optional[str] = None) -> dict:
    """Process a chat message through the multi-agent system.

    Pipeline: Memory Context → RAG Context → Router → Agent → RAG Ingest → Memory Update → Metrics

    Args:
        message: User's message (already sanitized by guardrails).
        conversation_id: Existing conversation ID (for session memory).

    Returns:
        Dict with response message, agent used, and tools called.
    """
    import time
    from app.guardrails import InputGuard
    from app.memory.manager import get_memory_manager
    from app.observability import agent_metrics

    graph = get_graph()
    conv_id = conversation_id or str(uuid.uuid4())

    # ── Inject memory context ──
    memory = get_memory_manager()
    memory_context = memory.get_full_context(conv_id)

    # ── Inject RAG context ──
    rag_context = ""
    tickers = InputGuard.extract_tickers(message)
    try:
        from app.rag.pipeline import get_rag_pipeline
        rag = get_rag_pipeline()
        if rag.available:
            rag_results = rag.query(message, n_results=5)
            if rag_results:
                rag_chunks = "\n\n---\n\n".join(
                    f"[Source: {r['metadata'].get('source', 'unknown')} | "
                    f"Ticker: {r['metadata'].get('ticker', 'N/A')}]\n{r['text']}"
                    for r in rag_results
                    if r.get("distance", 1.0) < 0.8  # Only include relevant matches
                )
                if rag_chunks:
                    rag_context = f"## Relevant Research Context\n{rag_chunks}"
    except Exception as exc:
        log.debug("rag.context_fetch_failed", error=str(exc))

    messages: list[BaseMessage] = []
    if memory_context:
        messages.append(SystemMessage(content=f"## User Context\n{memory_context}"))
    if rag_context:
        messages.append(SystemMessage(content=rag_context))
    messages.append(HumanMessage(content=message))

    initial_state: AgentState = {
        "messages": messages,
        "next_agent": "",
        "conversation_id": conv_id,
        "tools_called": [],
    }

    start = time.perf_counter()
    result = await graph.ainvoke(initial_state)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Extract the final AI message
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage) and m.content]
    response_text = ai_messages[-1].content if ai_messages else "I couldn't process that request."

    agent_used = result.get("next_agent", "unknown")

    # ── Auto-ingest conversation into RAG (for future context) ──
    if tickers and len(response_text) > 200:
        try:
            from app.rag.pipeline import get_rag_pipeline
            rag = get_rag_pipeline()
            if rag.available:
                rag.ingest(
                    doc_id=f"chat_{conv_id}_{tickers[0]}",
                    text=f"Q: {message}\n\nA: {response_text}",
                    metadata={
                        "source": "chat_history",
                        "ticker": tickers[0],
                        "agent": agent_used,
                        "conversation_id": conv_id,
                    },
                )
        except Exception:
            pass  # Non-critical, don't fail the response

    # ── Update session memory ──
    if tickers:
        memory.session.update_session_context(conv_id, ticker=tickers[0], agent=agent_used)
    else:
        memory.session.update_session_context(conv_id, agent=agent_used)

    # ── Record metrics ──
    agent_metrics.record_call(agent_used, latency_ms=elapsed_ms, success=True)

    return {
        "message": response_text,
        "conversation_id": conv_id,
        "agent_used": agent_used,
        "tools_called": result.get("tools_called", []),
    }
