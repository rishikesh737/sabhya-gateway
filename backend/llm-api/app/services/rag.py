import os
from typing import List, Optional, Tuple

import chromadb
import requests
import structlog
from pypdf import PdfReader

log = structlog.get_logger()

# Meta-question keywords that should bypass strict distance filtering
META_QUERY_KEYWORDS = [
    "summarize",
    "summary",
    "explain",
    "describe",
    "what is this",
    "tell me about",
    "overview",
    "look inside",
    "contents",
    "info about",
    "information about",
    "document",
    "file",
    "uploaded",
    "attached",
]


class LocalRAGService:
    def __init__(self):
        # NATIVE MODE: Use a local folder relative to this file's location
        self.db_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "chroma_data"
        )
        self.db_path = os.path.abspath(self.db_path)

        # Ensure directory exists
        os.makedirs(self.db_path, exist_ok=True)

        # Track uploaded files for context injection
        self.uploaded_files: List[str] = []
        self.last_uploaded_filename: Optional[str] = None
        self._last_sources: List[dict] = []  # Store sources from last query

        # Robust initialization with detailed error logging
        try:
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(
                name="user_documents", metadata={"hnsw:space": "cosine"}
            )
            log.info("chromadb_initialized", path=self.db_path)
        except Exception as e:
            log.error("chromadb_init_failed", error=str(e), path=self.db_path)
            raise RuntimeError(f"ChromaDB initialization failed: {e}")

        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Data directory for storing uploaded files
        self.data_dir = os.getenv("DATA_DIR", "./data")
        os.makedirs(self.data_dir, exist_ok=True)

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

        # SKIP RAG for simple greetings or very short queries
        # This prevents "Hello" from retrieving irrelevant resume context
        query_lower = query_text.lower().strip()
        greetings = [
            "hello",
            "hi",
            "hey",
            "greetings",
            "good morning",
            "good evening",
            "good afternoon",
        ]
        if (query_lower in greetings) or (len(query_text.split()) < 2 and not is_meta):
            log.info("rag_skipped_greeting", query=query_text)
            self._last_sources = []
            return [], ""

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
                include=["documents", "distances", "metadatas"],
            )

            raw_documents = results["documents"][0] if results["documents"] else []
            distances = results["distances"][0] if results.get("distances") else []
            metadatas = results["metadatas"][0] if results.get("metadatas") else []

            # DEBUG LOGGING - Critical for troubleshooting
            log.info(
                "rag_retrieval_debug",
                query=query_text[:50],
                num_chunks=len(raw_documents),
                distances=distances[:3] if distances else [],
                is_meta_query=is_meta,
            )

            # For meta-questions, return ALL retrieved chunks (don't filter by distance)
            # For specific queries, only filter out poor matches (distance > 0.5)
            if is_meta:
                # Meta-question: Force return all chunks found
                documents = raw_documents
                sources = metadatas
                log.info("rag_meta_query_force_return", chunks_returned=len(documents))
            else:
                # Specific query: Only return actually relevant matches
                # Cosine distance: 0 = identical, 1 = orthogonal, 2 = opposite
                # Using 0.5 threshold to ensure semantic relevance
                filtered = (
                    [
                        (doc, meta, dist)
                        for doc, meta, dist in zip(raw_documents, metadatas, distances)
                        if dist < 0.5  # Stricter threshold for relevance
                    ]
                    if distances
                    else [(doc, meta, 0) for doc, meta in zip(raw_documents, metadatas)]
                )
                documents = [x[0] for x in filtered]
                sources = [x[1] for x in filtered]

            # Build context note with filename info
            if self.last_uploaded_filename:
                context_note = f"Note: The user recently uploaded a file named '{self.last_uploaded_filename}'."
            if self.uploaded_files:
                all_files = ", ".join(self.uploaded_files)
                context_note += f" All uploaded files: {all_files}."

            log.info(
                "rag_query_complete",
                docs_returned=len(documents),
                has_context_note=bool(context_note),
            )

            # Store sources for retrieval
            self._last_sources = sources

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
        chunks = [
            text[i : i + chunk_size] for i in range(0, len(text), chunk_size - 100)
        ]

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

    def get_last_sources(self) -> List[dict]:
        """Return source metadata from the last query for citations."""
        return self._last_sources.copy()

    def delete_document(self, filename: str):
        """Removes a document from the vector store and disk."""
        try:
            print(f"[RAG] Attempting to delete: {filename}")

            # 1. Remove from ChromaDB (The Brain)
            self.collection.delete(where={"source": filename})

            # 2. Remove from Disk (The Storage)
            file_path = os.path.join(self.data_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[RAG] Deleted file from disk: {file_path}")
                return True
            else:
                print(f"[RAG] File not found on disk: {file_path}")
                # We return True if it's gone from disk (even if it was already gone)
                return True

        except Exception as e:
            print(f"[RAG] Error deleting document: {e}")
            return False


rag_service = LocalRAGService()
