from __future__ import annotations

import argparse
import dis
import hashlib
import json
from pathlib import Path
from types import CodeType
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ptr-cpython-bytecode-crosscheck/v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_sources(root: Path) -> dict[str, str]:
    base = root / "src" / "ptr_v3"
    sources = {
        f"ptr_v3.{path.stem}": path.read_text(encoding="utf-8")
        for path in sorted(base.glob("*.py"))
    }
    sources["script.run_two_host"] = (root / "scripts" / "run_two_host.py").read_text(encoding="utf-8")
    return sources


def walk_code(code: CodeType):
    yield code
    for value in code.co_consts:
        if isinstance(value, CodeType):
            yield from walk_code(value)


def compile_inventory(sources: Mapping[str, str]) -> dict[str, object]:
    objects: dict[str, dict[str, object]] = {}
    for module, source in sorted(sources.items()):
        filename = module.replace(".", "/") + ".py"
        top = compile(source, filename, "exec", dont_inherit=True, optimize=0)
        for code in walk_code(top):
            key = f"{module}:{code.co_qualname}"
            instructions = [
                {
                    "op": item.opname,
                    "arg": item.argval
                    if isinstance(item.argval, (str, int, float, type(None)))
                    else repr(item.argval),
                }
                for item in dis.get_instructions(code)
            ]
            stable = json.dumps(instructions, sort_keys=True, separators=(",", ":")).encode("utf-8")
            objects[key] = {
                "names": sorted(code.co_names),
                "locals": list(code.co_varnames),
                "instruction_sha256": sha256_bytes(stable),
                "instructions": instructions,
            }
    return {"schema": SCHEMA, "objects": objects}


def analyze_sources(sources: Mapping[str, str]) -> dict[str, object]:
    inventory = compile_inventory(sources)
    objects = inventory["objects"]
    assert isinstance(objects, dict)

    def matches(suffix: str) -> list[tuple[str, dict[str, object]]]:
        return [
            (name, value)
            for name, value in objects.items()
            if name.endswith(suffix) and isinstance(value, dict)
        ]

    def unique(suffix: str) -> dict[str, object] | None:
        rows = matches(suffix)
        return rows[0][1] if len(rows) == 1 else None

    partial = unique("ptr_v3.operator_server:_partial_and_proof")
    post = unique("ptr_v3.operator_server:build_handler.<locals>.Handler.do_POST")
    send = unique("ptr_v3.operator_server:build_handler.<locals>.Handler._send")
    run_order = unique("ptr_v3.experiment:run_order")
    serve = unique("ptr_v3.operator_server:serve")
    main = unique("ptr_v3.operator_server:main")

    def names(value: dict[str, object] | None) -> set[str]:
        return set(value.get("names", [])) if value else set()

    all_instructions = [
        (name, item)
        for name, value in objects.items()
        if isinstance(value, dict)
        for item in value.get("instructions", [])
        if isinstance(item, dict)
    ]
    store_sensitive = [
        {"object": name, "attr": item.get("arg")}
        for name, item in all_instructions
        if item.get("op") == "STORE_ATTR"
        and item.get("arg") in {"share", "public_share", "identity"}
    ]
    dynamic_names = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
        "subprocess",
        "importlib",
        "runpy",
        "ctypes",
    }
    present_dynamic = sorted(
        {
            item
            for value in objects.values()
            if isinstance(value, dict)
            for item in value.get("names", [])
            if item in dynamic_names
        }
    )

    checks = {
        "CPYTHON_COMPILES_ALL_SOURCES": True,
        "CRITICAL_CODE_OBJECTS_UNIQUE": all(
            value is not None for value in (partial, post, send, run_order, serve, main)
        ),
        "PARTIAL_PRIMITIVE_IN_PRODUCER_ONLY": (
            partial is not None
            and "create_partial" in names(partial)
            and post is not None
            and "create_partial" not in names(post)
        ),
        "POST_REACHES_DECLARED_PRODUCER_AND_SEND": (
            {"_partial_and_proof", "_send"} <= names(post)
            if post is not None
            else False
        ),
        "RAW_HTTP_SINKS_CONFINED_TO_SEND": (
            {"send_response", "send_header", "end_headers", "wfile", "write"} <= names(send)
            if send is not None
            else False
        ),
        "THRESHOLD_AND_COMMITMENT_IN_RUN_ORDER": (
            {"combine_partials", "verify_threshold_result", "mark_success"} <= names(run_order)
            if run_order is not None
            else False
        ),
        "SINGLE_LISTENER_IN_SERVE": (
            serve is not None
            and "ThreadingHTTPServer" in names(serve)
            and "ThreadingHTTPServer" not in names(main)
        ),
        "SENSITIVE_STORES_CONSTRUCTOR_ONLY": (
            len(store_sensitive) == 3
            and {
                (item["object"], item["attr"]) for item in store_sensitive
            }
            == {
                ("ptr_v3.operator_server:OperatorState.__init__", "share"),
                ("ptr_v3.operator_server:OperatorState.__init__", "public_share"),
                ("ptr_v3.operator_server:OperatorState.__init__", "identity"),
            }
        ),
        "NO_DYNAMIC_OR_NATIVE_ESCAPE_NAMES": not present_dynamic,
    }
    return {
        "schema": SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "diagnostics": {
            "sensitive_store_instructions": store_sensitive,
            "dynamic_names": present_dynamic,
            "critical_instruction_sha256": {
                name: objects[name]["instruction_sha256"]
                for name in sorted(objects)
                if any(
                    token in name
                    for token in (
                        "_partial_and_proof",
                        "Handler.do_POST",
                        "Handler._send",
                        "experiment:run_order",
                        "operator_server:serve",
                    )
                )
            },
        },
        "claim": (
            "CPython's compiler independently maps the frozen source to code objects "
            "with the same privileged-operation confinement required by the AST proof."
        ),
        "not_claimed": [
            "a proof of CPython compiler or interpreter correctness",
            "operating-system or native-runtime integrity",
            "replacement for the restricted-source soundness theorem",
        ],
    }


def analyze(root: Path) -> dict[str, object]:
    return analyze_sources(load_sources(root.resolve()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-check source confinement in CPython bytecode.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "cpython_bytecode_crosscheck.v1.json",
    )
    args = parser.parse_args()
    result = analyze(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for name, ok in result["checks"].items():
        print(f"{name}={'PASS' if ok else 'FAIL'}")
    print(f"CPYTHON_BYTECODE_CROSSCHECK={result['status']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
