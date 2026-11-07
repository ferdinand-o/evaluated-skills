"""Prototyp: Gegenstellen der geaenderten Python-Zeilen eines Git-Bereichs sammeln.

Aufruf: counterparts.py <repo> <bereich> [--root src] [--max-bytes 60000]

Je geaenderter Stelle, rein mechanisch:
- Aufruf auf einer geaenderten Zeile -> Definition der Gegenstelle (auch vendorter Code),
  Signatur und die Ausnahmen, die sie wirft (transitiv im selben Modul, Tiefe 2).
- geaenderte except-Klausel -> Ausnahmen aller Aufrufe im zugehoerigen try-Block.
- geaendertes Schluesselwort-Argument -> Weg des Parameters durch die Gegenstellen
  (Weitergabe als Schluesselwort, Tiefe 4) und die Bedingungen, die ihn pruefen.
Nur Stdlib, nie import des Zielcodes.
"""
import argparse
import ast
import pathlib
import re
import subprocess
import sys
from collections import defaultdict

MAX_DEFS = 2


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True,
                          text=True).stdout


def changed_lines(repo, rng, root):
    out = git(repo, "diff", "-U0", rng, "--", f"{root}/*.py", f"{root}/**/*.py")
    files, cur = defaultdict(set), None
    for line in out.splitlines():
        if line.startswith("+++ "):
            cur = None if line.endswith("/dev/null") else line[6:]
        elif line.startswith("@@") and cur:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start, count = int(m.group(1)), int(m.group(2) or 1)
            files[cur].update(range(start, start + count))
    return {f: ls for f, ls in files.items() if ls}


class Index:
    """Alle Definitionen unter root: name -> [(datei, qualname, node)]."""

    def __init__(self, repo, root):
        self.repo = pathlib.Path(repo)
        self.defs = defaultdict(list)
        self.trees = {}
        for p in sorted((self.repo / root).rglob("*.py")):
            rel = p.relative_to(self.repo).as_posix()
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            self.trees[rel] = tree
            for cls, node in walk_defs(tree):
                q = f"{cls}.{node.name}" if cls else node.name
                self.defs[node.name].append((rel, q, node))
                if isinstance(node, ast.ClassDef):
                    for b in node.body:
                        if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and b.name == "__init__":
                            self.defs[node.name].append((rel, f"{node.name}.__init__", b))

    def module_file(self, module):
        base = module.replace(".", "/")
        for cand in (f"src/{base}.py", f"src/{base}/__init__.py", f"{base}.py", f"{base}/__init__.py"):
            if cand in self.trees:
                return cand
        return None


def walk_defs(tree):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield None, node
        elif isinstance(node, ast.ClassDef):
            yield None, node
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield node.name, b


def imports_of(tree):
    """Modulpfade, die eine Datei importiert (auch Importe in Funktionen)."""
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
            for a in n.names:
                mods.add(f"{n.module}.{a.name}")
        elif isinstance(n, ast.Import):
            for a in n.names:
                mods.add(a.name)
    return mods


def import_prefixes(index, rel):
    """Dateien/Pakete, aus denen eine Datei tatsaechlich Namen bezieht (spezifischster Pfad)."""
    tree = index.trees.get(rel)
    out = set()
    if tree is None:
        return out

    def add(f):
        out.add(f.rsplit("/", 1)[0] + "/" if f.endswith("__init__.py") else f)

    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                f = index.module_file(f"{n.module}.{a.name}") or index.module_file(n.module)
                if f:
                    add(f)
        elif isinstance(n, ast.Import):
            for a in n.names:
                f = index.module_file(a.name)
                if f and "." in a.name:
                    add(f)
    return out


def callee_name(call):
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def resolve_call(index, call, from_file):
    """Wie resolve, aber ein voll qualifizierter Modulpfad (a.b.c.Name) entscheidet zuerst."""
    name = callee_name(call)
    if isinstance(call.func, ast.Attribute):
        mod = dotted(call.func.value)
        f = index.module_file(mod) if mod and "." in mod else None
        if f:
            exact = [c for c in index.defs.get(name, []) if c[0] == f]
            if exact:
                return exact[:MAX_DEFS]
    return resolve(index, name or "", from_file)


def resolve(index, name, from_file):
    """Definitionen zu einem Namen, bevorzugt: gleiche Datei, importierte Module/Pakete."""
    cands = index.defs.get(name, [])
    if not cands:
        return []
    prefixes = import_prefixes(index, from_file)

    def rank(c):
        rel = c[0]
        if rel == from_file:
            return 0
        if any(rel == p or rel.startswith(p) for p in prefixes):
            return 1
        return 2

    ranked = sorted(cands, key=rank)
    best = rank(ranked[0])
    if best == 2 and len(cands) > 3:
        return []  # ohne Importbezug und mehrdeutig: lieber nichts als Raten
    return [c for c in ranked if rank(c) == best][:MAX_DEFS]


def signature(node):
    if isinstance(node, ast.ClassDef):
        return f"class {node.name}"
    return f"def {node.name}({ast.unparse(node.args)})"


def raises_in(index, rel, node, depth=2, seen=None):
    """(Typ, Datei:Zeile) aller raise in node, transitiv ueber Aufrufe im selben Modul."""
    seen = seen or set()
    key = (rel, node.lineno)
    if key in seen:
        return []
    seen.add(key)
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Raise) and n.exc is not None:
            exc = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            out.append((ast.unparse(exc), f"{rel}:{n.lineno}"))
        elif depth > 0 and isinstance(n, ast.Call):
            name = callee_name(n)
            for d in index.defs.get(name or "", []):
                if d[0] == rel and isinstance(d[2], (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out += raises_in(index, rel, d[2], depth - 1, seen)
    return out


def param_flow(index, rel, fn, param, depth=4, seen=None):
    """Wo landet ein Parameter: Bedingungen, die ihn pruefen, und Weitergaben."""
    seen = seen or set()
    if depth == 0 or (rel, fn.lineno, param) in seen:
        return []
    seen.add((rel, fn.lineno, param))
    lines = []
    src = index.trees.get(rel)
    for n in ast.walk(fn):
        if isinstance(n, (ast.If, ast.IfExp, ast.While)) and any(
                isinstance(x, ast.Name) and x.id == param for x in ast.walk(n.test)):
            body = n.body if isinstance(n.body, list) else [n.body]
            snippet = ast.unparse(n.test)
            first = ast.unparse(body[0]).splitlines()[0] if body else ""
            lines.append(f"{rel}:{n.lineno}: if {snippet}: {first}")
        if isinstance(n, ast.Call):
            for kw in n.keywords:
                if isinstance(kw.value, ast.Name) and kw.value.id == param and kw.arg:
                    name = callee_name(n)
                    for drel, q, d in resolve_call(index, n, rel):
                        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            lines.append(f"{rel}:{n.lineno}: {param} -> {q}({kw.arg}=...) [{drel}:{d.lineno}]")
                            lines += param_flow(index, drel, d, kw.arg, depth - 1, seen)
    return lines


def enclosing_def(tree, lineno):
    best = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= lineno <= n.end_lineno:
            if best is None or n.lineno >= best.lineno:
                best = n
    return best


def collect(repo, rng, root):
    index = Index(repo, root)
    report = []
    for rel, lines in sorted(changed_lines(repo, rng, root).items()):
        tree = index.trees.get(rel)
        if tree is None:
            continue
        done = set()
        for n in ast.walk(tree):
            # geaenderte except-Klausel: was kann der try-Block werfen?
            if isinstance(n, ast.Try):
                for h in n.handlers:
                    if h.lineno in lines:
                        found = []
                        for c in ast.walk(ast.Module(body=n.body, type_ignores=[])):
                            if isinstance(c, ast.Call):
                                for drel, q, d in resolve_call(index, c, rel):
                                    rs = raises_in(index, drel, d)
                                    if rs:
                                        found.append((q, drel, d, rs))
                        caught = ast.unparse(h.type) if h.type else "alles"
                        entry = [f"### {rel}:{h.lineno} except {caught}"]
                        for q, drel, d, rs in found:
                            types = sorted({t for t, _ in rs})
                            entry.append(f"- try-Block ruft {q} [{drel}:{d.lineno}] -> wirft {', '.join(types)}")
                            entry += [f"    raise {t} at {w}" for t, w in rs[:8]]
                        if found:
                            report.append("\n".join(entry))
            if not isinstance(n, ast.Call) or not (set(range(n.lineno, n.end_lineno + 1)) & lines):
                continue
            name = callee_name(n)
            if not name or (rel, n.lineno, name) in done:
                continue
            done.add((rel, n.lineno, name))
            defs = resolve_call(index, n, rel)
            if not defs:
                continue
            changed_kw = [kw for kw in n.keywords if kw.arg and kw.value.lineno in lines]
            entry = [f"### {rel}:{n.lineno} ruft {name}(...)"]
            for drel, q, d in defs:
                entry.append(f"- Gegenstelle {q} [{drel}:{d.lineno}]: {signature(d)}")
                doc = ast.get_docstring(d) if not isinstance(d, ast.ClassDef) or True else None
                if doc:
                    entry.append("  Doc: " + " ".join(doc.split())[:240])
                target = d
                if isinstance(d, ast.ClassDef):
                    target = next((b for b in d.body if isinstance(b, ast.FunctionDef) and b.name == "__init__"), None)
                if target is None:
                    continue
                rs = raises_in(index, drel, target)
                if rs:
                    entry.append("  wirft: " + ", ".join(sorted({t for t, _ in rs})))
                for kw in changed_kw:
                    flow = param_flow(index, drel, target, kw.arg)
                    if flow:
                        entry.append(f"  geaendert: {kw.arg}={ast.unparse(kw.value)}; Weg:")
                        entry += [f"    {x}" for x in flow[:12]]
            if len(entry) > 1 and (changed_kw or any("wirft" in e for e in entry)):
                report.append("\n".join(entry))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("range")
    ap.add_argument("--root", default="src")
    ap.add_argument("--max-bytes", type=int, default=60000)
    a = ap.parse_args()
    parts = collect(a.repo, a.range, a.root)
    head = (f"# Gegenstellen fuer {a.range}\n\nMechanisch gesammelt (ast, ohne Auswahl nach Verdacht): "
            f"{len(parts)} Stellen. Je Stelle die aufgerufene Definition, was sie wirft und wohin "
            f"geaenderte Schluesselwort-Argumente fliessen.\n")
    out, size = [head], len(head)
    for p in parts:
        if size + len(p) > a.max_bytes:
            out.append(f"\n(abgeschnitten: {len(parts) - len(out) + 1} weitere Stellen)")
            break
        out.append(p)
        size += len(p) + 2
    sys.stdout.write("\n\n".join(out) + "\n")


if __name__ == "__main__":
    main()
