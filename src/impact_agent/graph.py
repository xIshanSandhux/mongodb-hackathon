"""GRAPH-2 handoff: changed chunks, affected nodes, candidates, and uncertainty."""

from collections import defaultdict, deque
from pathlib import Path
from typing import Protocol

from pymongo.errors import PyMongoError

from .gitrepo import changed_paths, read_python, resolve_commit, tree_files
from .indexer import IndexingError, _chunks, _node, is_test_file, parse_python
from .models import Document, GraphImpact
from .service_graph import SERVICE_MAP_PATH


class GraphStore(Protocol):
    def snapshot_status(self, repo_id: str, sha: str) -> str: ...
    def nodes(self, repo_id: str, sha: str, *, paths=None, node_ids=None) -> list[Document]: ...
    def graph_rows(self, repo_id: str, sha: str, roots: list[str]) -> list[Document]: ...


def _paths(root: str, edges: list[Document]):
    adjacency = defaultdict(list)
    for edge in edges:
        adjacency[edge["source_id"]].append(edge)
    queue = deque([(root, [], {root})])
    while queue:
        node, evidence, visited = queue.popleft()
        if len(evidence) == 2:
            continue
        for edge in sorted(adjacency[node], key=lambda e: (e["target_id"], e["kind"])):
            target = edge["target_id"]
            if target in visited:
                continue
            path = evidence + [{k: v for k, v in edge.items() if k not in ("_id", "depth")}]
            yield target, path
            queue.append((target, path, visited | {target}))


def analyze_graph(repo: Path, repo_id: str, base: str, head: str, store: GraphStore) -> GraphImpact:
    """Never executes tests. Person 3 must honor fallback_reasons before selection.

    Empty graph candidates alone do not force fallback here: vector search or
    prior-run memory may still produce evidence. The final selector owns that gate.
    Git errors are input errors and propagate to the caller.
    """
    base_sha, head_sha = resolve_commit(repo, base), resolve_commit(repo, head)
    result = GraphImpact(repo_id, base_sha, head_sha, changed_paths(repo, base_sha, head_sha))
    head_files = tree_files(repo, head_sha)
    all_head_files = tree_files(repo, head_sha, regular_only=False)
    base_files = tree_files(repo, base_sha)
    python_paths = [p for p in result.changed_paths if p.endswith(".py")]
    if SERVICE_MAP_PATH in python_paths:
        result.fallback_reasons.append("service_metadata_changed")
    head_tests = {}
    for path in python_paths:
        if path not in head_files:
            if path in all_head_files:
                result.fallback_reasons.append(f"unsupported_python: {path}")
                continue
            if path in base_files:
                continue  # A deleted module is traced using its base nodes below.
            result.fallback_reasons.append(f"unmapped_python: {path}")
            continue
        try:
            source = read_python(repo, head_files[path])
            tree = parse_python(source, path)
            chunks = list(_chunks(repo_id, head_sha, path, source, tree))
            # Module-level assignments also need semantic context.
            result.changed_chunks.append(_node(repo_id, head_sha, path, "<module>", source, "module"))
            result.changed_chunks.extend(chunks)
            if is_test_file(path):
                head_tests[path] = [n for n in chunks if n["kind"] == "test"]
        except (IndexingError, UnicodeError, SyntaxError, LookupError):
            result.fallback_reasons.append(f"cannot_parse_python: {path}")

    candidates = {}

    def add(test: Document, reason: Document):
        if test["path"] not in head_files:
            return
        # A changed file may have removed or renamed a base test.
        if test["path"] in head_tests and test["pytest_id"] not in {
            n["pytest_id"] for n in head_tests[test["path"]]
        }:
            return
        test_id = test["pytest_id"]
        candidate = candidates.setdefault(test_id, {
            "test_id": test_id, "node_id": test["node_id"], "path": test["path"], "reasons": [],
        })
        if reason not in candidate["reasons"]:
            candidate["reasons"].append(reason)

    for path, tests in head_tests.items():
        for test in tests:
            add(test, {"kind": "changed_test", "changed_path": path})

    try:
        status = store.snapshot_status(repo_id, base_sha)
        if status != "ready":
            result.fallback_reasons.append(f"{status}_base_snapshot")
        else:
            nodes = store.nodes(repo_id, base_sha, paths=python_paths)
            roots = {n["node_id"]: n for n in nodes if n["node_type"] == "module"}
            mapped = {n["path"] for n in roots.values()}
            for path in python_paths:
                if path not in mapped:
                    reason = f"unmapped_python: {path}"
                    if reason not in result.fallback_reasons:
                        result.fallback_reasons.append(reason)
            result.changed_chunks.extend(n for n in nodes if n["path"] not in head_files)
            paths = []
            graph_truncated = False
            for row in store.graph_rows(repo_id, base_sha, sorted(roots)):
                root = row["node_id"]
                reachable = row["reachable"]
                # Atlas returns depth 2 as the third edge. It is a lookahead:
                # candidates and explanations still use at most two edges.
                if any(edge.get("depth", -1) >= 2 for edge in reachable):
                    graph_truncated = True
                for target, evidence in _paths(root, reachable):
                    paths.append((target, {"kind": "graph", "changed_path": roots[root]["path"],
                                           "edges": evidence}))
            if graph_truncated:
                result.fallback_reasons.append("graph_truncated")
            affected = store.nodes(repo_id, base_sha, node_ids=sorted({target for target, _ in paths}))
            result.affected_nodes = sorted(affected, key=lambda n: n["node_id"])
            lookup = {n["node_id"]: n for n in affected}
            for target, reason in paths:
                if target in lookup and lookup[target]["kind"] == "test":
                    add(lookup[target], reason)
    except PyMongoError:
        result.fallback_reasons.append("atlas_retrieval_failed")
    result.candidates = sorted(candidates.values(), key=lambda c: c["test_id"])
    return result
