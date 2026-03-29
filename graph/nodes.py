"""
graph/nodes.py
==============
All LangGraph node functions.

Design principles
-----------------
- No module-level mutable state.  Every node receives all it needs via *state*.
- Each node returns a **new dict** (spread operator `{**state, …}`); the graph
  runner is responsible for merging.
- The Tavily client is instantiated lazily so it is never shared across threads.
"""

from __future__ import annotations

import os

from langchain_groq import ChatGroq
from tavily import TavilyClient

from graph.state import GraphState
from prompts import prompts
from utils.cache import get_from_cache, set_cache
from utils.helper import clean_topics

import re
# ── LLM factory ───────────────────────────────────────────────────────────────

def _llm(api_key: str | None = None) -> ChatGroq:
    """Return a fresh ChatGroq client.  Never reuse across requests."""
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.3,
        groq_api_key=api_key,
    )


def _tavily() -> TavilyClient:
    """Return a Tavily client using the key set in the environment."""
    return TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))


# ── Planner ───────────────────────────────────────────────────────────────────

def planner_node(state: GraphState) -> GraphState:
    llm = _llm(state.get("api_key"))

    response = llm.invoke(
        prompts.planner_prompt.format_messages(syllabus=state["syllabus"])
    )
    topics = clean_topics(response.content)

    if not topics:
        raise ValueError("Planner returned no topics — check the syllabus format.")

    return {
        **state,
        "topics":               topics,
        "current_topic_index":  0,
        "current_topic":        topics[0],
        "all_notes":            [],
        "all_questions":        [],
    }


# ── Researcher ────────────────────────────────────────────────────────────────

def researcher_node(state: GraphState) -> GraphState:
    topic       = state["current_topic"]
    has_book    = state["has_book"]
    vectorstore = state.get("vectorstore")

    cache_key = f"research::{topic}"
    cached    = get_from_cache(cache_key)
    if cached:
        return {**state, "research_content": cached}

    llm = _llm(state.get("api_key"))

    if has_book and vectorstore:
        docs = vectorstore.similarity_search(topic, k=4)

        seen: set[str] = set()
        unique_docs    = []
        for doc in docs:
            if doc.page_content not in seen:
                seen.add(doc.page_content)
                unique_docs.append(doc)

        context = "\n\n".join(d.page_content for d in unique_docs[:6])
    else:
        results = _tavily().search(query=topic, max_results=3)
        context = "\n\n".join(r["content"] for r in results["results"])

    # Normalise and truncate so we stay within the model context window
    context = context.replace("\n\n\n", "\n")[:1400]

    response = llm.invoke(
        prompts.researcher_prompt.format_messages(topic=topic, context=context)
    )

    result = response.content
    set_cache(cache_key, result)

    return {**state, "research_content": result}


# ── Writer ────────────────────────────────────────────────────────────────────

def writer_node(state: GraphState) -> GraphState:
    llm      = _llm(state.get("api_key"))
    feedback = state.get("critic_feedback", "")
    content  = state["research_content"]

    # Provide the last two notes as rolling context to avoid repetition
    prev_notes = "\n\n".join(state.get("all_notes", [])[-2:])
    if prev_notes:
        content += f"\n\nContext from previous topics (do NOT repeat):\n{prev_notes}"

    # Always generate in-depth; the "mode" selector has been removed from the UI
    content += (
        "\n\nInstruction: Provide a thorough, exam-focused explanation with "
        "conceptual clarity.  Avoid repeating anything covered in previous topics."
    )

    if feedback:
        content += f"\n\nRevision feedback — apply these improvements:\n{feedback}"

    response = llm.invoke(
        prompts.writer_prompt.format_messages(
            topic=state["current_topic"],
            research_content=content,
        )
    )

    return {**state, "draft_notes": response.content}


# ── Critic ────────────────────────────────────────────────────────────────────

def critic_node(state: GraphState) -> GraphState:
    llm = _llm(state.get("api_key"))

    response = llm.invoke(
        prompts.critic_prompt.format_messages(
            topic=state["current_topic"],
            draft_notes=state["draft_notes"],
        )
    )

    output = response.content.lower().strip()
    passed = output.startswith("pass") and "fail" not in output

    retry = state.get("retry_count", 0)
    if not passed:
        retry += 1

    return {
        **state,
        "critic_pass":     passed,
        "critic_feedback": response.content,
        "retry_count":     retry,
    }


# ── Exam agent ────────────────────────────────────────────────────────────────

def exam_agent_node(state: GraphState) -> GraphState:
    """Persist the approved draft and append it to all_notes."""
    topic = state["current_topic"]
    set_cache(f"final_notes::{topic}", state["draft_notes"])

    return {
        **state,
        "all_notes": state.get("all_notes", []) + [state["draft_notes"]],
    }


# ── Final exam question generator ─────────────────────────────────────────────

def final_exam_node(state: GraphState) -> GraphState:
    syllabus_hash = hash(state.get("syllabus", ""))
    cache_key     = f"unit_questions::{syllabus_hash}"
    cached        = get_from_cache(cache_key)
    if cached:
        return {**state, "unit_questions": cached}

    notes  = state.get("all_notes",  [])
    topics = state.get("topics",      [])

    if not notes:
        return {**state, "unit_questions": "Questions unavailable — no notes were generated."}

    llm = _llm(state.get("api_key"))

    # Sample first 350 chars of each topic to stay under the context limit
    combined = ""
    for i, note in enumerate(notes):
        heading  = topics[i] if i < len(topics) else f"Topic {i + 1}"
        combined += f"## {heading}\n{note[:350]}\n\n"
    combined = combined[:2800]

    try:
        response  = llm.invoke(
            prompts.exam_prompt.format_messages(
                topic="Complete Unit",
                final_notes=combined,
            )
        )
        questions = response.content
    except Exception:
        questions = "Questions could not be generated due to API limits."

    set_cache(cache_key, questions)
    return {**state, "unit_questions": questions}


# ── Next topic ────────────────────────────────────────────────────────────────

def next_topic_node(state: GraphState) -> GraphState:
    i = state["current_topic_index"] + 1
    return {
        **state,
        "current_topic_index": i,
        "current_topic":       state["topics"][i],
        "retry_count":         0,
        "critic_feedback":     "",
        "critic_pass":         False,
    }


# ── Formatter ─────────────────────────────────────────────────────────────────

def formatter_node(state: GraphState) -> GraphState:
    lines: list[str] = []

    for i, topic in enumerate(state["topics"]):
        lines.append(f"# {topic}\n")
        lines.append(state["all_notes"][i])
        lines.append("")

    lines.append("\n# Important Questions\n")
    lines.append(state.get("unit_questions", "No questions generated."))

    return {**state, "final_document": "\n".join(lines)}


# ── Routing functions ─────────────────────────────────────────────────────────

def critic_router(state: GraphState) -> str:
    """Allow at most one retry per topic to keep latency reasonable."""
    if state["critic_pass"] or state["retry_count"] >= 1:
        return "exam_agent"
    return "writer"


def topic_router(state: GraphState) -> str:
    if state["current_topic_index"] + 1 < len(state["topics"]):
        return "next_topic"
    return "final_exam"