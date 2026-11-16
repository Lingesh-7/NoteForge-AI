import hashlib
import logging

from langchain_openai import ChatOpenAI
from tavily import TavilyClient

from prompts import prompts
from graph.state import GraphState
from utils.helper import clean_topics
from utils.cache import get_from_cache, set_cache

logger = logging.getLogger("noteforge")

# Maximum number of times the writer will attempt a topic before the critic's
# feedback is dropped and the topic moves on regardless (prevents infinite loops
# and bounds latency/cost per topic).
MAX_WRITE_ATTEMPTS = 2


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# "openrouter/free" lets OpenRouter pick whichever free model is available right
# now. Individual free models are added and withdrawn often, so this default
# keeps working when a specific ":free" model disappears.
DEFAULT_MODEL = "openrouter/free"


def get_llm(state: GraphState) -> ChatOpenAI:
    """Chat model served by OpenRouter (it speaks the OpenAI API)."""
    api_key = state.get("api_key")
    if not api_key:
        raise ValueError("Missing OpenRouter API key.")
    return ChatOpenAI(
        model=state.get("model") or DEFAULT_MODEL,
        temperature=0.3,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        timeout=120,
        max_retries=2,
    )


def _source_id(state: GraphState) -> str:
    """Identifies where research comes from: a specific book, the web, or the model alone."""
    if state.get("has_book"):
        return f"book:{state.get('source_id') or 'unknown'}"
    return "web" if state.get("tavily_api_key") else "llm"


def get_tavily_client(api_key: str) -> TavilyClient:
    if not api_key:
        raise ValueError("Missing Tavily API key.")
    return TavilyClient(api_key=api_key)


# -------- PLANNER --------
def planner_node(state: GraphState):
    llm = get_llm(state)

    response = llm.invoke(
        prompts.planner_prompt.format_messages(syllabus=state["syllabus"])
    )

    topics = clean_topics(response.content)

    if not topics:
        raise ValueError(
            "Couldn't break the syllabus into topics. Try rephrasing it, e.g. "
            "'Topic: Subtopic1, Subtopic2' per line."
        )

    return {
        **state,
        "topics": topics,
        "current_topic_index": 0,
        "current_topic": topics[0],
        "all_notes": [],
        "all_questions": [],
    }


# -------- RESEARCHER --------
def researcher_node(state: GraphState):
    topic = state["current_topic"]
    has_book = state["has_book"]
    vectorstore = state.get("vectorstore")

    # The cache is shared by every user of the deployment, so key it by the
    # source too: research drawn from one user's book must not be served to a
    # user with a different book (or none).
    cache_key = f"research::{_source_id(state)}::{topic}"
    cached = get_from_cache(cache_key)

    if cached:
        return {**state, "research_content": cached}

    llm = get_llm(state)

    if has_book and vectorstore:
        docs = vectorstore.similarity_search(topic, k=4)

        seen = set()
        filtered = []
        for d in docs:
            if d.page_content not in seen:
                seen.add(d.page_content)
                filtered.append(d)

        context = "\n\n".join(d.page_content for d in filtered[:6])
    elif state.get("tavily_api_key"):
        try:
            tavily_client = get_tavily_client(state["tavily_api_key"])
            results = tavily_client.search(query=topic, max_results=2)
            context = "\n\n".join(r["content"] for r in results["results"])
        except Exception:
            logger.exception("Tavily search failed for topic %r", topic)
            context = ""
    else:
        # No book and no web search configured: the model writes from its own
        # knowledge. The app warns the user about this before the run.
        context = ""

    context = context.replace("\n\n\n", "\n")[:1200]

    response = llm.invoke(
        prompts.researcher_prompt.format_messages(topic=topic, context=context)
    )

    result = response.content
    set_cache(cache_key, result)

    return {**state, "research_content": result}


# -------- WRITER --------
def writer_node(state: GraphState):
    llm = get_llm(state)

    feedback = state.get("critic_feedback", "")
    content = state["research_content"]

    if feedback:
        content += f"\n\nFix based on feedback:\n{feedback}"

    response = llm.invoke(
        prompts.writer_prompt.format_messages(
            topic=state["current_topic"],
            research_content=content,
        )
    )

    # Count this write attempt. retry_count tracks attempts used for the
    # *current* topic and is reset by next_topic_node.
    attempts = state.get("retry_count", 0) + 1

    return {
        **state,
        "draft_notes": response.content,
        "retry_count": attempts,
    }


# -------- CRITIC --------
def critic_node(state: GraphState):
    llm = get_llm(state)

    response = llm.invoke(
        prompts.critic_prompt.format_messages(
            topic=state["current_topic"],
            draft_notes=state["draft_notes"],
        )
    )

    output = response.content.lower()
    passed = output.startswith("pass")

    return {
        **state,
        "critic_pass": passed,
        "critic_feedback": response.content,
    }


# -------- EXAM AGENT --------
def exam_agent_node(state: GraphState):
    return {
        **state,
        "all_notes": state.get("all_notes", []) + [state["draft_notes"]],
    }


# -------- FINAL EXAM --------
def final_exam_node(state: GraphState):
    syllabus_hash = hashlib.sha256(
        state.get("syllabus", "").encode("utf-8")
    ).hexdigest()
    cache_key = f"unit_questions::{_source_id(state)}::{syllabus_hash}"
    cached = get_from_cache(cache_key)

    if cached:
        return {**state, "unit_questions": cached}

    notes = state.get("all_notes", [])
    topics = state.get("topics", [])

    if not notes:
        return {**state, "unit_questions": "Questions unavailable."}

    # Sample from across ALL topics, not just the first few.
    combined = ""
    for i, note in enumerate(notes):
        heading = topics[i] if i < len(topics) else f"Topic {i + 1}"
        combined += f"## {heading}\n{note[:300]}\n\n"
    combined = combined[:2500]

    try:
        llm = get_llm(state)
        response = llm.invoke(
            prompts.exam_prompt.format_messages(
                topic="Complete Unit",
                final_notes=combined,
            )
        )
        questions = response.content
    except Exception:
        # Don't cache the failure, or every later run of this syllabus would
        # get the placeholder instead of real questions.
        logger.exception("Exam question generation failed")
        return {**state, "unit_questions": "Questions unavailable due to limits."}

    set_cache(cache_key, questions)

    return {**state, "unit_questions": questions}


# -------- NEXT TOPIC --------
def next_topic_node(state: GraphState):
    i = state["current_topic_index"] + 1

    return {
        **state,
        "current_topic_index": i,
        "current_topic": state["topics"][i],
        "retry_count": 0,
        "critic_feedback": "",
        "critic_pass": False,
    }


# -------- FORMATTER --------
def formatter_node(state: GraphState):
    output = ""

    for i, topic in enumerate(state["topics"]):
        output += f"# {topic}\n\n"
        if i < len(state["all_notes"]):
            output += state["all_notes"][i] + "\n\n"

    output += "\n# Important Questions\n\n"
    output += state.get("unit_questions", "No questions generated.")

    return {**state, "final_document": output}


# -------- ROUTERS --------
def critic_router(state: GraphState):
    if state["critic_pass"] or state["retry_count"] >= MAX_WRITE_ATTEMPTS:
        return "exam_agent"
    return "writer"


def topic_router(state: GraphState):
    if state["current_topic_index"] + 1 < len(state["topics"]):
        return "next_topic"
    return "final_exam"
