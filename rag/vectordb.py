from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


def create_vectorstore(pdf_path: str):
    # -------- LOAD PDF --------
    loader = PyMuPDFLoader(pdf_path)
    documents = loader.load()

    # -------- SPLIT INTO CHUNKS --------
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=80
    )

    split_docs = splitter.split_documents(documents)

    # -------- EMBEDDINGS --------
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # -------- CREATE VECTORSTORE --------
    vectorstore = FAISS.from_documents(split_docs, embeddings)

    return vectorstore