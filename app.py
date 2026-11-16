import hashlib
import logging
import os
import tempfile
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from langgraph.errors import GraphRecursionError
from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

from graph.graph_builder import build_graph
from graph.nodes import DEFAULT_MODEL
from utils.progress import after_step, checklist_markdown

load_dotenv()  # app-level keys come from .env (or real environment variables when hosted)
logging.basicConfig(level=logging.INFO)
for noisy in ("httpx", "fontTools"):  # per-request and per-font-table lines are noise
    logging.getLogger(noisy).setLevel(logging.WARNING)
logger = logging.getLogger("noteforge")

FONT_DIR = Path(__file__).parent / "fonts"
MAX_UPLOAD_MB = 25          # keep in sync with maxUploadSize in .streamlit/config.toml
MAX_SYLLABUS_CHARS = 6000
# One topic takes up to 7 graph steps and LangGraph stops at 25 steps by default,
# which would cut off any syllabus with more than about three topics.
RECURSION_LIMIT = 2000

# Free models change often; the list is a convenience and the box accepts any id.
FREE_MODELS = [
    DEFAULT_MODEL,
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "baidu/ernie-5.5-flash-preview:free",
]

SECTION_LABELS = ("Definition", "Intuition", "Detailed Explanation", "Example", "Key Points")
MARK_LABELS = ("2 Marks", "5 Marks", "10 Marks")

EXAMPLE_SYLLABUS = (
    "Fuzzy sets: Membership functions, Operations on fuzzy sets\n"
    "Fuzzy inference: Mamdani method, Sugeno method\n"
    "Defuzzification"
)


# ---- CONFIG / SHARED RESOURCES ----
def get_secret(name: str) -> str:
    """Read an app-level key from the environment (.env is loaded at startup)."""
    return (os.getenv(name) or "").strip()


@st.cache_resource(show_spinner=False)
def get_graph():
    return build_graph()


@st.cache_resource(show_spinner=False)
def get_embeddings():
    # Imported here so the page renders before torch is loaded.
    from rag.vectordb import load_embeddings

    return load_embeddings()


def build_vectorstore(data: bytes):
    """Index an uploaded PDF. Uses a private temp file so concurrent users
    never read each other's uploads."""
    from rag.vectordb import create_vectorstore

    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return create_vectorstore(path, get_embeddings())
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ---- OUTPUT FORMATTING ----
def build_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    next_line = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

    for line in text.split("\n"):
        line = line.strip()

        if not line:
            pdf.ln(3)
        elif line.startswith("# "):
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", 16)
            pdf.multi_cell(0, 10, line[2:], **next_line)
        elif line.startswith(SECTION_LABELS) or line in MARK_LABELS:
            pdf.set_font("DejaVu", "B", 13)
            pdf.multi_cell(0, 8, line, **next_line)
        else:
            pdf.set_font("DejaVu", "", 12)
            pdf.multi_cell(0, 7, line, **next_line)

    return bytes(pdf.output())


def to_markdown(text: str) -> str:
    """Turn the plain-text document into Markdown for the preview and .md download."""
    blocks: list[str] = []
    in_list = False

    for line in text.split("\n"):
        s = line.strip()
        if not s:
            in_list = False
            continue

        if s.startswith("- "):
            if in_list:
                blocks[-1] += "\n" + s
            else:
                blocks.append(s)
            in_list = True
            continue

        in_list = False
        if s.startswith("# "):
            blocks.append(f"## {s[2:]}")
        elif s in SECTION_LABELS or s in MARK_LABELS:
            blocks.append(f"**{s}**")
        else:
            blocks.append(s)

    return "\n\n".join(blocks) + "\n"


def assemble_document(topics: list[str], notes: list[str], questions: str) -> str:
    """The plain-text document, from however many topics were finished."""
    doc = ""
    for topic, note in zip(topics, notes):
        doc += f"# {topic}\n\n{note}\n\n"
    if questions:
        doc += f"\n# Important Questions\n\n{questions}"
    return doc


def format_duration(seconds: float) -> str:
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes} min {secs} s" if minutes else f"{secs} s"


# ---- GENERATION ----
def generate(syllabus: str, pdf_file, api_key: str, model: str, tavily_key: str) -> None:
    """Run the pipeline and leave the outcome in st.session_state
    ("result" and/or "error") for the next rerun to display."""
    ss = st.session_state
    ss.error = None

    syllabus = syllabus.strip()
    if not api_key:
        ss.error = "Add your OpenRouter API key in step 1 first."
        return
    if not syllabus:
        ss.error = "Enter a syllabus first."
        return
    if len(syllabus) > MAX_SYLLABUS_CHARS:
        ss.error = (
            f"The syllabus is {len(syllabus):,} characters; the limit is "
            f"{MAX_SYLLABUS_CHARS:,}. Generate one unit at a time."
        )
        return
    if pdf_file is not None and pdf_file.size > MAX_UPLOAD_MB * 1024 * 1024:
        ss.error = f"The PDF is larger than {MAX_UPLOAD_MB} MB. Upload a smaller file."
        return

    started = time.monotonic()

    with st.status("Getting ready", expanded=True) as status:
        bar = st.progress(0.0, text="0%")
        checklist = st.empty()
        st.caption("Keep this tab open. Finished topics are kept even if the run stops early.")

        def show(fraction: float, message: str) -> None:
            status.update(label=message)
            bar.progress(fraction, text=f"{int(fraction * 100)}%")

        # -- optional book --
        vectorstore, source_id = None, ""
        if pdf_file is not None:
            data = pdf_file.getvalue()
            source_id = hashlib.sha256(data).hexdigest()
            cached = ss.get("book_index")

            if cached and cached["id"] == source_id:
                vectorstore = cached["store"]
            else:
                show(0.0, "Reading your book (the first time can take a minute)")
                try:
                    vectorstore = build_vectorstore(data)
                except ValueError as e:
                    ss.error = str(e)
                    return
                except Exception:
                    logger.exception("Could not index the uploaded PDF")
                    ss.error = "Couldn't read this PDF. It may be corrupted or password-protected."
                    return
                ss.book_index = {"id": source_id, "store": vectorstore}

        state = {
            "syllabus": syllabus,
            "has_book": vectorstore is not None,
            "vectorstore": vectorstore,
            "source_id": source_id,
            "api_key": api_key,
            "model": model or DEFAULT_MODEL,
            "tavily_api_key": tavily_key,
            "topics": [],
            "current_topic_index": 0,
            "current_topic": "",
            "all_notes": [],
            "all_questions": [],
            "retry_count": 0,
            "critic_feedback": "",
            "critic_pass": False,
            "research_content": "",
            "draft_notes": "",
            "unit_questions": "",
            "final_document": "",
        }

        current = None
        stop_reason = None  # set when the run ends early

        try:
            show(0.0, "Reading the syllabus and listing the topics")
            for step in get_graph().stream(state, config={"recursion_limit": RECURSION_LIMIT}):
                node, current = next(iter(step.items()))
                progress = after_step(node, current)
                show(progress.fraction, progress.message)
                checklist.markdown(
                    checklist_markdown(
                        current.get("topics", []), progress.topics_done, progress.active_topic
                    )
                )

        except AuthenticationError:
            ss.error = "OpenRouter rejected the API key. Check it in step 1 and try again."
            return
        except RateLimitError:
            stop_reason = (
                "The free-model rate limit was reached. Wait a minute, or pick another "
                "model in the sidebar, and run it again."
            )
        except APIConnectionError:
            stop_reason = "Couldn't reach OpenRouter. Check the connection and try again."
        except APIStatusError as e:
            logger.exception("OpenRouter API error")
            if e.status_code in (402, 404):
                stop_reason = (
                    f"OpenRouter can't serve this model right now (HTTP {e.status_code}). "
                    "Pick another model in the sidebar, or see Troubleshooting in the Guide tab."
                )
            else:
                stop_reason = f"OpenRouter returned an error (HTTP {e.status_code})."
        except GraphRecursionError:
            stop_reason = "The syllabus has too many topics for one run."
        except ValueError as e:  # e.g. the planner found no topics
            stop_reason = str(e)
        except Exception:
            logger.exception("Generation failed")
            stop_reason = "Something went wrong while generating the notes."

        topics = (current or {}).get("topics", [])
        notes = (current or {}).get("all_notes", [])
        questions = (current or {}).get("unit_questions", "") if not stop_reason else ""

        if not notes:
            ss.error = stop_reason or "Generation produced no output. Try again."
            return

        show(1.0 if not stop_reason else bar_fraction(len(notes), len(topics)), "Creating the PDF")
        document = assemble_document(topics, notes, questions)
        try:
            pdf_bytes = build_pdf(document)
        except Exception:
            logger.exception("PDF creation failed")
            pdf_bytes = None

    if vectorstore is not None:
        source = "Your book"
    elif tavily_key:
        source = "Web search"
    else:
        source = "AI knowledge"

    ss.result = {
        "topics": topics[: len(notes)],
        "notes": [to_markdown(n) for n in notes],
        "questions": to_markdown(questions) if questions else "",
        "markdown": to_markdown(document),
        "pdf": pdf_bytes,
        "stop_reason": stop_reason,
        "topics_done": len(notes),
        "topics_total": len(topics),
        "source": source,
        "duration": format_duration(time.monotonic() - started),
    }


def bar_fraction(done: int, total: int) -> float:
    return done / total if total else 0.0


# ---- CALLBACKS ----
def start_run():
    st.session_state.running = True
    st.session_state.error = None


def use_example():
    st.session_state.syllabus = EXAMPLE_SYLLABUS


def clear_result():
    st.session_state.result = None
    st.session_state.error = None


# ---- GUIDE CONTENT ----
def openrouter_key_steps():
    st.markdown(
        """
1. Open [openrouter.ai](https://openrouter.ai) and sign up with Google, GitHub or email. No card is needed for free models.
2. Go to [openrouter.ai/keys](https://openrouter.ai/keys).
3. Select **Create Key**, give it any name (for example "NoteForge"), and create it.
4. Copy the key straight away. It starts with `sk-or-` and is shown only once.
5. Paste it into the key box in step 1 on the **Create notes** tab.
"""
    )
    st.caption(
        "The key stays in your browser session. It is not saved by this app, and you "
        "will need to paste it again next time."
    )


def guide_tab(tavily_key: str):
    st.subheader("How it works")
    st.markdown(
        """
1. You paste a syllabus. The app splits it into topics.
2. For each topic it gathers facts from your textbook PDF if you uploaded one, otherwise from the web or the AI model's own knowledge.
3. It writes notes in a fixed exam format: Definition, Intuition, Detailed Explanation, Example, Key Points.
4. A second AI pass reviews each topic and asks for one rewrite if something is missing.
5. It adds important questions (2, 5 and 10 marks) and gives you a PDF.
"""
    )

    st.subheader("Get your free OpenRouter key")
    openrouter_key_steps()

    st.subheader("Write a syllabus that works well")
    st.markdown(
        """
- Put **one topic per line**.
- List subtopics after a colon, separated by commas. Each subtopic gets its own notes.
- Do **one unit at a time**. Free AI models limit how many requests you can make, and each topic uses several.
"""
    )
    st.code(EXAMPLE_SYLLABUS, language=None)

    st.subheader("For professors")
    st.markdown(
        """
- Upload the prescribed textbook so the notes follow your course material instead of general web content.
- Paste the syllabus exactly as it appears in the course plan, one unit per run.
- The notes are AI-generated and can contain mistakes. Review them before sharing with a class.
"""
    )

    st.subheader("Troubleshooting")
    with st.expander("It stopped with a rate limit message"):
        st.markdown(
            "Free models allow a limited number of requests per minute and per day. "
            "Topics that finished are kept, so download them, wait a minute, and run "
            "the remaining topics. You can also pick a different model in the sidebar."
        )
    with st.expander("OpenRouter can't serve this model (HTTP 402 or 404)"):
        st.markdown(
            "Free models are added and withdrawn often. Choose `openrouter/free` in the "
            "sidebar so OpenRouter picks one that is available. If the message mentions "
            "a data policy, open [OpenRouter privacy settings]"
            "(https://openrouter.ai/settings/privacy) and allow free model providers."
        )
    with st.expander("My PDF could not be read"):
        st.markdown(
            f"Scanned books (pages that are images) have no text to read, and "
            f"password-protected files cannot be opened. The limit is {MAX_UPLOAD_MB} MB; "
            f"for a large book, upload only the chapters for this unit."
        )
    with st.expander("The key was rejected"):
        st.markdown(
            "Check that you copied the whole key, that it starts with `sk-or-`, and that "
            "there are no spaces. If you lost it, create a new one; old keys cannot be viewed again."
        )

    st.subheader("If you host this app")
    with st.expander("Turn on web search with a Tavily key"):
        st.markdown(
            """
Web search is used when no textbook is uploaded. It needs one key, set by whoever runs the app:

1. Sign up at [tavily.com](https://tavily.com); there is a free plan.
2. Copy the API key from the dashboard at [app.tavily.com](https://app.tavily.com). It starts with `tvly-`.
3. Add it to the `.env` file in the project folder as `TAVILY_API_KEY=tvly-...` and restart the app.
"""
        )
        st.caption("Web search is on for this app." if tavily_key else "Web search is off for this app.")


# ---- RESULT ----
def show_result(result: dict):
    if result["stop_reason"]:
        st.warning(
            f"Stopped early: {result['stop_reason']} "
            f"{result['topics_done']} of {result['topics_total']} topics finished and are below."
        )
    else:
        st.success(f"Your notes are ready: {result['topics_total']} topics.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Topics", f"{result['topics_done']} of {result['topics_total']}")
    c2.metric("Source", result["source"])
    c3.metric("Time taken", result["duration"])

    d1, d2, d3 = st.columns(3)
    if result["pdf"]:
        d1.download_button(
            "Download PDF",
            result["pdf"],
            file_name="notes.pdf",
            mime="application/pdf",
            type="primary",
            icon=":material/picture_as_pdf:",
            on_click="ignore",
            width="stretch",
        )
    d2.download_button(
        "Download Markdown",
        result["markdown"],
        file_name="notes.md",
        mime="text/markdown",
        icon=":material/description:",
        on_click="ignore",
        width="stretch",
    )
    d3.button(
        "Start new notes",
        icon=":material/refresh:",
        on_click=clear_result,
        width="stretch",
    )
    if not result["pdf"]:
        st.warning("The PDF could not be created. The Markdown download still works.")

    st.caption("AI-generated notes can contain mistakes. Check them against your textbook.")

    labels = ["Notes"] + (["Important questions"] if result["questions"] else [])
    tabs = st.tabs(labels)
    with tabs[0]:
        for i, (topic, note) in enumerate(zip(result["topics"], result["notes"])):
            with st.expander(f"{i + 1}. {topic}", expanded=(i == 0)):
                st.markdown(note)
    if result["questions"]:
        with tabs[1]:
            st.markdown(result["questions"])


# ---- PAGE ----
st.set_page_config(page_title="NoteForge AI", page_icon=":material/menu_book:", layout="centered")

for key, default in (("running", False), ("error", None), ("result", None)):
    st.session_state.setdefault(key, default)

running = st.session_state.running
tavily_key = get_secret("TAVILY_API_KEY")

with st.sidebar:
    st.header("Settings")
    model = st.selectbox(
        "AI model",
        FREE_MODELS,
        key="model",
        disabled=running,
        accept_new_options=True,
        help=(
            "All listed models are free on OpenRouter. 'openrouter/free' picks whichever "
            "free model is available, which is the safest choice. You can also type any "
            "other OpenRouter model id."
        ),
    )
    model = (model or DEFAULT_MODEL).strip()

    st.divider()
    st.subheader("Where the facts come from")
    st.markdown(
        "1. **Your textbook PDF**, if you upload one\n"
        f"2. **Web search** ({'on' if tavily_key else 'off for this app'})\n"
        "3. **The AI model's own knowledge**"
    )
    st.caption("The first available source in this order is used.")

st.title("NoteForge AI")
st.caption(
    "Turn a syllabus into exam-ready notes with important questions, as a PDF. "
    "For students revising a unit and professors preparing handouts."
)

create_tab, help_tab = st.tabs(["Create notes", "Guide"])

with help_tab:
    guide_tab(tavily_key)

with create_tab:
    # -- Step 1: key --
    with st.container(border=True):
        st.markdown("**Step 1. Connect your free AI key**")
        api_key = st.text_input(
            "OpenRouter API key",
            type="password",
            key="api_key",
            disabled=running,
            placeholder="sk-or-...",
            help="Used only for this session. It is not stored or shared.",
        ).strip()

        if api_key and not api_key.startswith("sk-or-"):
            st.caption(":orange[:material/warning:] OpenRouter keys start with `sk-or-`. Check that you pasted the right key.")
        elif api_key:
            st.caption(":green[:material/check_circle:] Key added.")

        with st.expander("How do I get a key? It is free and takes about two minutes", expanded=not api_key):
            openrouter_key_steps()

    # -- Step 2: syllabus --
    with st.container(border=True):
        st.markdown("**Step 2. Paste your syllabus**")
        syllabus = st.text_area(
            "Syllabus",
            key="syllabus",
            height=170,
            max_chars=MAX_SYLLABUS_CHARS,
            disabled=running,
            placeholder=EXAMPLE_SYLLABUS,
            help="One topic per line. Write subtopics as 'Topic: Subtopic 1, Subtopic 2'.",
        )
        col_hint, col_example = st.columns([3, 1])
        col_hint.caption("One topic per line. Add subtopics after a colon, separated by commas. One unit at a time works best.")
        col_example.button("Use an example", on_click=use_example, disabled=running, width="stretch")

    # -- Step 3: book --
    with st.container(border=True):
        st.markdown("**Step 3. Add your textbook (optional)**")
        pdf_file = st.file_uploader(
            f"Textbook PDF, up to {MAX_UPLOAD_MB} MB",
            type=["pdf"],
            key="book",
            disabled=running,
            help="Scanned (image-only) and password-protected PDFs cannot be read.",
        )
        if pdf_file is not None:
            st.caption(":green[:material/check_circle:] Notes will be based on this book.")
        elif tavily_key:
            st.caption("Without a book, the notes are based on web search results.")
        else:
            st.caption("Without a book, the notes come from the AI model's own knowledge, so check them carefully.")

    st.button(
        "Generating..." if running else "Generate notes",
        type="primary",
        icon=":material/auto_awesome:",
        on_click=start_run,
        disabled=running,
        width="stretch",
    )

    if running:
        try:
            generate(syllabus, pdf_file, api_key, model, tavily_key)
        finally:
            st.session_state.running = False
        st.rerun()

    if st.session_state.error:
        st.error(st.session_state.error)

    if st.session_state.result:
        st.divider()
        show_result(st.session_state.result)
