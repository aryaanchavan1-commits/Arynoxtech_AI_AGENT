# MIT License
#
# Copyright (c) 2026 Aryan Chavan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""RAG retrieval utilities.

Implements a simple 3-stage retrieval pipeline:
1) Dense (semantic) retrieval using SentenceTransformers embeddings + cosine similarity.
2) Sparse (lexical) retrieval using BM25.
3) Re-ranking using a lightweight cross-encoder if available; otherwise uses
   a deterministic fallback score.

This module is designed to be optional and best-effort: if embeddings/cross-encoder
packages are missing, dense/sparse/rerank fall back gracefully.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class RetrievedChunk:
    content: str
    metadata: Dict[str, Any]
    dense_score: float
    bm25_score: float
    rerank_score: float


def _normalize_text(s: str) -> str:
    return " ".join((s or "").split())


def _try_import(name: str):
    try:
        return __import__(name)
    except Exception:
        return None


def _cosine_sim(a: Sequence[float], b: Sequence[float]) -> float:
    # assumes vectors are same length
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class RAGRetriever:
    """Dense + sparse retrieval with optional reranking."""

    def __init__(
        self,
        dense_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        cross_encoder_model: Optional[str] = None,
        rerank_top_k: int = 20,
    ) -> None:
        self.dense_model_name = dense_model
        self.cross_encoder_model = cross_encoder_model
        self.rerank_top_k = rerank_top_k

        # Dense setup
        self._st = _try_import("sentence_transformers")
        self._sentence_model = None
        if self._st is not None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._sentence_model = SentenceTransformer(self.dense_model_name)
            except Exception:
                self._sentence_model = None

        # Sparse setup
        self._rank_bm25 = _try_import("rank_bm25")
        self._bm25 = None

        # Rerank setup
        self._cross = None
        if self.cross_encoder_model:
            self._transformers = _try_import("transformers")
            if self._transformers is not None:
                try:
                    from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore

                    tok = AutoTokenizer.from_pretrained(self.cross_encoder_model)
                    mdl = AutoModelForSequenceClassification.from_pretrained(self.cross_encoder_model)
                    self._cross = (tok, mdl)
                except Exception:
                    self._cross = None

    def _dense_search(
        self,
        query: str,
        chunk_texts: List[str],
        top_k: int,
    ) -> List[Tuple[int, float]]:
        if not self._sentence_model:
            return []

        q_emb = self._sentence_model.encode([query], normalize_embeddings=True)[0]
        # Batch embeddings for chunks
        c_embs = self._sentence_model.encode(chunk_texts, normalize_embeddings=True)

        scored: List[Tuple[int, float]] = []
        for i, c_emb in enumerate(c_embs):
            scored.append((i, float(_cosine_sim(q_emb, c_emb))))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


    def _sparse_search(
        self,
        query: str,
        chunk_texts: List[str],
        top_k: int,
    ) -> List[Tuple[int, float]]:
        if self._rank_bm25 is None:
            return []

        from rank_bm25 import BM25Okapi  # type: ignore

        tokenized = [_normalize_text(t).lower().split() for t in chunk_texts]
        bm25 = BM25Okapi(tokenized)
        q_tokens = _normalize_text(query).lower().split()
        scores = bm25.get_scores(q_tokens)

        scored = [(i, float(s)) for i, s in enumerate(scores)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _rerank(
        self,
        query: str,
        candidates: List[Tuple[int, float, float]],
        chunk_texts: List[str],
        top_k: int,
    ) -> List[Tuple[int, float]]:
        """Return list (idx, rerank_score)"""

        # candidates: (idx, dense_score, bm25_score)
        reranked: List[Tuple[int, float]] = []

        # If cross encoder available, use it.
        if self._cross is not None:
            tok, mdl = self._cross
            try:
                import torch  # type: ignore

                mdl.eval()
                with torch.no_grad():
                    pairs = [(query, chunk_texts[i]) for i, _, _ in candidates]
                    texts_a = [p[0] for p in pairs]
                    texts_b = [p[1] for p in pairs]
                    enc = tok(texts_a, texts_b, padding=True, truncation=True, return_tensors="pt")
                    out = mdl(**enc)
                    # classification logits (assume single score)
                    logits = out.logits
                    if logits.ndim == 2 and logits.size(1) == 1:
                        vals = logits[:, 0]
                    else:
                        # take first column
                        vals = logits[:, 0] if logits.ndim == 2 else logits
                    vals = vals.detach().cpu().numpy().tolist()

                for (cand, (_, _, _)), score in zip(zip(candidates, candidates), vals):
                    # cand is tuple (idx,dense,bm25)
                    idx = cand[0]
                    reranked.append((idx, float(score)))
            except Exception:
                reranked = []

        if not reranked:
            # Deterministic fallback: weighted sum of dense and bm25
            # Candidates already limited.
            for idx, d, b in candidates:
                reranked.append((idx, 0.6 * d + 0.4 * b))

        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked[:top_k]

    def retrieve(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k_dense: int = 20,
        top_k_sparse: int = 20,
        top_k_final: int = 8,
    ) -> List[RetrievedChunk]:
        """chunks should include {content, metadata}."""

        if not chunks:
            return []

        chunk_texts = [_normalize_text(c.get("content", "")) for c in chunks]
        # Build dense + sparse top candidates
        dense_hits = self._dense_search(query, chunk_texts, top_k_dense)
        sparse_hits = self._sparse_search(query, chunk_texts, top_k_sparse)

        # Union candidates
        cand_map: Dict[int, Tuple[float, float]] = {}
        for idx, s in dense_hits:
            cand_map[idx] = (s, cand_map.get(idx, (0.0, 0.0))[1])
        for idx, s in sparse_hits:
            cand_map[idx] = (cand_map.get(idx, (0.0, 0.0))[0], s)

        candidates = [(i, d, b) for i, (d, b) in cand_map.items()]
        # If we have too few candidates and both search are missing,
        # fallback to lexical-only using naive substring counts.
        if not candidates:
            for i, t in enumerate(chunk_texts):
                d = 0.0
                b = t.lower().count(query.lower())
                candidates.append((i, d, b))

        # Limit candidates for rerank
        candidates.sort(key=lambda x: (x[1] + x[2]), reverse=True)
        candidates = candidates[: self.rerank_top_k]

        reranked = self._rerank(query, candidates, chunk_texts, top_k= min(top_k_final, len(candidates)))

        # Compose final objects
        results: List[RetrievedChunk] = []
        for idx, rr in reranked:
            d_score = 0.0
            b_score = 0.0
            for cand in candidates:
                if cand[0] == idx:
                    d_score = cand[1]
                    b_score = cand[2]
                    break
            results.append(
                RetrievedChunk(
                    content=chunks[idx].get("content", ""),
                    metadata=chunks[idx].get("metadata", {}),
                    dense_score=d_score,
                    bm25_score=b_score,
                    rerank_score=rr,
                )
            )

        return results

