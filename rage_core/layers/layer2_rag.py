"""
Layer 2 — RAG Threat Knowledge Base.

Embeds the threat KB at startup and scores incoming text by cosine similarity
against known attacks.

Embedder priority:
  1. sentence-transformers (local, better quality) if installed and RAGE_EMBEDDER=transformers
  2. TF-IDF (scikit-learn, zero download, zero API key) — DEFAULT offline path
  3. OpenAI embeddings if OPENAI_API_KEY is set and RAGE_EMBEDDER=openai

The vector store is a simple numpy cosine-similarity matrix (in-memory).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np

from rage_core.models import Layer2Signal

_KB_PATH = Path(__file__).parent.parent / "kb" / "threats.json"

# --------------------------------------------------------------------------- #
# Embedders                                                                    #
# --------------------------------------------------------------------------- #


class _TFIDFEmbedder:
    """Offline TF-IDF embedder — no downloads, no API keys required."""

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore

        self._vectorizer = TfidfVectorizer(sublinear_tf=True, max_features=4096)
        self._fitted = False

    def fit(self, texts: list[str]) -> None:
        self._vectorizer.fit(texts)
        self._fitted = True

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Call .fit() before .embed()")
        matrix = self._vectorizer.transform(texts)
        return matrix.toarray().astype(np.float32)  # type: ignore[return-value]


class _SentenceTransformerEmbedder:
    """Local sentence-transformers embedder (requires `sentence-transformers` package)."""

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(self.MODEL_NAME)

    def fit(self, texts: list[str]) -> None:  # noqa: ARG002
        pass  # pre-trained — no fitting needed

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)


class _OpenAIEmbedder:
    """OpenAI embeddings (requires OPENAI_API_KEY env var)."""

    MODEL_NAME = "text-embedding-3-small"

    def __init__(self) -> None:
        import openai  # type: ignore

        self._client = openai.OpenAI()

    def fit(self, texts: list[str]) -> None:  # noqa: ARG002
        pass

    def embed(self, texts: list[str]) -> np.ndarray:

        response = self._client.embeddings.create(input=texts, model=self.MODEL_NAME)
        vecs = np.array([d.embedding for d in response.data], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.clip(norms, 1e-9, None)


def _build_embedder() -> _TFIDFEmbedder | _SentenceTransformerEmbedder | _OpenAIEmbedder:
    mode = os.environ.get("RAGE_EMBEDDER", "tfidf").lower()
    if mode == "transformers":
        try:
            return _SentenceTransformerEmbedder()
        except ImportError:
            pass
    if mode == "openai" and os.environ.get("OPENAI_API_KEY"):
        try:
            return _OpenAIEmbedder()
        except ImportError:
            pass
    return _TFIDFEmbedder()


# --------------------------------------------------------------------------- #
# Vector store                                                                 #
# --------------------------------------------------------------------------- #


def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Return cosine similarity of a single query vector against each row in matrix."""
    q_norm = query / (np.linalg.norm(query) + 1e-9)
    m_norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
    m_normed = matrix / m_norms
    return (m_normed @ q_norm).astype(np.float32)


# --------------------------------------------------------------------------- #
# Threat KB Retriever                                                          #
# --------------------------------------------------------------------------- #


class ThreatKBRetriever:
    """Layer 2: RAG-based threat knowledge base.

    Scores a text string against all known attack patterns and returns the
    top-k most similar matches.
    """

    def __init__(self, top_k: int = 3, score_threshold: float = 0.25) -> None:
        self._top_k = top_k
        self._threshold = score_threshold
        self._threats: list[dict] = self._load_kb()
        self._embedder = _build_embedder()
        self._matrix: Optional[np.ndarray] = None
        self._build_index()

    # --- public API -------------------------------------------------------- #

    def score(self, text: str) -> Layer2Signal:
        """Return a Layer2Signal for the given text."""
        query_vec = self._embed_query(text)
        sims = _cosine_similarity(query_vec, self._matrix)
        top_idx = int(np.argmax(sims))
        top_sim = float(sims[top_idx])

        if top_sim < self._threshold:
            return Layer2Signal(score=top_sim)

        threat = self._threats[top_idx]
        return Layer2Signal(
            score=top_sim,
            top_match_id=threat["id"],
            top_match_category=threat["category"],
            top_match_technique=threat["technique"],
            owasp_id=threat["owasp_id"],
            severity=threat["severity"],
        )

    def add_threat(self, entry: dict) -> None:
        """Hot-update: add a new threat to the KB without retraining."""
        required = {"id", "category", "technique", "owasp_id", "severity", "text"}
        if not required.issubset(entry.keys()):
            raise ValueError(f"Threat entry must contain keys: {required}")
        self._threats.append(entry)
        self._build_index()  # re-embed the entire KB (small, so cheap)

    # --- private ----------------------------------------------------------- #

    @staticmethod
    def _load_kb() -> list[dict]:
        with open(_KB_PATH, encoding="utf-8") as fh:
            return json.load(fh)

    def _build_index(self) -> None:
        texts = [t["text"] for t in self._threats]
        self._embedder.fit(texts)
        self._matrix = self._embedder.embed(texts)

    def _embed_query(self, text: str) -> np.ndarray:
        return self._embedder.embed([text])[0]


_RETRIEVER: ThreatKBRetriever | None = None


def get_threat_kb_retriever() -> ThreatKBRetriever:
    """Shared KB retriever — index built once per process (benchmark speed)."""
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = ThreatKBRetriever()
    return _RETRIEVER
