"""Assemble an explainable test plan; uncertainty always wins over narrowing."""

from copy import deepcopy
from dataclasses import dataclass, field
import math
from typing import Protocol

from pymongo.errors import PyMongoError

from .models import Document, GraphImpact


class RetrievalStore(Protocol):
    def search_tests(self, repo_id: str, base_sha: str, text: str, limit: int = 3) -> list[Document]: ...
    def search_runs(self, repo_id: str, text: str, limit: int = 3) -> list[Document]: ...
    def save_run(self, document: Document) -> None: ...


@dataclass
class TestPlan:
    candidates: list[Document] = field(default_factory=list)
    fallback_reasons: list[str] = field(default_factory=list)

    @property
    def full_suite(self) -> bool:
        return bool(self.fallback_reasons)


def _score(document: Document) -> bool:
    value = document.get("score")
    return isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1


def assemble_plan(impact: GraphImpact, retrieval: RetrievalStore) -> TestPlan:
    plan = TestPlan(fallback_reasons=list(impact.fallback_reasons))
    merged = {}

    def add(test_id, reason, *, node_id=None):
        if not isinstance(test_id, str) or not test_id or not reason:
            return
        candidate = merged.setdefault(test_id, {
            "test_id": test_id, "node_id": node_id, "path": test_id.split("::")[0], "reasons": [],
        })
        if reason not in candidate["reasons"]:
            candidate["reasons"].append(deepcopy(reason))

    for candidate in impact.candidates:
        for reason in candidate["reasons"]:
            add(candidate["test_id"], reason, node_id=candidate.get("node_id"))

    # Nothing can override a mandatory graph fallback. Avoid unnecessary queries.
    if not plan.full_suite:
        try:
            queried = set()
            for chunk in impact.changed_chunks:
                if chunk["kind"] != "code" or chunk["search_text"] in queried:
                    continue
                queried.add(chunk["search_text"])
                for match in retrieval.search_tests(impact.repo_id, impact.base_sha, chunk["search_text"][:12000], limit=3)[:3]:
                    if (match.get("repo_id") != impact.repo_id or match.get("base_sha") != impact.base_sha
                            or match.get("kind") != "test" or not _score(match) or not match.get("pytest_id")):
                        plan.fallback_reasons.append("invalid_retrieval_evidence")
                        continue
                    add(match["pytest_id"], {"kind": "semantic_match", "changed_path": chunk["path"],
                        "symbol": chunk.get("symbol"), "document_id": str(match["_id"]),
                        "score": match["score"]}, node_id=match.get("node_id"))
            query = "Changed paths: " + ", ".join(impact.changed_paths)
            query += "\n" + "\n".join(sorted(queried))
            for run in retrieval.search_runs(impact.repo_id, query[:12000], limit=3):
                if run.get("repo_id") != impact.repo_id or run.get("kind") != "pr_run" or not _score(run):
                    plan.fallback_reasons.append("invalid_retrieval_evidence")
                    continue
                for outcome in run.get("test_outcomes", []):
                    if outcome.get("outcome") in ("failed", "error"):
                        add(outcome.get("test_id"), {"kind": "prior_regression", "run_id": str(run["_id"]),
                                                   "score": run["score"]})
        except PyMongoError:
            plan.fallback_reasons.append("atlas_retrieval_failed")
        except (KeyError, TypeError, ValueError, AttributeError):
            plan.fallback_reasons.append("invalid_retrieval_evidence")
    plan.candidates = sorted(merged.values(), key=lambda c: c["test_id"])
    if not plan.candidates and not plan.full_suite:
        plan.fallback_reasons.append("no_defensible_candidates")
    plan.fallback_reasons = list(dict.fromkeys(plan.fallback_reasons))
    return plan
