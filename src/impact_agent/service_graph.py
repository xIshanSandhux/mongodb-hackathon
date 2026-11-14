"""Read the demo's explicit service registry as literals, never by importing it."""

import ast

SERVICE_MAP_PATH = "app/dependency_graph.py"


def _root(node):
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _reject_mutations(tree, wanted, declarations):
    aliases = set(wanted)
    alias_assignments = set()
    # Include direct aliases and aliases of entries, such as SERVICE_CALLS.
    for _ in range(len(tree.body)):
        for statement in tree.body:
            if isinstance(statement, ast.Assign) and _root(statement.value) in aliases:
                for target in statement.targets:
                    if isinstance(target, ast.Name) and target.id not in wanted:
                        aliases.add(target.id)
                        alias_assignments.add(statement)
    mutators = {"add", "update", "setdefault", "clear", "pop", "popitem", "remove", "discard",
                "append", "extend", "insert", "difference_update", "intersection_update", "symmetric_difference_update"}
    for statement in ast.walk(tree):
        if statement in declarations or statement in alias_assignments:
            continue
        targets = (statement.targets if isinstance(statement, (ast.Assign, ast.Delete))
                   else [statement.target] if isinstance(statement, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) else [])
        if any(_root(target) in aliases for target in targets):
            raise ValueError("Dynamic service registry mutation is unsupported")
        if (isinstance(statement, ast.Call) and isinstance(statement.func, ast.Attribute)
                and _root(statement.func.value) in aliases and statement.func.attr in mutators):
            raise ValueError("Dynamic service registry mutation is unsupported")
    for statement in tree.body:
        if statement in declarations or statement in alias_assignments or isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if any(isinstance(node, ast.Name) and node.id in aliases for node in ast.walk(statement)):
            raise ValueError("Dynamic service registry evaluation is unsupported")


def service_relationships(tree: ast.Module | None, modules: dict[str, str]):
    if tree is None:
        return []
    tables = {}
    declarations = set()
    wanted = {"SERVICE_MODULES", "SERVICE_DEPENDENTS"}
    for statement in tree.body:
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target] if isinstance(statement, ast.AnnAssign) else []
        for target in targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                declarations.add(statement)
                if target.id in tables:
                    raise ValueError("Duplicate service registry assignment")
                try:
                    tables[target.id] = ast.literal_eval(statement.value)
                except (ValueError, TypeError, SyntaxError, RecursionError) as exc:
                    raise ValueError("The service registry must use literal tables") from exc
    _reject_mutations(tree, wanted, declarations)
    if not tables:
        return []
    if set(tables) != wanted:
        raise ValueError("Incomplete service registry")
    registry, dependents = tables["SERVICE_MODULES"], tables["SERVICE_DEPENDENTS"]
    if not isinstance(registry, dict) or not isinstance(dependents, dict) or set(registry) != set(dependents):
        raise ValueError("Mismatched service registry tables")
    if not all(isinstance(name, str) and isinstance(module, str) and module in modules for name, module in registry.items()):
        raise ValueError("Unmapped service module")
    relationships = []
    for provider, consumers in dependents.items():
        if not isinstance(consumers, (set, list, tuple)) or not all(isinstance(name, str) and name in registry for name in consumers):
            raise ValueError("Unknown service consumer")
        for consumer in sorted(consumers):
            relationships.append((modules[registry[provider]], modules[registry[consumer]]))
    return relationships
