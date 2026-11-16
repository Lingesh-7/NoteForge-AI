# NoteForge-AI

NoteForge-AI is a multi-agent AI app that turns a syllabus into structured, exam-ready notes with important questions and a PDF export. It is built for students revising a unit and professors preparing handouts.

**Live app:** https://noteforge-ai-lingesh.streamlit.app/

---

## 🧠 Overview

For each topic in the syllabus, a chain of agents does the work:

1. **Planner** splits the syllabus into topics and subtopics.
2. **Researcher** gathers facts from your textbook PDF, from web search, or from the model's own knowledge.
3. **Writer** produces notes in a fixed format: Definition, Intuition, Detailed Explanation, Example, Key Points.
4. **Critic** reviews the notes and asks for one rewrite if something is missing.
5. **Exam agent** adds important questions (2, 5 and 10 marks) for the whole unit.

---

## 🏗️ Architecture

<p align="center">
  <img src="image.png" width="600"/>
</p>

---

## ✨ Features

- Multi-agent pipeline built with LangGraph
- Free to use: runs on free OpenRouter models, with a model picker
- Three sources of facts, used in this order:
  - Uploaded textbook PDF (RAG with FAISS and MiniLM embeddings)
  - Web search (Tavily), if the host has set a key
  - The AI model's own knowledge
- Guided three-step screen with an in-app guide to getting an API key
- Live progress: the current step, a percentage, and a per-topic checklist
- Finished topics are kept if a run stops early (for example on a rate limit)
- Download as PDF or Markdown
- Caching of research per topic and source

---

## 🔐 Keys

| Key | Who provides it | Where it goes |
|---|---|---|
| OpenRouter API key | Each user | Pasted into step 1 of the app. Used for that session only, never stored. |
| `TAVILY_API_KEY` | The app owner (optional) | `.env` in the project root. |

**Getting an OpenRouter key (free):**

1. Sign up at [openrouter.ai](https://openrouter.ai). No card is needed for free models.
2. Open [openrouter.ai/keys](https://openrouter.ai/keys) and select **Create Key**.
3. Copy the key (it starts with `sk-or-` and is shown only once) and paste it into the app.

**Turning on web search (optional, for the host):** sign up at [tavily.com](https://tavily.com), copy the key from the dashboard, and put it in `.env`:

```env
TAVILY_API_KEY=your_api_key
```

Without `TAVILY_API_KEY` the app still runs: notes come from the uploaded textbook, or from the model's own knowledge if there is none.

> ⚠️ Never commit `.env`. It is in `.gitignore`. The app reads keys from environment variables only; it does not use `secrets.toml`.

---

## 🛠️ Run locally

Needs Python 3.11 or newer.

```bash
git clone https://github.com/Lingesh-7/NoteForge-AI.git
cd NoteForge-AI
pip install -r requirements.txt
streamlit run app.py
```

With [uv](https://docs.astral.sh/uv/), use `uv sync` and then `uv run streamlit run app.py`.

---

## 🔄 Using the app

1. Paste your OpenRouter API key.
2. Paste the syllabus, one topic per line. Put subtopics after a colon, separated by commas:
   ```text
   Fuzzy sets: Membership functions, Operations on fuzzy sets
   Fuzzy inference: Mamdani method, Sugeno method
   Defuzzification
   ```
3. Upload the textbook PDF (optional, up to 25 MB).
4. Select **Generate notes** and follow the progress.
5. Download the PDF or Markdown.

The **Guide** tab in the app covers key setup, syllabus tips and troubleshooting.

---

## ☁️ Deploy on Streamlit Community Cloud

1. Push the repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io) choose **New app**, pick the repo, branch `main`, file `app.py`.
3. Under **Advanced settings** choose Python 3.13.
4. Optional, for web search: `.env` is not in the repo, so paste `TAVILY_API_KEY = "tvly-..."` into **Settings > Secrets**. Streamlit Cloud exposes it to the app as an environment variable.
5. Deploy.

Streamlit Cloud installs from `uv.lock`, which pins CPU-only PyTorch on Linux. To change a dependency, edit `pyproject.toml`, run `uv lock`, mirror the change in `requirements.txt`, and commit all three.

---

## 📁 Project Structure

```bash
.
├── app.py                  # Streamlit UI and run loop
├── graph/
│   ├── graph_builder.py    # LangGraph wiring
│   ├── nodes.py            # planner, researcher, writer, critic, exam agents
│   └── state.py
├── prompts/
│   └── prompts.py
├── rag/
│   └── vectordb.py         # PDF loading, embeddings, FAISS index
├── utils/
│   ├── cache.py
│   ├── helper.py
│   └── progress.py         # progress messages derived from the graph's routers
├── fonts/                  # DejaVu fonts for the PDF
├── .streamlit/
│   └── config.toml
├── pyproject.toml
├── uv.lock
├── requirements.txt
└── README.md
```

---

## ⚠️ Limitations

- Free OpenRouter models limit requests per minute and per day, and each topic uses several requests. Generate one unit at a time.
- Free models are added and withdrawn often. The default `openrouter/free` picks whichever is available, so quality can vary between runs.
- Scanned (image-only) and password-protected PDFs cannot be read. Only the first 400 text chunks of a book are indexed.
- Notes are AI-generated and can contain mistakes. Check them against the textbook.

---

## 🚀 Roadmap

- [x] Export to Markdown
- [ ] Better PDF styling and formatting
- [ ] Export to DOCX
- [ ] Semantic caching (vector reuse)
- [ ] Fast vs high-quality mode
- [ ] Evaluation metrics for generated notes

---

## 🤝 Contributing

Contributions, improvements and ideas are welcome. Feel free to open issues or submit pull requests.

---

## 📜 License

MIT License

---

## 💡 Motivation

Students spend hours converting scattered syllabus content into structured notes. NoteForge-AI automates that workflow.

---

## ⭐ Support

If you find this project useful, consider giving it a star ⭐
