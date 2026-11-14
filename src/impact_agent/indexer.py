"""Conservative file-level import graph plus source/test AST chunks."""

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath

from .gitrepo import read_python, resolve_commit, tree_files
from .models import Document, Snapshot
from .service_graph import SERVICE_MAP_PATH, service_relationships


class IndexingError(ValueError):
    pass


def stable_id(*parts: str) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True).encode()).hexdigest()


def is_test_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.startswith("test_") or name.endswith("_test.py")


def parse_python(source: str, path: str) -> ast.Module:
    try:
        return ast.parse(source, filename=path)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise IndexingError(f"Cannot parse Python: {path}") from exc


def _module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[0] == "src":
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _node(repo_id: str, sha: str, path: str, symbol: str, source: str,
          node_type: str, kind: str = "code", **extra) -> Document:
    node_id = stable_id(repo_id, path, symbol)
    return {
        "_id": stable_id(repo_id, sha, node_id), "node_id": node_id,
        "repo_id": repo_id, "base_sha": sha, "kind": kind,
        "path": path, "symbol": symbol, "node_type": node_type,
        "source_text": source, "search_text": f"{path} {symbol}\n{source}", **extra,
    }


def _chunks(repo_id: str, sha: str, path: str, source: str, tree: ast.Module):
    lines = source.splitlines(keepends=True)
    for item in tree.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        items = [(item, item.name, False)]
        if isinstance(item, ast.ClassDef):
            # Default pytest collection excludes classes with custom constructors.
            collect_class = item.name.startswith("Test") and not any(
                isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name in ("__init__", "__new__")
                for m in item.body
            )
            items += [(m, f"{item.name}.{m.name}", collect_class) for m in item.body
                      if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for obj, symbol, class_test in items:
            start = min([obj.lineno] + [d.lineno for d in obj.decorator_list])
            text = "".join(lines[start - 1:obj.end_lineno])
            test = is_test_file(path) and not isinstance(obj, ast.ClassDef) and obj.name.startswith("test_") and (
                "." not in symbol or class_test
            )
            extra = {"pytest_id": path + "::" + symbol.replace(".", "::")} if test else {}
            yield _node(repo_id, sha, path, symbol, text, "symbol", "test" if test else "code",
                        start_line=start, end_line=obj.end_lineno, **extra)


def _dependencies(tree: ast.Module, name: str, package: bool, modules: dict[str, str]):
    dependencies = set()
    for item in ast.walk(tree):
        names = []
        if isinstance(item, ast.Import):
            names = [alias.name for alias in item.names]
        elif isinstance(item, ast.ImportFrom):
            prefix = item.module or ""
            if item.level:
                parts = name.split(".") if package else name.split(".")[:-1]
                if item.level > len(parts):
                    continue
                prefix = ".".join(parts[:len(parts) - item.level + 1] + ([prefix] if prefix else []))
            names = [prefix] + [f"{prefix}.{alias.name}" if prefix else alias.name for alias in item.names]
        for imported in names:
            # Importing a submodule executes its package initializers too.
            parts = imported.split(".")
            for end in range(1, len(parts) + 1):
                candidate = ".".join(parts[:end])
                if candidate in modules:
                    dependencies.add(modules[candidate])
    return dependencies


def build_snapshot(repo: Path, repo_id: str, commit: str) -> Snapshot:
    """Build an immutable snapshot locally. No database writes or code execution."""
    sha = resolve_commit(repo, commit)
    nodes, parsed, modules = [], {}, {}
    files = tree_files(repo, sha)
    for path in tree_files(repo, sha, regular_only=False):
        if path.endswith(".py") and path not in files:
            raise IndexingError(f"Unsupported Python symlink: {path}")
    for path, oid in sorted(files.items()):
        if not path.endswith(".py"):
            continue
        try:
            source = read_python(repo, oid)
        except (UnicodeError, SyntaxError, LookupError) as exc:
            raise IndexingError(f"Cannot decode Python: {path}") from exc
        tree = parse_python(source, path)
        name = _module_name(path)
        if name in modules:
            raise IndexingError(f"Ambiguous Python module: {name}")
        modules[name] = path
        parsed[path] = tree
        nodes.append(_node(repo_id, sha, path, "<module>", source, "module"))
        nodes.extend(_chunks(repo_id, sha, path, source, tree))
    module_nodes = {n["path"]: n for n in nodes if n["node_type"] == "module"}
    edges = {}

    def add_edge(dependency: str, target: Document, edge_kind: str | None = None, **evidence):
        source_id = module_nodes[dependency]["node_id"]
        target_id = target["node_id"]
        kind = edge_kind or ("tested_by" if target["kind"] == "test" else "imports")
        eid = stable_id(repo_id, sha, source_id, target_id, kind)
        edges[eid] = {"_id": eid, "repo_id": repo_id, "base_sha": sha,
                      "source_id": source_id, "target_id": target_id, "kind": kind,
                      "source_path": dependency, "target_path": target["path"], **evidence}

    for path, tree in parsed.items():
        targets = [module_nodes[path]] + [n for n in nodes if n["path"] == path and n["kind"] == "test"]
        for dependency in sorted(_dependencies(tree, _module_name(path), path.endswith("/__init__.py"), modules)):
            if dependency == path:
                continue
            for target in targets:
                add_edge(dependency, target)
        if PurePosixPath(path).name == "conftest.py":
            parent = PurePosixPath(path).parent
            for target in nodes:
                if target["kind"] == "test" and PurePosixPath(target["path"]).is_relative_to(parent):
                    add_edge(path, target)
    try:
        for dependency, consumer in service_relationships(parsed.get(SERVICE_MAP_PATH), modules):
            add_edge(dependency, module_nodes[consumer], "service_call", evidence_path=SERVICE_MAP_PATH)
    except ValueError as exc:
        raise IndexingError(f"Invalid service registry: {exc}") from exc
    return Snapshot(repo_id, sha, nodes, sorted(edges.values(), key=lambda e: e["_id"]))
