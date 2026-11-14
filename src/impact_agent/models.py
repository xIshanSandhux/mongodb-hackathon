"""Shared GRAPH-1/GRAPH-2 return types; documents remain plain BSON-ready dicts."""

from dataclasses import dataclass, field
from typing import Any

Document = dict[str, Any]


@dataclass
class Snapshot:
    repo_id: str
    base_sha: str
    nodes: list[Document]
    edges: list[Document]


@dataclass
class GraphImpact:
    repo_id: str
    base_sha: str
    head_sha: str
    changed_paths: list[str] = field(default_factory=list)
    changed_chunks: list[Document] = field(default_factory=list)
    candidates: list[Document] = field(default_factory=list)
    affected_nodes: list[Document] = field(default_factory=list)
    fallback_reasons: list[str] = field(default_factory=list)

    @property
    def requires_full_suite(self) -> bool:
        return bool(self.fallback_reasons)
