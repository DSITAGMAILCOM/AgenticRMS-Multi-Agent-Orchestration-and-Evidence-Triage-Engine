import os
import glob
import json
import hashlib
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

# Embedding & Vector store dependencies
_embeddings_instance = None

def get_embeddings():
    """Lazy-load shared HuggingFaceEmbeddings singleton to conserve memory."""
    global _embeddings_instance
    if _embeddings_instance is None:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            _embeddings_instance = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"}
            )
        except Exception:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            _embeddings_instance = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"}
            )
    return _embeddings_instance


class DepartmentVectorStore:
    """
    Department-level Vector Store managing localized document ingestion, FAISS indexing,
    and similarity search for faculties and specialized domains.
    """
    def __init__(self, faculty_id: str, dept_id: str, base_dir: str):
        self.faculty_id = faculty_id
        self.dept_id = dept_id
        self.dept_name = f"{faculty_id}/{dept_id}" if dept_id else faculty_id
        
        # Resolve document and index storage paths
        if dept_id:
            self.docs_dir = os.path.join(base_dir, "docs", dept_id)
            self.index_dir = os.path.join(base_dir, "indexes", dept_id)
        else:
            self.docs_dir = os.path.join(base_dir, "docs")
            self.index_dir = os.path.join(base_dir, "faiss_index")
            
        self.registry_file = os.path.join(self.index_dir, "registry.json")
        os.makedirs(self.docs_dir, exist_ok=True)
        os.makedirs(self.index_dir, exist_ok=True)
        
        self.vstore = self._build_index()

    def _hash_file(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def _build_index(self):
        """Constructs or updates the FAISS vector index from PDFs in docs_dir."""
        pdfs = glob.glob(os.path.join(self.docs_dir, "*.pdf"))
        index_file = os.path.join(self.index_dir, "index.faiss")

        # Fast exit if no documents and no cached index
        if not pdfs and not os.path.exists(index_file):
            return None

        from langchain_community.vectorstores import FAISS
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

        store = None
        if os.path.exists(index_file):
            try:
                embeddings = get_embeddings()
                store = FAISS.load_local(self.index_dir, embeddings, allow_dangerous_deserialization=True)
            except Exception:
                store = None

        if not pdfs:
            return store

        reg = {}
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r") as f:
                    reg = json.load(f)
            except Exception:
                reg = {}

        new_chunks = []
        cur_hashes = {}
        for pdf in pdfs:
            fname = os.path.basename(pdf)
            fhash = self._hash_file(pdf)
            cur_hashes[fname] = fhash

            if reg.get(fname) != fhash:
                extracted_pages = []
                # Attempt PyPDFLoader
                try:
                    from langchain_community.document_loaders import PyPDFLoader
                    loader = PyPDFLoader(pdf)
                    extracted_pages = [d for d in loader.load() if d.page_content.strip()]
                except Exception:
                    pass

                # Fallback to PDFPlumberLoader
                if not extracted_pages:
                    try:
                        from langchain_community.document_loaders import PDFPlumberLoader
                        loader = PDFPlumberLoader(pdf)
                        extracted_pages = [d for d in loader.load() if d.page_content.strip()]
                    except Exception:
                        pass

                if extracted_pages:
                    new_chunks.extend(splitter.split_documents(extracted_pages))

        if new_chunks:
            embeddings = get_embeddings()
            if store is None:
                store = FAISS.from_documents(new_chunks, embeddings)
            else:
                store.add_documents(new_chunks)
            store.save_local(self.index_dir)

        try:
            with open(self.registry_file, "w") as f:
                json.dump(cur_hashes, f, indent=2)
        except Exception:
            pass

        return store

    def search(self, query: str, k: int = 4) -> str:
        """Executes similarity search on the vector store, returning markdown-formatted context."""
        if not self.vstore:
            return f"No indexed syllabus/documents available for {self.dept_name}."

        try:
            docs = self.vstore.similarity_search(query, k=k)
            if not docs:
                return f"No matching passages found for '{query}' in {self.dept_name}."

            passages = []
            for d in docs:
                source = os.path.basename(d.metadata.get("source", "doc"))
                page = d.metadata.get("page", 0) + 1
                text = d.page_content.strip()
                passages.append(f"[{source} p.{page}]: {text}")

            return "\n\n---\n\n".join(passages)
        except Exception as e:
            return f"Vector search error in {self.dept_name}: {e}"


# Re-export RAGEngine for backwards compatibility
from core.rag_engine import RAGEngine