from typing import TypedDict, List, Any


class GraphState(TypedDict):
    # -------- INPUT --------
    syllabus: str
    has_book: bool
    vectorstore: Any   # stores FAISS or None

    # -------- TOPIC FLOW --------
    topics: List[str]
    current_topic_index: int
    current_topic: str

    # -------- CONTENT GENERATION --------
    research_content: str
    draft_notes: str

    # -------- CRITIC LOOP --------
    critic_feedback: str
    critic_pass: bool
    retry_count: int

    # -------- FINAL OUTPUT PER TOPIC --------
    final_notes: str
    exam_questions: str

    # -------- AGGREGATED OUTPUT --------
    all_notes: List[str]
    all_questions: List[str]

    # -------- FINAL DOCUMENT --------
    final_document: str