from __future__ import annotations

import re
from typing import Any

import numpy as np

from src.schemas import Claim, EvidenceItem, EvidenceMatch


class EvidenceMatcher:
    """Match claims to evidence using lexical overlap and semantic similarity."""

    _stop_words = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "itself",
        "just",
        "me",
        "more",
        "most",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "now",
        "of",
        "on",
        "once",
        "only",
        "or",
        "other",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "she",
        "should",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        semantic_weight: float = 0.75,
        lexical_weight: float = 0.25,
        top_k: int = 3,
        minimum_score: float = 0.10,
    ) -> None:
        """Initialize the matcher and validate its configuration."""
        if semantic_weight < 0.0 or lexical_weight < 0.0:
            raise ValueError("Weights must be nonnegative.")
        if semantic_weight + lexical_weight <= 0.0:
            raise ValueError("Weights must sum to a value greater than zero.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError("minimum_score must be between 0.0 and 1.0.")

        self.model_name = model_name
        self.semantic_weight = semantic_weight / (semantic_weight + lexical_weight)
        self.lexical_weight = lexical_weight / (semantic_weight + lexical_weight)
        self.top_k = top_k
        self.minimum_score = minimum_score
        self._model: Any | None = None

    def _get_model(self) -> Any:
        """Load the sentence-transformer model lazily on first use."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _tokenize(self, text: str) -> set[str]:
        """Lowercase text, extract alphanumeric tokens, and drop common stop words."""
        tokens = re.findall(r"\b\d+(?:\.\d+)?\b|[a-z]+", text.lower())
        return {token for token in tokens if token not in self._stop_words}

    def _lexical_overlap(self, left: set[str], right: set[str]) -> float:
        """Return the Jaccard similarity between two token sets."""
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _semantic_similarity(self, claim_text: str, evidence_texts: list[str]) -> list[float]:
        """Encode claim and evidence in one batch and compute cosine similarity."""
        if not evidence_texts:
            return []

        model = self._get_model()
        texts = [claim_text, *evidence_texts]
        embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        claim_embedding = embeddings[0]
        evidence_embeddings = embeddings[1:]
        similarities: list[float] = []
        for embedding in evidence_embeddings:
            similarity = float(np.dot(claim_embedding, embedding))
            similarities.append(float(np.clip(similarity, 0.0, 1.0)))
        return similarities

    def match_claim(
        self,
        claim: Claim,
        evidence: list[EvidenceItem],
        top_k: int | None = None,
    ) -> list[EvidenceMatch]:
        """Return the best evidence matches for a single claim."""
        if not evidence:
            return []

        effective_top_k = self.top_k if top_k is None else max(1, top_k)
        claim_tokens = self._tokenize(claim.text)
        evidence_texts = [item.text for item in evidence]
        semantic_scores = self._semantic_similarity(claim.text, evidence_texts)

        matches: list[EvidenceMatch] = []
        for item, semantic_score in zip(evidence, semantic_scores):
            lexical_score = self._lexical_overlap(claim_tokens, self._tokenize(item.text))
            combined_score = (self.semantic_weight * semantic_score) + (self.lexical_weight * lexical_score)
            matches.append(
                EvidenceMatch(
                    evidence_id=item.evidence_id,
                    similarity_score=semantic_score,
                    lexical_overlap=lexical_score,
                    combined_score=combined_score,
                )
            )

        matches.sort(key=lambda match: (-match.combined_score, match.evidence_id))

        selected: list[EvidenceMatch] = []
        for match in matches:
            if match.combined_score >= self.minimum_score:
                selected.append(match)
                if len(selected) >= effective_top_k:
                    break

        cited_ids = {cid for cid in claim.cited_evidence_ids if cid}
        for match in matches:
            if match.evidence_id in cited_ids and match not in selected:
                selected.append(match)

        seen_ids: set[str] = set()
        deduped: list[EvidenceMatch] = []
        for match in sorted(selected, key=lambda item: (-item.combined_score, item.evidence_id)):
            if match.evidence_id in seen_ids:
                continue
            seen_ids.add(match.evidence_id)
            deduped.append(match)

        return deduped

    def match_claims(self, claims: list[Claim], evidence: list[EvidenceItem]) -> dict[str, list[EvidenceMatch]]:
        """Return evidence matches keyed by claim ID."""
        return {claim.claim_id: self.match_claim(claim, evidence) for claim in claims}
