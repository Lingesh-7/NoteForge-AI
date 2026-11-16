from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Cap how many chunks we embed per upload so one very large PDF can't blow up
# memory/time on a shared, resource-limited deployment (e.g. Streamlit Cloud free tier).
MAX_CHUNKS = 400


def load_embeddings() -> HuggingFaceEmbeddings:
    """Load the embedding model. Slow (downloads ~90 MB on first use), so the
    app caches the result and passes it to create_vectorstore."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )


def create_vectorstore(pdf_path: str, embeddings: HuggingFaceEmbeddings | None = None):
    """Build a FAISS index from a PDF. Raises ValueError if the PDF has no
    extractable text (e.g. a scanned book without OCR)."""
    documents = PyMuPDFLoader(pdf_path).load()
    documents = [d for d in documents if d.page_content.strip()]

    if not documents:
        raise ValueError(
            "No text could be extracted from this PDF. Scanned or image-only "
            "PDFs are not supported."
        )

    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=80)
    split_docs = splitter.split_documents(documents)[:MAX_CHUNKS]

    if not split_docs:
        raise ValueError("The uploaded PDF produced no usable text.")

    return FAISS.from_documents(split_docs, embeddings or load_embeddings())
