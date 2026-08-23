from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ptr-restricted-source-inventory/v2"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


class InventoryVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.definitions: dict[str, dict[str, Any]] = {}
        self.calls: list[dict[str, Any]] = []
        self.imports: list[dict[str, Any]] = []
        self.attributes: list[dict[str, Any]] = []

    @property
    def context(self) -> str:
        return ".".join(self.stack) or "<module>"

    def _visit_definition(self, node: ast.AST, name: str, kind: str) -> None:
        qualified = ".".join((*self.stack, name))
        rendered = ast.dump(node, annotate_fields=True, include_attributes=False)
        self.definitions[qualified] = {
            "kind": kind,
            "ast_sha256": digest(rendered.encode("utf-8")),
            "line": getattr(node, "lineno", 0),
        }
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition(node, node.name, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition(node, node.name, "async-function")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition(node, node.name, "class")

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(
            {"context": self.context, "name": call_name(node.func), "line": node.lineno}
        )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(
                {
                    "kind": "import",
                    "module": alias.name,
                    "asname": alias.asname,
                    "line": node.lineno,
                }
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.imports.append(
                {
                    "kind": "from",
                    "module": node.module,
                    "level": node.level,
                    "name": alias.name,
                    "asname": alias.asname,
                    "line": node.lineno,
                }
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.attributes.append(
            {
                "context": self.context,
                "name": call_name(node),
                "tail": node.attr,
                "mode": type(node.ctx).__name__,
                "line": node.lineno,
            }
        )
        self.generic_visit(node)


def load_source_files(root: Path) -> dict[str, Path]:
    base = root / "src" / "ptr_v3"
    files = {f"src/ptr_v3/{path.name}": path for path in sorted(base.glob("*.py"))}
    files["scripts/run_two_host.py"] = root / "scripts" / "run_two_host.py"
    return files


def build_inventory(root: Path) -> dict[str, Any]:
    output: dict[str, Any] = {"schema": SCHEMA, "files": {}}
    for relative, path in sorted(load_source_files(root.resolve()).items()):
        raw = path.read_bytes()
        source = raw.decode("utf-8")
        tree = ast.parse(source, filename=relative)
        visitor = InventoryVisitor()
        visitor.visit(tree)
        tree_dump = ast.dump(tree, annotate_fields=True, include_attributes=False)
        node_counts: dict[str, int] = {}
        for node in ast.walk(tree):
            name = type(node).__name__
            node_counts[name] = node_counts.get(name, 0) + 1
        output["files"][relative] = {
            "source_sha256": digest(raw),
            "ast_sha256": digest(tree_dump.encode("utf-8")),
            "node_counts": dict(sorted(node_counts.items())),
            "definitions": dict(sorted(visitor.definitions.items())),
            "imports": sorted(
                visitor.imports,
                key=lambda item: (
                    item["line"],
                    item.get("module") or "",
                    item.get("name") or "",
                ),
            ),
            "calls": sorted(
                visitor.calls,
                key=lambda item: (item["line"], item["context"], item["name"]),
            ),
            "attributes": sorted(
                visitor.attributes,
                key=lambda item: (
                    item["line"],
                    item["context"],
                    item["name"],
                    item["mode"],
                ),
            ),
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Untrusted extractor for the exhaustive restricted-source inventory."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "restricted_source_inventory.v2.json",
    )
    args = parser.parse_args()
    inventory = build_inventory(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"RESTRICTED_SOURCE_INVENTORY_FILES={len(inventory['files'])}")
    print(f"RESTRICTED_SOURCE_INVENTORY={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
