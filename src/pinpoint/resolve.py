"""AST resolver: which library APIs does this code touch, and how does it call them?

Pure static analysis of the generated code; no library is imported here (the probe does that, in the
pinned venv). Precision over recall: anything it cannot trace to an import is simply not reported.

Handles: `import a.b [as x]`, `from a import b [as c]`, dotted attribute chains, calls with their
argument shape, and `v = lib.Class(...)` so that `v.method(...)` resolves to `lib.Class.method`.
Whether `lib.Class` really is a class (not a factory function) is checked later against the probe.
"""
import ast
from dataclasses import dataclass, field


@dataclass
class Use:
    path: str                       # canonical dotted path, e.g. "pandas.DataFrame.append"
    line: int
    kind: str                       # "import" | "call" | "attr"
    ctor: str | None = None         # set when reached through `v = ctor(...)`; path is then ctor + "." + attr
    n_pos: int = 0
    kwargs: list[str] = field(default_factory=list)
    star_args: bool = False
    star_kwargs: bool = False
    caught: frozenset = frozenset()  # exception names caught by enclosing try/except ("*" = bare/any)

    @property
    def root(self) -> str:
        return self.path.split(".")[0]


class _Resolver(ast.NodeVisitor):
    def __init__(self):
        self.aliases: dict[str, str] = {}      # local name -> dotted module/object path
        self.instances: dict[str, str] = {}    # local variable -> constructor path
        self.uses: list[Use] = []
        self.guards: list[frozenset] = []      # exceptions caught by the try blocks we are inside

    # -- imports
    def visit_Import(self, node):
        for a in node.names:
            if a.asname:
                self.aliases[a.asname] = a.name
            else:
                self.aliases[a.name.split(".")[0]] = a.name.split(".")[0]
            self.uses.append(Use(a.name, node.lineno, "import", caught=self._caught()))

    def visit_ImportFrom(self, node):
        if node.level or not node.module:
            return  # relative imports are local code
        for a in node.names:
            if a.name == "*":
                continue
            self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"
            self.uses.append(Use(f"{node.module}.{a.name}", node.lineno, "import", caught=self._caught()))

    # -- feature detection: code that catches the error itself is not judged by the diff
    def visit_Try(self, node):
        names = set()
        for h in node.handlers:
            if h.type is None:
                names.add("*")
            else:
                for t in (h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]):
                    names.add(t.attr if isinstance(t, ast.Attribute) else getattr(t, "id", "*"))
        self.guards.append(frozenset(names))
        for stmt in node.body:
            self.visit(stmt)
        self.guards.pop()
        for part in (*node.handlers, *node.orelse, *node.finalbody):
            self.visit(part)

    # -- parameters annotated with a library class: `def f(client: lib.Client)` makes `client` an instance
    def _function(self, node):
        added = []
        for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            if a.annotation is not None:
                r = self._chain(a.annotation)
                if r and r[1] is None:
                    self.instances[a.arg] = r[0]
                    added.append(a.arg)
                    self.uses.append(Use(r[0], a.lineno, "attr", caught=self._caught()))
        for stmt in node.body:
            self.visit(stmt)
        for name in added:
            self.instances.pop(name, None)

    visit_FunctionDef = visit_AsyncFunctionDef = _function

    def _caught(self) -> frozenset:
        return frozenset().union(*self.guards) if self.guards else frozenset()

    # -- name resolution
    def _chain(self, node) -> tuple[str, str | None] | None:
        """Resolve a Name/Attribute chain to (path, ctor). ctor is set for instance-based chains."""
        if isinstance(node, ast.Name):
            if node.id in self.instances:
                return self.instances[node.id], self.instances[node.id]
            if node.id in self.aliases:
                return self.aliases[node.id], None
            return None
        if isinstance(node, ast.Attribute):
            base = self._chain(node.value)
            if base is None:
                return None
            path, ctor = base
            return f"{path}.{node.attr}", ctor
        return None

    def _is_bare_instance(self, node) -> bool:
        return isinstance(node, ast.Name) and node.id in self.instances

    # -- statements / expressions
    def visit_Assign(self, node):
        self.visit(node.value)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            self.instances.pop(name, None)
            if isinstance(node.value, ast.Call):
                r = self._chain(node.value.func)
                if r and r[1] is None:  # constructed from an import, not from another instance
                    self.instances[name] = r[0]

    def visit_Call(self, node):
        r = self._chain(node.func)
        if r is not None and not self._is_bare_instance(node.func):
            path, ctor = r
            self.uses.append(Use(
                path, node.lineno, "call", ctor=ctor, caught=self._caught(),
                n_pos=sum(not isinstance(a, ast.Starred) for a in node.args),
                kwargs=[k.arg for k in node.keywords if k.arg],
                star_args=any(isinstance(a, ast.Starred) for a in node.args),
                star_kwargs=any(k.arg is None for k in node.keywords)))
        else:
            self.visit(node.func)
        for a in node.args:
            self.visit(a)
        for k in node.keywords:
            self.visit(k.value)

    def visit_Attribute(self, node):
        r = self._chain(node)
        if r is not None and not self._is_bare_instance(node):
            self.uses.append(Use(r[0], node.lineno, "attr", ctor=r[1], caught=self._caught()))
        else:
            self.generic_visit(node)


def resolve(code: str) -> list[Use]:
    """Library uses in `code`, in source order. Returns [] if the code does not parse."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    r = _Resolver()
    r.visit(tree)
    return r.uses
