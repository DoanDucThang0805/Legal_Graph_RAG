"""Reranker interfaces for retrieval candidates.

This module intentionally contains only lightweight abstractions and a no-op
fallback. Model-backed rerankers should live behind this interface and must not
be enabled implicitly from import-time code.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, TypeVar, runtime_checkable

CandidateT = TypeVar("CandidateT")


@runtime_checkable
class Reranker(Protocol[CandidateT]):
    """Base protocol for reranking retrieval candidates."""

    def rerank(self, question: str, candidates: Sequence[CandidateT]) -> list[CandidateT]:
        """Return candidates ordered by relevance to the question."""
        ...


class NoOpReranker:
    """Safe fallback reranker that preserves retrieval output exactly."""

    def rerank(self, question: str, candidates: Sequence[CandidateT]) -> list[CandidateT]:
        """Return candidates in their original order without external calls.

        The input sequence is copied into a new list so callers can mutate the
        returned container without changing the original container. Candidate
        objects themselves are kept unchanged to support dicts, Pydantic models,
        dataclasses, or retrieval hit objects without schema coupling.
        """

        return list(candidates)


def get_default_reranker() -> Reranker[Any]:
    """Return the default disabled reranker.

    Phase 7 starts with an explicit no-op fallback. Future model-backed
    rerankers should be selected by config in orchestration code, not here.
    """

    return NoOpReranker()
