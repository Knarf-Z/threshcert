from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WANTED = {
    "src/ptr_v3/operator_server.py": [
        "runtime_source_digest", "OperatorState.__init__", "_partial_and_proof",
        "build_handler", "build_handler.Handler._send",
        "build_handler.Handler.do_GET", "build_handler.Handler.do_POST", "serve", "main",
    ],
    "src/ptr_v3/crypto.py": [
        "ScalarRng.scalar", "ScalarRng.bytes", "Ciphertext.to_dict",
        "encrypt_capability", "create_partial", "combine_partials",
        "verify_threshold_result",
    ],
    "src/ptr_v3/network_identity.py": ["signing_message", "sign"],
    "src/ptr_v3/coordinator.py": [
        "Coordinator._post", "Coordinator._verify", "Coordinator.request",
    ],
    "src/ptr_v3/experiment.py": ["make_ciphertext", "run_order"],
    "scripts/run_two_host.py": ["main"],
}


class Index(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.nodes: dict[str, ast.AST] = {}

    def enter(self, node: ast.AST, name: str) -> None:
        self.nodes[".".join((*self.stack, name))] = node
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.enter(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.enter(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.enter(node, node.name)


def main() -> None:
    output: dict[str, str] = {}
    for relative, names in WANTED.items():
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        visitor = Index()
        visitor.visit(tree)
        for name in names:
            rendered = ast.dump(
                visitor.nodes[name], annotate_fields=True, include_attributes=False
            ).encode("utf-8")
            output[f"{relative}::{name}"] = hashlib.sha256(rendered).hexdigest().upper()
    print(json.dumps(output, indent=4, sort_keys=True))


if __name__ == "__main__":
    main()
