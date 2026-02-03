import os
from typing import Optional, Tuple, List
import chromadb
from chromadb.config import Settings
import requests
from pypdf import PdfReader
import structlog

log = structlog.get_logger()

# Meta-question keywords that should bypass strict distance filtering
META_QUERY_KEYWORDS = [
    "summarize", "summary", "explain", "describe", "what is this",
    "tell me about", "overview", "look inside", "contents", "info about",
    "information about", "document", "file", "uploaded", "attached"
]


class LocalRAGService:
    def __init__(self):
        # NATIVE MODE: Use a local folder relative to this file's location
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_data")
        self.db_path = os.path.abspath(self.db_path)
        
        # Ensure directory exists
        os.makedirs(self.db_path, exist_ok=True)
        
        # Track uploaded files for context injection
        self.uploaded_files: List[str] = []
        self.last_uploaded_filename: Optional[str] = None
        
        # Robust initialization with detailed error logging
        try:
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(
                name="user_documents", 
                metadata={"hnsw:space": "cosine"}
            )
            log.info("chromadb_initialized", path=self.db_path)
        except Exception as e:
            log.error("chromadb_init_failed", error=str(e), path=self.db_path)
            raise RuntimeError(f"ChromaDB initialization failed: {e}")
        
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def _is_meta_query(self, query_text: str) -> bool:
        """Check if query is asking about the document itself (meta-question)."""
        query_lower = query_text.lower()
        return any(kw in query_lower for kw in META_QUERY_KEYWORDS)

    def query(self, query_text: str, n_results: int = 5) -> Tuple[List[str], str]:
        """
        Query the vector DB and return (documents, context_note).
        
        For meta-questions (summarize, explain, etc.), we force-return 
        top chunks regardless of distance score.
        """
        context_note = ""
        is_meta = self._is_meta_query(query_text)
        
        log.info("rag_query_start", query=query_text[:50], is_meta_query=is_meta)
        
        try:
            # Generate embedding via Ollama
            resp = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": query_text},
            )
            if resp.status_code != 200:
                log.error("ollama_embedding_failed", status=resp.status_code)
                if self.last_uploaded_filename:
                    context_note = f"Note: The user recently uploaded a file named '{self.last_uploaded_filename}'."
                return [], context_note
            
            query_vector = resp.json()["embedding"]
            
            # Query ChromaDB with increased n_results
            results = self.collection.query(
                query_embeddings=[query_vector], 
                n_results=n_results,
                include=["documents", "distances", "metadatas"]
            )
            
            raw_documents = results["documents"][0] if results["documents"] else []
            distances = results["distances"][0] if results.get("distances") else []
            
            # DEBUG LOGGING - Critical for troubleshooting
            log.info("rag_retrieval_debug", 
                     query=query_text[:50], 
                     num_chunks=len(raw_documents),
                     distances=distances[:3] if distances else [],
                     is_meta_query=is_meta)
            
            # AGGRESSIVE RETRIEVAL:
            # For meta-questions, return ALL retrieved chunks (don't filter by distance)
            # For specific queries, only filter out very poor matches (distance > 0.8)
            if is_meta:
                # Meta-question: Force return all chunks found
                documents = raw_documents
                log.info("rag_meta_query_force_return", chunks_returned=len(documents))
            else:
                # Specific query: Only filter very poor matches
                documents = [
                    doc for doc, dist in zip(raw_documents, distances)
                    if dist < 0.8  # Very permissive threshold
                ] if distances else raw_documents
            
            # Build context note with filename info
            if self.last_uploaded_filename:
                context_note = f"Note: The user recently uploaded a file named '{self.last_uploaded_filename}'."
            if self.uploaded_files:
                all_files = ", ".join(self.uploaded_files)
                context_note += f" All uploaded files: {all_files}."
            
            log.info("rag_query_complete", 
                     docs_returned=len(documents), 
                     has_context_note=bool(context_note))
            
            return documents, context_note
            
        except Exception as e:
            log.error("rag_query_failed", error=str(e))
            if self.last_uploaded_filename:
                context_note = f"Note: The user recently uploaded a file named '{self.last_uploaded_filename}'."
            return [], context_note

    def ingest_pdf(self, file_path: str, filename: str) -> int:
        """Ingest a PDF file into the vector database."""
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        chunk_size = 500
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size - 50)]
        
        log.info("processing_pdf", filename=filename, chunks=len(chunks))

        # Track this filename for context injection
        self.last_uploaded_filename = filename
        if filename not in self.uploaded_files:
            self.uploaded_files.append(filename)

        for i, chunk in enumerate(chunks):
            try:
                resp = requests.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": chunk},
                )
                if resp.status_code == 200:
                    vector = resp.json()["embedding"]
                    self.collection.add(
                        ids=[f"{filename}_{i}"],
                        embeddings=[vector],
                        documents=[chunk],
                        metadatas=[{"source": filename, "chunk_index": i}],
                    )
            except Exception as e:
                log.error("chunk_failed", error=str(e))

        log.info("pdf_ingested", filename=filename, total_chunks=len(chunks))
        return len(chunks)
    
    def get_uploaded_files(self) -> List[str]:
        """Return list of all uploaded filenames."""
        return self.uploaded_files.copy()


rag_service = LocalRAGService()
