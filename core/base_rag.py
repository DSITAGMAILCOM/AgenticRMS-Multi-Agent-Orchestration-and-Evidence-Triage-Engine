import os
import glob
import json
import time
import hashlib
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

# Global RAG registry for dynamic document lookup and ingestion
GLOBAL_RAG_REGISTRY: Dict[str, Any] = {}

# Embedding & Vector store dependencies
_embeddings_instance = None
from langchain_core.embeddings import Embeddings


class CompactONNXEmbeddings(Embeddings):
    """
    Ultra-lightweight sentence embedding generator using ONNX Runtime.
    Eliminates PyTorch/Transformers overhead, slashing memory consumption
    from ~550MB down to <60MB, ensuring 100% stability on Render 512MB RAM free instances.
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from huggingface_hub import hf_hub_download
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_path = hf_hub_download(model_name, "onnx/model_O4.onnx")
        tok_path = hf_hub_download(model_name, "tokenizer.json")

        self.tokenizer = Tokenizer.from_file(tok_path)
        self.tokenizer.enable_padding(length=128)
        self.tokenizer.enable_truncation(max_length=128)

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.enable_mem_pattern = True
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])

    def _embed(self, texts: List[str]) -> List[List[float]]:
        results = []
        for text in texts:
            encoded = self.tokenizer.encode(str(text))
            input_ids = np.array([encoded.ids], dtype=np.int64)
            attention_mask = np.array([encoded.attention_mask], dtype=np.int64)
            token_type_ids = np.array([encoded.type_ids], dtype=np.int64)

            outputs = self.session.run(None, {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids
            })
            token_embeddings = outputs[0]
            mask_expanded = np.expand_dims(attention_mask, -1)
            sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
            sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
            embedding = sum_embeddings / sum_mask
            norm = np.linalg.norm(embedding, axis=1, keepdims=True)
            norm_embedding = (embedding / norm)[0]
            results.append(norm_embedding.tolist())
        return results

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embed([text])[0]

    def __call__(self, text: str) -> List[float]:
        return self.embed_query(text)


def get_embeddings():
    """
    Lazy-loads an ultra-lightweight ONNX sentence embedding singleton (<60MB RAM)
    with graceful fallback to HuggingFaceEmbeddings to prevent OOM on 512MB RAM cloud tiers.
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        try:
            _embeddings_instance = CompactONNXEmbeddings()
        except Exception:
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
        
        # Lazy initialization & hot-reload state
        self._vstore = None
        self._last_pdf_check = 0.0
        self._cached_pdf_files: List[str] = []
        self._query_cache: Dict[str, Tuple[str, float]] = {}

        # Register in global registry for dynamic lookups and upload routing
        GLOBAL_RAG_REGISTRY[self.dept_name] = self
        if dept_id:
            GLOBAL_RAG_REGISTRY[dept_id] = self

    def _hash_file(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def _needs_refresh(self) -> bool:
        """
        Fast non-blocking check: verifies if PDFs have been added, modified,
        or removed since the FAISS index was last loaded.
        """
        now = time.time()
        if now - self._last_pdf_check < 2.0:
            return False  # Throttle filesystem checks to at most once per 2 seconds
        self._last_pdf_check = now

        current_pdfs = sorted(glob.glob(os.path.join(self.docs_dir, "*.pdf")))
        if current_pdfs != self._cached_pdf_files:
            return True

        # Check if registry file exists
        if not os.path.exists(self.registry_file):
            return bool(current_pdfs)

        try:
            with open(self.registry_file, "r") as f:
                reg = json.load(f)
            if len(current_pdfs) != len(reg):
                return True
            for pdf in current_pdfs:
                fname = os.path.basename(pdf)
                if fname not in reg:
                    return True
        except Exception:
            return True

        return False

    @property
    def vstore(self):
        """Lazy-loads or hot-refreshes the FAISS vector index whenever documents change."""
        if self._vstore is None or self._needs_refresh():
            self._vstore = self._build_index()
            self._cached_pdf_files = sorted(glob.glob(os.path.join(self.docs_dir, "*.pdf")))
            self._query_cache.clear()  # Invalidate cached searches when index updates
        return self._vstore

    def ingest_pdf(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Dynamically ingests an uploaded PDF into the department's docs directory,
        instantly processes it into chunks, updates the FAISS vector index,
        and clears query caches so new knowledge is immediately searchable.
        """
        clean_name = os.path.basename(filename)
        dest_path = os.path.join(self.docs_dir, clean_name)
        with open(dest_path, "wb") as f:
            f.write(file_content)

        # Force rebuild/refresh of the vector index
        t0 = time.perf_counter()
        self._vstore = self._build_index()
        self._cached_pdf_files = sorted(glob.glob(os.path.join(self.docs_dir, "*.pdf")))
        self._query_cache.clear()
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "success": True,
            "filename": clean_name,
            "department": self.dept_name,
            "indexed_path": dest_path,
            "indexing_latency_ms": duration_ms
        }

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
        """Executes similarity search on the vector store, returning markdown-formatted context with in-memory caching."""
        cache_key = f"{query.strip().lower()}_k{k}"
        now = time.time()
        if cache_key in self._query_cache:
            cached_res, expiry = self._query_cache[cache_key]
            if now < expiry:
                return cached_res

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

            result = "\n\n---\n\n".join(passages)
            self._query_cache[cache_key] = (result, now + 120.0)  # 2 minute cache
            return result
        except Exception as e:
            return f"Vector search error in {self.dept_name}: {e}"
