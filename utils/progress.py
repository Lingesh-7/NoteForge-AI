"""Turn graph stream events into an accurate progress report.

`graph.stream()` reports a node only after it has *finished*. To tell the user
what is happening *now*, we work out which node runs next, using the graph's
own routers so this can never disagree with the real control flow.
"""
from dataclasses import dataclass

from graph.nodes import MAX_WRITE_ATTEMPTS, critic_router, topic_router

# Work units: 1 for planning, 3 per topic (research, write, review),
# 1 for exam questions, 1 for assembling the document.
UNITS_PER_TOPIC = 3
FIXED_UNITS = 3


@dataclass(frozen=True)
class Progress:
    fraction: float        # 0.0-1.0, never decreases during a run
    message: str           # what is happening now
    next_node: str | None  # node about to run (None when finished)
    topics_done: int
    topics_total: int
    active_topic: int | None  # 0-based index of the topic being worked on


def _research_verb(state: dict) -> str:
    if state.get("has_book"):
        return "Searching your book for"
    if state.get("tavily_api_key"):
        return "Searching the web for"
    return "Gathering facts on"


def after_step(node: str, state: dict) -> Progress:
    """Progress once `node` has finished, given the state it returned."""
    topics = state.get("topics", [])
    total = len(topics)
    done = len(state.get("all_notes", []))
    total_units = UNITS_PER_TOPIC * total + FIXED_UNITS
    base = 1 + UNITS_PER_TOPIC * done  # planning + every finished topic

    def topic_label(i: int) -> str:
        name = topics[i] if i < total else ""
        return f"topic {i + 1} of {total}: {name}"

    active: int | None = done if done < total else None

    if node == "planner":
        units, nxt = base, "researcher"
        message = f"{_research_verb(state)} {topic_label(0)}"
    elif node == "next_topic":
        units, nxt = base, "researcher"
        message = f"{_research_verb(state)} {topic_label(done)}"
    elif node == "researcher":
        units, nxt = base + 1, "writer"
        message = f"Writing notes for {topic_label(done)}"
    elif node == "writer":
        units, nxt = base + 2, "critic"
        message = f"Checking the notes for {topic_label(done)}"
    elif node == "critic":
        nxt = critic_router(state)
        if nxt == "writer":
            units = base + 2  # a rewrite repeats work; hold the bar, don't move it back
            attempt = state.get("retry_count", 0) + 1
            message = (
                f"Improving the notes after review (attempt {attempt} of "
                f"{MAX_WRITE_ATTEMPTS}) for {topic_label(done)}"
            )
        else:
            units = base + 3
            message = f"Saving {topic_label(done)}"
    elif node == "exam_agent":
        nxt = topic_router(state)
        units = base  # `done` already counts the topic just saved
        if nxt == "next_topic":
            message = f"Moving on to {topic_label(done)}"
        else:
            message = "Writing the important questions"
    elif node == "final_exam":
        units, nxt, active = total_units - 1, "formatter", None
        message = "Putting the document together"
    elif node == "formatter":
        units, nxt, active = total_units, None, None
        message = "Finished"
    else:  # unknown node: report honestly without moving the bar
        units, nxt = base, None
        message = "Working"

    fraction = min(max(units / total_units, 0.0), 1.0) if total else 0.0
    return Progress(fraction, message, nxt, done, total, active)


def checklist_markdown(topics: list[str], done: int, active: int | None) -> str:
    """A per-topic status list for the progress panel."""
    lines = []
    for i, topic in enumerate(topics):
        if i < done:
            lines.append(f":green[:material/check_circle:] {topic}")
        elif i == active:
            lines.append(f":blue[:material/pending:] **{topic}**")
        else:
            lines.append(f":gray[:material/radio_button_unchecked: {topic}]")
    return "  \n".join(lines)
