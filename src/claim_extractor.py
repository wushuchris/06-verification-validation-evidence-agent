from __future__ import annotations

import re
from typing import Tuple

from src.schemas import Claim


class ClaimExtractor:
    """Extracts factual claims from answer text using deterministic heuristics."""

    _citation_pattern = re.compile(r"\[(?P<ids>[A-Za-z0-9]+(?:\s*,\s*[A-Za-z0-9]+)*)\]")
    _abbreviations = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "u.s", "us"}

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentence-like fragments while preserving decimals and abbreviations."""
        if not text or not text.strip():
            return []

        fragments: list[str] = []
        start = 0
        for index, char in enumerate(text):
            if char in ".?!" and self._is_sentence_boundary(text, index):
                fragment = text[start : index + 1].strip()
                if fragment:
                    fragments.append(fragment)
                start = index + 1

        tail = text[start:].strip()
        if tail:
            fragments.append(tail)
        return fragments

    def _is_sentence_boundary(self, text: str, index: int) -> bool:
        """Return True when a punctuation mark is likely a sentence terminator."""
        char = text[index]
        if char == ".":
            if index > 0 and text[index - 1].isdigit() and index + 1 < len(text) and text[index + 1].isdigit():
                return False
            if index + 1 < len(text) and text[index + 1] and not text[index + 1].isspace():
                return False
            token = text[:index].split()[-1].lower().rstrip(".") if text[:index].split() else ""
            if token in self._abbreviations or token.replace(".", "") in self._abbreviations:
                return False
            return True

        if char in "?!":
            next_char = text[index + 1] if index + 1 < len(text) else ""
            return not next_char or next_char.isspace()

        return False

    def _clean_text(self, text: str) -> str:
        """Remove bullets, numbering, markdown headings, and surrounding whitespace."""
        cleaned_lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.match(r"^#{1,6}\s+", line):
                continue
            line = re.sub(r"^[-*+]\s+", "", line)
            line = re.sub(r"^\d+[.)]\s*", "", line)
            if line:
                cleaned_lines.append(line)
        return re.sub(r"\s+", " ", " ".join(cleaned_lines)).strip()

    def _extract_citations(self, text: str) -> Tuple[list[str], str]:
        """Extract citation IDs and remove citation markers from text."""
        citations: list[str] = []
        seen: set[str] = set()

        def replace(match: re.Match[str]) -> str:
            values = [item.strip() for item in match.group("ids").split(",") if item.strip()]
            for value in values:
                if value not in seen:
                    seen.add(value)
                    citations.append(value)
            return ""

        cleaned = self._citation_pattern.sub(replace, text)
        return citations, re.sub(r"\s+", " ", cleaned).strip()

    def extract(self, answer_text: str) -> list[Claim]:
        """Return a deterministic list of claims extracted from answer text."""
        if not answer_text or not answer_text.strip():
            return []

        claims: list[Claim] = []
        claim_index = 0
        for fragment in self._split_sentences(answer_text):
            cleaned = self._clean_text(fragment)
            if not cleaned or cleaned.endswith("?") or self._is_heading(cleaned):
                continue

            citations, text_without_citations = self._extract_citations(cleaned)
            if not text_without_citations:
                continue

            claim_index += 1
            claims.append(
                Claim(
                    claim_id=f"C{claim_index}",
                    text=text_without_citations,
                    cited_evidence_ids=citations,
                )
            )

        return claims

    def _is_heading(self, text: str) -> bool:
        """Ignore common headings that do not state a factual assertion."""
        stripped = text.strip()
        if not stripped:
            return True
        if stripped.startswith("#"):
            return True
        if re.fullmatch(r"[A-Za-z][A-Za-z\s-]{0,30}", stripped) and len(stripped.split()) <= 4:
            return True
        if re.fullmatch(r"(?:summary|overview|details|notes?|conclusion|result|results|background|evidence|context|appendix)\s*:?", stripped, re.I):
            return True
        return False
