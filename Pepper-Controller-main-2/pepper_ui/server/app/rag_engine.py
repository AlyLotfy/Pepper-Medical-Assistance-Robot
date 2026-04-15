# -*- coding: utf-8 -*-
"""
rag_engine.py - FAISS Retrieval-Augmented Generation Engine
============================================================
Embeds hospital knowledge chunks with sentence-transformers/all-MiniLM-L6-v2
and stores them in a FAISS IndexFlatL2 for sub-millisecond retrieval.

Usage (from app.py):
    from rag_engine import RAGEngine
    rag = RAGEngine()                         # loads or builds index
    context = rag.retrieve("chest pain", k=3) # returns top-3 chunks
"""

# Prevent Keras 3 / TF conflict when importing sentence-transformers
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")

import json
import numpy as np
import faiss

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_PATH = os.path.join(_DIR, "rag_corpus.json")
INDEX_PATH  = os.path.join(_DIR, "rag_index.faiss")
META_PATH   = os.path.join(_DIR, "rag_meta.json")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM        = 384          # output dim of all-MiniLM-L6-v2
DEFAULT_K            = 3            # top-k chunks per query
SIMILARITY_THRESHOLD = 1.6          # L2 distance cutoff (lower = more similar)


class RAGEngine:
    """
    Manages the full RAG lifecycle:
      1. Load corpus  ->  embed with sentence-transformers  ->  build FAISS index
      2. Persist index + metadata to disk
      3. At query time: embed query  ->  FAISS search  ->  return top-k chunks
    """

    def __init__(self, auto_load=True):
        self.index    = None          # faiss.IndexFlatL2
        self.metadata = []            # list of dicts parallel to index rows
        self.model    = None          # SentenceTransformer (lazy loaded)
        self._ready   = False

        if auto_load:
            self.load_or_build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_ready(self):
        return self._ready and self.index is not None and self.index.ntotal > 0

    def retrieve(self, query, lang="en", k=DEFAULT_K):
        """
        Retrieve the top-k most relevant corpus chunks for *query*.
        Returns a list of dicts: [{"id", "category", "text", "score"}, ...]
        Lower score = better match (L2 distance).
        """
        if not self.is_ready():
            return []

        self._ensure_model()
        q_vec = self.model.encode([query], normalize_embeddings=True)
        q_vec = np.array(q_vec, dtype="float32")

        distances, indices = self.index.search(q_vec, k)

        results = []
        for rank in range(k):
            idx  = int(indices[0][rank])
            dist = float(distances[0][rank])
            if idx < 0 or idx >= len(self.metadata):
                continue
            if dist > SIMILARITY_THRESHOLD:
                continue   # too dissimilar - skip
            meta = self.metadata[idx]
            # Pick the right language text
            text = meta.get("text_" + lang, meta.get("text_en", ""))
            results.append({
                "id":       meta.get("id", ""),
                "category": meta.get("category", ""),
                "text":     text,
                "score":    round(dist, 4),
            })
        return results

    def retrieve_context_string(self, query, lang="en", k=DEFAULT_K):
        """
        Convenience: returns a single string ready to inject into a
        Gemini system prompt.
        """
        chunks = self.retrieve(query, lang=lang, k=k)
        if not chunks:
            return ""
        lines = []
        for i, c in enumerate(chunks, 1):
            lines.append(f"[{i}] ({c['category']}) {c['text']}")
        return "\n".join(lines)

    def status(self):
        """Return a dict describing engine health."""
        return {
            "ready":        self.is_ready(),
            "total_chunks": self.index.ntotal if self.index else 0,
            "model":        EMBEDDING_MODEL_NAME,
            "embedding_dim": EMBEDDING_DIM,
            "index_path":   INDEX_PATH,
            "corpus_path":  CORPUS_PATH,
        }

    # ------------------------------------------------------------------
    # Index lifecycle
    # ------------------------------------------------------------------
    def load_or_build(self):
        """Load persisted index from disk, or build from corpus if missing."""
        if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
            try:
                self._load_index()
                print(f"[RAG] Loaded FAISS index: {self.index.ntotal} vectors from {INDEX_PATH}")
                self._ready = True
                return
            except Exception as e:
                print(f"[RAG] Failed to load index ({e}), rebuilding...")

        # Build from scratch
        if os.path.exists(CORPUS_PATH):
            self.build_index()
        else:
            print(f"[RAG] No corpus file at {CORPUS_PATH}. RAG disabled.")

    def build_index(self):
        """
        Read corpus JSON, embed all chunks, build + save FAISS index.
        Called once on first startup, or when corpus changes.
        """
        print("[RAG] Building FAISS index from corpus...")
        self._ensure_model()

        with open(CORPUS_PATH, "r", encoding="utf-8") as f:
            corpus = json.load(f)

        if not corpus:
            print("[RAG] Empty corpus. RAG disabled.")
            return

        # Combine EN + AR text for richer embeddings
        texts = []
        meta  = []
        for doc in corpus:
            combined = (doc.get("text_en", "") + " " + doc.get("text_ar", "")).strip()
            texts.append(combined)
            meta.append({
                "id":       doc.get("id", ""),
                "category": doc.get("category", ""),
                "text_en":  doc.get("text_en", ""),
                "text_ar":  doc.get("text_ar", ""),
            })

        # Encode all chunks
        print(f"[RAG] Encoding {len(texts)} chunks with {EMBEDDING_MODEL_NAME}...")
        embeddings = self.model.encode(texts, normalize_embeddings=True,
                                       show_progress_bar=False, batch_size=32)
        embeddings = np.array(embeddings, dtype="float32")

        # Build FAISS IndexFlatL2
        self.index = faiss.IndexFlatL2(EMBEDDING_DIM)
        self.index.add(embeddings)
        self.metadata = meta

        # Persist to disk
        self._save_index()
        self._ready = True
        print(f"[RAG] FAISS index built: {self.index.ntotal} vectors saved to {INDEX_PATH}")

    def rebuild(self):
        """Force rebuild (e.g. after corpus update)."""
        self._ready = False
        self.build_index()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_model(self):
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            print(f"[RAG] Loading embedding model: {EMBEDDING_MODEL_NAME}...")
            self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            print(f"[RAG] Embedding model loaded.")

    def _save_index(self):
        faiss.write_index(self.index, INDEX_PATH)
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False)

    def _load_index(self):
        self.index = faiss.read_index(INDEX_PATH)
        with open(META_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)


# ---------------------------------------------------------------------------
# CLI: run this file directly to (re)build the index
#   python rag_engine.py
#   python rag_engine.py --query "where is cardiology"
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    engine = RAGEngine(auto_load=False)
    engine.build_index()

    # Optional: test query
    if len(sys.argv) > 2 and sys.argv[1] == "--query":
        query = " ".join(sys.argv[2:])
        print(f"\nQuery: {query}")
        results = engine.retrieve(query, lang="en", k=3)
        for r in results:
            print(f"  [{r['score']:.4f}] {r['id']}: {r['text'][:120]}...")
    elif len(sys.argv) == 1:
        print("\nIndex built. Test with: python rag_engine.py --query \"chest pain\"")
