Here’s a **clean, professional, GitHub-ready `README.md`** version of your project. I’ve improved structure, clarity, formatting, and added slight polish so it looks like a serious AI project (resume-worthy + recruiter-friendly).

---

````markdown
# 🚀 NoteForge-AI

Generate **structured, exam-ready notes** from a syllabus using a **multi-agent AI system**.

---

## 📌 Overview

**NoteForge-AI** converts a syllabus (and optionally a reference book PDF) into:

- 📖 Structured topic-wise notes  
- 🧠 Clear explanations (definitions, intuition, examples)  
- 📝 Unit-level important exam questions  
- 📄 Downloadable, well-formatted PDF  

It leverages a **multi-agent workflow** to plan, research, write, review, and refine content automatically.

---

## ⚙️ Features

- 🤖 Multi-agent architecture (LangGraph)
- 📚 Works with:
  - Uploaded PDF (RAG-based)
  - Web search fallback (Tavily)
- 🔁 Self-improving notes using critic loop
- 🎯 Exam-focused structured output
- 🧩 Unit-level important questions
- 📄 PDF export support
- ⚡ Caching for faster repeated runs

---

## 🧠 Architecture

![Architecture](image.png)

---

## 🔄 Workflow

1. **Planner** → Breaks syllabus into structured topics
2. **Researcher** → Fetches content (PDF / Web)
3. **Writer** → Generates notes
4. **Critic** → Improves quality (loop until pass)
5. **Exam Agent** → Creates important questions
6. **Topic Loop** → Iterates for all topics
7. **Final Generator** → Combines everything
8. **Formatter** → Produces clean PDF

---

## 🧰 Tech Stack

* **LangGraph** – Agent workflow orchestration
* **LangChain** – LLM pipelines
* **Groq** – LLM inference
* **FAISS** – Vector database
* **Sentence Transformers** – Embeddings
* **PyMuPDF** – PDF parsing
* **Tavily** – Web search
* **Streamlit** – UI
* **FPDF** – PDF generation

---

## 📦 Installation

```bash
git clone https://github.com/your-username/noteforge-ai.git
cd noteforge-ai

pip install -r requirements.txt
```

---

## 🔐 Environment Variables

Create a `.env` file:

```env
GROQ_API_KEY=your_api_key
TAVILY_API_KEY=your_api_key
```

> Alternatively, you can enter the Groq API key directly in the UI.

---

## ▶️ Usage

```bash
streamlit run app.py
```

### Steps

1. Enter syllabus
2. (Optional) Upload book PDF
3. Click **Generate Notes**
4. Download PDF

---

## 📁 Project Structure

```
.
├── app.py
├── graph/
│   ├── nodes.py
│   ├── graph_builder.py
│   └── state.py
├── prompts/
├── rag/
├── utils/
├── fonts/
├── requirements.txt
└── README.md
```

---

## 📝 Notes

* Uses PDF as primary source (if provided)
* Falls back to web search otherwise
* Caching reduces API calls
* Critic loop ensures output quality

---

## ⚠️ Limitations

* API rate limits may affect long runs
* Output quality depends on input content
* Large syllabus may require multiple runs

---

## 🚀 Future Improvements

* 🎨 Better PDF styling
* 🧠 Semantic caching
* 📤 Export to DOCX / Markdown
* ⚡ Fast vs Quality mode

---

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

---

## 📜 License

MIT License

---

## 💡 Inspiration

Built to solve a real student problem:

> Turning messy syllabus content into structured, exam-ready notes efficiently.

---

```

---
