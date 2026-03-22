from langchain_groq import ChatGroq
from prompts import prompts
from graph.state import GraphState
from dotenv import load_dotenv
from tavily import TavilyClient
import os

from utils.helper import clean_topics
from utils.cache import get_from_cache, set_cache

load_dotenv()

os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY")

tavily_client = TavilyClient()


def get_llm(api_key=None):
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.3,
        groq_api_key=api_key
    )


# -------- PLANNER --------
def planner_node(state: GraphState):
    llm = get_llm(state.get("api_key"))

    response = llm.invoke(
        prompts.planner_prompt.format_messages(
            syllabus=state["syllabus"]
        )
    )

    topics = clean_topics(response.content)

    if not topics:
        raise ValueError("Planner failed to generate topics")

    return {
        **state,
        "topics": topics,
        "current_topic_index": 0,
        "current_topic": topics[0]
    }


# -------- RESEARCHER --------
def researcher_node(state: GraphState):
    topic = state["current_topic"]
    has_book = state["has_book"]
    vectorstore = state.get("vectorstore")

    cache_key = f"research::{topic}"
    cached = get_from_cache(cache_key)

    if cached:
        return {**state, "research_content": cached}

    llm = get_llm(state.get("api_key"))

    query_prompt = f"Generate 2 specific search queries for: {topic}"
    queries_resp = llm.invoke(query_prompt)

    queries = [
        q.strip("- ").strip()
        for q in queries_resp.content.split("\n")
        if q.strip()
    ]

    docs = []

    if has_book and vectorstore:
        for q in queries:
            docs.extend(vectorstore.similarity_search(q, k=2))

        seen = set()
        filtered = []

        for d in docs:
            if d.page_content not in seen:
                seen.add(d.page_content)
                filtered.append(d)

        context = "\n\n".join(d.page_content for d in filtered[:6])

    else:
        results = tavily_client.search(query=topic, max_results=2)
        context = "\n\n".join(r["content"] for r in results["results"])

    context = context.replace("\n\n\n", "\n")[:1200]

    response = llm.invoke(
        prompts.researcher_prompt.format_messages(
            topic=topic,
            context=context
        )
    )

    result = response.content
    set_cache(cache_key, result)

    return {
        **state,
        "research_content": result
    }


# -------- WRITER --------
def writer_node(state: GraphState):
    llm = get_llm(state.get("api_key"))

    feedback = state.get("critic_feedback", "")
    content = state["research_content"]

    if feedback:
        content += f"\n\nFix based on feedback:\n{feedback}"

    response = llm.invoke(
        prompts.writer_prompt.format_messages(
            topic=state["current_topic"],
            research_content=content
        )
    )

    return {
        **state,
        "draft_notes": response.content
    }


# -------- CRITIC --------
def critic_node(state: GraphState):
    llm = get_llm(state.get("api_key"))

    response = llm.invoke(
        prompts.critic_prompt.format_messages(
            topic=state["current_topic"],
            draft_notes=state["draft_notes"]
        )
    )

    output = response.content.lower()
    passed = output.startswith("pass")

    retry = state.get("retry_count", 0)
    if not passed:
        retry += 1

    return {
        **state,
        "critic_pass": passed,
        "critic_feedback": response.content,
        "retry_count": retry
    }


# -------- EXAM AGENT --------
def exam_agent_node(state: GraphState):
    topic = state["current_topic"]

    cache_key = f"final_notes::{topic}"
    set_cache(cache_key, state["draft_notes"])

    return {
        **state,
        "all_notes": state.get("all_notes", []) + [state["draft_notes"]],
    }


# -------- FINAL EXAM --------
def final_exam_node(state: GraphState):
    syllabus_hash = hash(state.get("syllabus", ""))

    cache_key = f"unit_questions::{syllabus_hash}"
    cached = get_from_cache(cache_key)

    if cached:
        return {**state, "unit_questions": cached}

    llm = get_llm(state.get("api_key"))

    notes = state.get("all_notes", [])

    if not notes:
        return {
            **state,
            "unit_questions": "Questions unavailable."
        }

    combined = "\n\n".join(notes[:3])[:1200]

    try:
        response = llm.invoke(
            prompts.exam_prompt.format_messages(
                topic="Complete Unit",
                final_notes=combined
            )
        )
        questions = response.content
    except Exception:
        questions = "Questions unavailable due to limits."

    set_cache(cache_key, questions)

    return {
        **state,
        "unit_questions": questions
    }


# -------- NEXT TOPIC --------
def next_topic_node(state: GraphState):
    i = state["current_topic_index"] + 1

    return {
        **state,
        "current_topic_index": i,
        "current_topic": state["topics"][i],
        "retry_count": 0,
        "critic_feedback": "",
        "critic_pass": False
    }


# -------- FORMATTER --------
def formatter_node(state: GraphState):
    output = ""

    for i, topic in enumerate(state["topics"]):
        output += f"# {topic}\n\n"
        output += state["all_notes"][i] + "\n\n"

    output += "\n# Important Questions\n\n"
    output += state.get("unit_questions", "No questions generated.")

    return {
        **state,
        "final_document": output
    }


# -------- ROUTERS --------
def critic_router(state: GraphState):
    if state["critic_pass"] or state["retry_count"] >= 1:
        return "exam_agent"
    return "writer"


def topic_router(state: GraphState):
    if state["current_topic_index"] + 1 < len(state["topics"]):
        return "next_topic"
    return "formatter"