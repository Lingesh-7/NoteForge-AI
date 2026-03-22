import os
import streamlit as st
from fpdf import FPDF
from groq import RateLimitError

from graph.graph_builder import build_graph
from rag.vectordb import create_vectorstore


st.set_page_config(page_title="AI Notes Generator", layout="wide")
st.title("AI Notes Generator")


# ---- API KEY ----
st.sidebar.header("API Settings")
user_api_key = st.sidebar.text_input("GROQ API Key", type="password")

if user_api_key:
    os.environ["GROQ_API_KEY"] = user_api_key


# ---- PDF GENERATION ----
def create_pdf(text: str):
    pdf = FPDF()
    pdf.add_page()

    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "fonts/DejaVuSans-Bold.ttf", uni=True)

    pdf.set_auto_page_break(auto=True, margin=12)

    for line in text.split("\n"):
        line = line.strip()

        if not line:
            pdf.ln(3)
            continue

        if line.startswith("# "):
            pdf.set_font("DejaVu", "B", 16)
            pdf.cell(0, 10, line[2:], ln=True)

        elif line.startswith(("Definition", "Intuition", "Detailed Explanation", "Example", "Key Points")):
            pdf.set_font("DejaVu", "B", 13)
            pdf.multi_cell(0, 8, line)

        else:
            pdf.set_font("DejaVu", "", 12)
            pdf.multi_cell(0, 7, line)

    pdf.output("notes.pdf")


# ---- INPUT ----
syllabus = st.text_area("Enter syllabus")
pdf_file = st.file_uploader("Upload Book PDF (optional)", type=["pdf"])

status_box = st.empty()
progress_bar = st.progress(0)

graph = build_graph()


# ---- GENERATE ----
if st.button("Generate Notes"):

    if not syllabus.strip():
        st.error("Enter syllabus")
        st.stop()

    vectorstore = None

    if pdf_file:
        with st.spinner("Processing PDF..."):
            with open("temp.pdf", "wb") as f:
                f.write(pdf_file.read())
            vectorstore = create_vectorstore("temp.pdf")

    state = {
        "syllabus": syllabus,
        "has_book": bool(vectorstore),
        "vectorstore": vectorstore,
        "api_key": user_api_key,
        "topics": [],
        "current_topic_index": 0,
        "all_notes": [],
        "all_questions": [],
        "retry_count": 0,
        "critic_feedback": "",
        "critic_pass": False,
        "research_content": "",
        "draft_notes": "",
        "final_notes": "",
        "exam_questions": "",
        "final_document": ""
    }

    status_box.info("Generating...")

    current_state = None
    rate_limited = False

    try:
        for step in graph.stream(state):
            node = list(step.keys())[0]
            current_state = step[node]

            topic = current_state.get("current_topic", "")
            idx = current_state.get("current_topic_index", 0)
            total = len(current_state.get("topics", [])) or 1

            progress = int(((idx + 1) / total) * 100)
            progress_bar.progress(progress)

            status_box.info(f"{node} | {topic} | {progress}%")

    except RateLimitError:
        rate_limited = True
        status_box.warning("Rate limit reached. Returning partial output.")


    if current_state is None:
        st.error("Generation failed")
        st.stop()


    if rate_limited:
        notes = current_state.get("all_notes", [])
        final_doc = ""

        for i, note in enumerate(notes):
            topic = current_state["topics"][i]
            final_doc += f"# {topic}\n\n{note}\n\n"

        final_doc += "\nStopped due to rate limit.\n"

    else:
        final_doc = current_state.get("final_document", "")


    with st.spinner("Creating PDF..."):
        create_pdf(final_doc)

    with open("notes.pdf", "rb") as f:
        st.download_button("Download PDF", f, file_name="notes.pdf")