import os
import hashlib
import pickle
import traceback
from typing import List, Dict, Any, Tuple
import numpy as np

# Vector indexing
try:
    import faiss
except ImportError:
    faiss = None

# PDF extractors
try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from sentence_transformers import SentenceTransformer

class RAGEngine:
    def __init__(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: str = ".rag_cache",
        chunk_size: int = 500,
        chunk_overlap: int = 80
    ):
        self.cache_dir = cache_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        os.makedirs(self.cache_dir, exist_ok=True)

        try:
            self.model = SentenceTransformer(embedding_model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
        except Exception as e:
            raise RuntimeError(
                f"[RAG Init Error] Failed to load embedding model '{embedding_model_name}'. Details: {str(e)}\n"
                f"{traceback.format_exc()}"
            )

        self.index = None
        self.chunks_metadata: List[Dict[str, Any]] = []

    def _calculate_file_hash(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def extract_text_from_pdf(self, file_path: str) -> Tuple[bool, str, str]:
        if not os.path.exists(file_path):
            return False, "", f"[PDF Error] File not found at path: {file_path}"

        extracted_text = ""
        errors = []

        # Engine 1: pypdf
        if pypdf:
            try:
                reader = pypdf.PdfReader(file_path)
                for idx, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        extracted_text += f"\n--- Page {idx + 1} ---\n" + text
                if extracted_text.strip():
                    return True, extracted_text, ""
            except Exception as e:
                errors.append(f"pypdf extraction failed: {str(e)}")

        # Engine 2: pdfplumber fallback
        if pdfplumber:
            try:
                with pdfplumber.open(file_path) as pdf:
                    for idx, page in enumerate(pdf.pages):
                        text = page.extract_text()
                        if text:
                            extracted_text += f"\n--- Page {idx + 1} ---\n" + text
                if extracted_text.strip():
                    return True, extracted_text, ""
            except Exception as e:
                errors.append(f"pdfplumber extraction failed: {str(e)}")

        combined_error = " | ".join(errors) if errors else "No PDF library installed."
        return False, "", f"[Extraction Failure] Could not extract text from '{file_path}'. Log: {combined_error}"

    def chunk_document(self, text: str, source_doc: str) -> List[Dict[str, Any]]:
        chunks = []
        if not text or not text.strip():
            return chunks

        start = 0
        text_length = len(text)
        chunk_idx = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            
            # Sentence or newline boundary preservation
            if end < text_length:
                boundary = text.rfind("\n", start, end)
                if boundary == -1:
                    boundary = text.rfind(". ", start, end)
                if boundary != -1 and boundary > start + (self.chunk_size // 2):
                    end = boundary + 1

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "chunk_id": chunk_idx,
                    "source": source_doc,
                    "text": chunk_text,
                    "start_char": start,
                    "end_char": end
                })
                chunk_idx += 1

            start = end - self.chunk_overlap
            if start < 0 or start >= end:
                start = end

        return chunks

    def build_or_load_index(self, pdf_path: str, force_rebuild: bool = False) -> Dict[str, Any]:
        if not faiss:
            return {
                "success": False,
                "error": "FAISS library is missing. Install with: pip install faiss-cpu"
            }

        file_hash = self._calculate_file_hash(pdf_path)
        cache_index_path = os.path.join(self.cache_dir, f"{file_hash}.index")
        cache_meta_path = os.path.join(self.cache_dir, f"{file_hash}.pkl")

        # Load from cache if index already exists
        if not force_rebuild and os.path.exists(cache_index_path) and os.path.exists(cache_meta_path):
            try:
                self.index = faiss.read_index(cache_index_path)
                with open(cache_meta_path, "rb") as f:
                    self.chunks_metadata = pickle.load(f)
                return {
                    "success": True,
                    "cached": True,
                    "total_chunks": len(self.chunks_metadata),
                    "file_hash": file_hash
                }
            except Exception:
                pass  # Fall through to rebuild if cache is corrupt

        # 1. Extraction
        success, text, err = self.extract_text_from_pdf(pdf_path)
        if not success:
            return {"success": False, "stage": "PDF_EXTRACTION", "error": err}

        # 2. Chunking
        try:
            chunks = self.chunk_document(text, source_doc=os.path.basename(pdf_path))
            if not chunks:
                return {"success": False, "stage": "CHUNKING", "error": "Document contains no readable text."}
        except Exception as e:
            return {"success": False, "stage": "CHUNKING", "error": f"{str(e)}\n{traceback.format_exc()}"}

        # 3. Embedding Generation
        try:
            raw_texts = [c["text"] for c in chunks]
            embeddings = self.model.encode(raw_texts, show_progress_bar=False, normalize_embeddings=True)
            embeddings = np.array(embeddings, dtype="float32")
        except Exception as e:
            return {"success": False, "stage": "EMBEDDING_GENERATION", "error": f"{str(e)}\n{traceback.format_exc()}"}

        # 4. Indexing & Cache Storage
        try:
            index = faiss.IndexFlatIP(self.dimension)
            index.add(embeddings)
            
            faiss.write_index(index, cache_index_path)
            with open(cache_meta_path, "wb") as f:
                pickle.dump(chunks, f)

            self.index = index
            self.chunks_metadata = chunks

            return {
                "success": True,
                "cached": False,
                "total_chunks": len(chunks),
                "file_hash": file_hash
            }
        except Exception as e:
            return {"success": False, "stage": "FAISS_INDEXING", "error": f"{str(e)}\n{traceback.format_exc()}"}

    def query(self, query_text: str, top_k: int = 3) -> Dict[str, Any]:
        if self.index is None or not self.chunks_metadata:
            return {
                "success": False,
                "error": "No indexed document found. Ingest a document PDF first."
            }

        try:
            q_emb = self.model.encode([query_text], normalize_embeddings=True)
            q_emb = np.array(q_emb, dtype="float32")

            distances, indices = self.index.search(q_emb, top_k)
            
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx != -1 and idx < len(self.chunks_metadata):
                    meta = self.chunks_metadata[idx]
                    results.append({
                        "score": float(dist),
                        "chunk_id": meta["chunk_id"],
                        "source": meta["source"],
                        "text": meta["text"]
                    })

            return {"success": True, "results": results}
        except Exception as e:
            return {
                "success": False,
                "error": f"Vector retrieval error: {str(e)}\n{traceback.format_exc()}"
            }