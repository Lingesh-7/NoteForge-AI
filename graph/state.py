from typing import TypedDict, List, Any


class GraphState(TypedDict):
    # -------- INPUT --------
    syllabus: str
    has_book: bool
    vectorstore: Any        # stores FAISS or None
    api_key: str            # GROQ API key from UI

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

    # -------- AGGREGATED OUTPUT --------
    all_notes: List[str]
    all_questions: List[str]

    # -------- EXAM QUESTIONS --------
    unit_questions: str     # set by final_exam_node, read by formatter_node

    # -------- FINAL DOCUMENT --------
    final_document: str

    mode: str