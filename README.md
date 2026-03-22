# NoteForge-AI

An intelligent, agent-based note generation system that converts syllabus content into structured, downloadable PDF notes.

---

## 🛠️ Installation

```bash
git clone https://github.com/your-username/NoteForge-AI.git
cd NoteForge-AI
pip install -r requirements.txt
```

---

## 🔐 Environment Setup

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_api_key
TAVILY_API_KEY=your_api_key
```

> ⚠️ **Important:** Never commit `.env` to GitHub. Ensure it is added to `.gitignore`.

---

## ▶️ Usage

Run the application:

```bash
streamlit run app.py
```

---

## 🔄 Workflow

```text
1. Enter the syllabus
2. Upload reference PDF (optional)
3. Click Generate Notes
4. Download the structured PDF
```

---

## 📁 Project Structure

```bash
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

## 📊 Design Highlights

```text
- Modular agent-based architecture (extensible)
- Separation of reasoning, retrieval, and generation
- Iterative refinement improves output quality
- Works with incomplete or minimal input
```

---

## ⚠️ Limitations

```text
- Dependent on LLM API rate limits
- Output quality depends on input clarity
- Large syllabi may increase runtime
```

---

## 🚀 Roadmap

```text
[ ] Advanced PDF styling & formatting
[ ] Semantic caching (vector reuse)
[ ] Export to DOCX / Markdown
[ ] Configurable agent strategies (fast vs high-quality)
[ ] Evaluation metrics for generated notes
```

---

## 🤝 Contributing

```text
Contributions, improvements, and ideas are welcome.
Feel free to open issues or submit pull requests.
```

---

## 📜 License

```text
MIT License
```

---

## 💡 Motivation

```text
Students spend hours converting scattered syllabus content into structured notes.
NoteForge-AI automates that entire workflow intelligently.
```

---

## ⭐ Support

```text
If you find this project useful, consider giving it a star ⭐
```
