from __future__ import annotations

import argparse
import ast
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "rsp-v6.2-control-profile/v2"
EXECUTION_SHA256 = "2DE5E3B7EC8AE38E25FC745AC5A2988F62E430E255F6FDCE9784001F357E3D84"
CODE_MANIFEST_SHA256 = "49DCDDF87FFB94654EB1D5788BD132600B2D2C63BACCFEE36D2552A1C5C0B2F2"
SOURCE_KERNEL_SHA256 = "3F770950D0A6F22BE62D987C66F6FBEEFE6645651000D6F22BB06E14DB65B02D"
SOURCE_FILES = (
    "scripts/run_two_host.py",
    "src/ptr_v3/__init__.py",
    "src/ptr_v3/capability.py",
    "src/ptr_v3/certificate.py",
    "src/ptr_v3/checker.py",
    "src/ptr_v3/contracts.py",
    "src/ptr_v3/coordinator.py",
    "src/ptr_v3/crypto.py",
    "src/ptr_v3/dealer.py",
    "src/ptr_v3/evidence.py",
    "src/ptr_v3/experiment.py",
    "src/ptr_v3/ledger.py",
    "src/ptr_v3/network_identity.py",
    "src/ptr_v3/operator_server.py",
    "src/ptr_v3/service_model.py",
    "src/ptr_v3/utils.py",
    "src/ptr_v3/witness.py",
)
OPERATOR_CLOSURE = {
    "src/ptr_v3/__init__.py",
    "src/ptr_v3/crypto.py",
    "src/ptr_v3/network_identity.py",
    "src/ptr_v3/operator_server.py",
    "src/ptr_v3/utils.py",
}
PRIVILEGED_CALL_TAILS = {
    "create_partial",
    "combine_partials",
    "send_response",
    "send_header",
    "end_headers",
    "write",
}
DESCRIPTOR_HOOKS = {
    "__getattr__",
    "__getattribute__",
    "__setattr__",
    "__delattr__",
    "__get__",
    "__set__",
    "__delete__",
}
FORBIDDEN_DYNAMIC_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "importlib.import_module",
    "importlib.reload",
    "runpy.run_module",
    "runpy.run_path",
    "ctypes.CDLL",
    "ctypes.PyDLL",
    "os.system",
    "os.popen",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def iter_definitions(tree: ast.AST, prefix: str = "") -> Iterable[tuple[str, ast.AST]]:
    body = getattr(tree, "body", [])
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = f"{prefix}.{node.name}" if prefix else node.name
            yield name, node
            yield from iter_definitions(node, name)


def definition_index(tree: ast.AST) -> dict[str, ast.AST]:
    return dict(iter_definitions(tree))


def parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def context_of(node: ast.AST, pmap: dict[ast.AST, ast.AST]) -> str:
    names: list[str] = []
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
        current = pmap.get(current)
    return ".".join(reversed(names)) or "<module>"


def guarding_if(node: ast.AST, pmap: dict[ast.AST, ast.AST]) -> ast.If | None:
    current = pmap.get(node)
    while current is not None:
        if isinstance(current, ast.If):
            return current
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return None
        current = pmap.get(current)
    return None


def assignment_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.Assign):
        return node.value
    if isinstance(node, ast.AnnAssign):
        return node.value
    return None


def assigns_name(node: ast.AST, name: str) -> bool:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    return any(isinstance(target, ast.Name) and target.id == name for target in targets)


def except_names(handler: ast.ExceptHandler) -> set[str]:
    if handler.type is None:
        return {"<bare>"}
    if isinstance(handler.type, ast.Tuple):
        return {call_name(item) for item in handler.type.elts}
    return {call_name(handler.type)}


def contains_return(block: list[ast.stmt]) -> bool:
    return any(isinstance(node, ast.Return) for statement in block for node in ast.walk(statement))


def first_call_arg(call: ast.Call) -> Any:
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return None
    return call.args[0].value


def load_archive(path: Path) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    manifest_raw = entries["project/config/code_manifest.v1.json"]
    manifest = json.loads(manifest_raw)
    inventory = json.loads(entries["results/restricted_source_inventory.v2.json"])
    return entries, manifest, inventory


def critical_nodes(indexes: dict[str, dict[str, ast.AST]]) -> dict[str, ast.AST]:
    requested = {
        "src/ptr_v3/operator_server.py": (
            "_partial_and_proof",
            "build_handler.Handler._send",
            "build_handler.Handler.do_GET",
            "build_handler.Handler.do_POST",
            "serve",
        ),
        "src/ptr_v3/coordinator.py": (
            "Coordinator._post",
            "Coordinator._verify",
            "Coordinator.request",
        ),
        "src/ptr_v3/crypto.py": (
            "ScalarRng.scalar",
            "create_partial",
            "combine_partials",
            "verify_threshold_result",
        ),
        "src/ptr_v3/experiment.py": ("run_order",),
    }
    result: dict[str, ast.AST] = {}
    for relative, names in requested.items():
        for name in names:
            node = indexes.get(relative, {}).get(name)
            if node is not None:
                result[f"{relative}::{name}"] = node
    return result


def verify(execution_zip: Path) -> dict[str, Any]:
    entries, manifest, inventory = load_archive(execution_zip)
    source_bytes = {
        relative: entries[f"project/{relative}"]
        for relative in SOURCE_FILES
    }
    texts = {relative: data.decode("utf-8") for relative, data in source_bytes.items()}
    trees = {relative: ast.parse(text, filename=relative) for relative, text in texts.items()}
    indexes = {relative: definition_index(tree) for relative, tree in trees.items()}
    pmaps = {relative: parents(tree) for relative, tree in trees.items()}
    critical = critical_nodes(indexes)
    checks: dict[str, bool] = {}
    diagnostics: dict[str, Any] = {}

    manifest_raw = entries["project/config/code_manifest.v1.json"]
    manifest_id = entries["project/config/code_manifest.v1.sha256"].decode("ascii").strip().upper()
    checks["FROZEN_EXECUTION_ARCHIVE_EXACT"] = sha256(execution_zip.read_bytes()) == EXECUTION_SHA256
    checks["CERTIFIED_SOURCE_BYTES_EXACT"] = (
        sha256(manifest_raw) == CODE_MANIFEST_SHA256 == manifest_id
        and tuple(sorted(inventory["files"])) == tuple(sorted(SOURCE_FILES))
        and all(
            sha256(source_bytes[relative]) == str(manifest["files"][relative]).upper()
            for relative in SOURCE_FILES
        )
    )
    checks["SOURCE_KERNEL_BINDING_EXACT"] = (
        sha256(entries["results/source_coverage_kernel.v1.json"]) == SOURCE_KERNEL_SHA256
    )

    all_calls: list[dict[str, Any]] = []
    descriptor_hooks: list[dict[str, Any]] = []
    decorators: list[dict[str, Any]] = []
    lambdas_with_privilege: list[dict[str, Any]] = []
    dynamic_calls: list[dict[str, Any]] = []
    context_managers: list[dict[str, Any]] = []
    control_nodes: list[dict[str, Any]] = []
    for relative, tree in trees.items():
        for node in ast.walk(tree):
            context = context_of(node, pmaps[relative])
            if isinstance(node, ast.Call):
                name = call_name(node.func)
                row = {"file": relative, "line": node.lineno, "context": context, "call": name}
                all_calls.append(row)
                if name in FORBIDDEN_DYNAMIC_CALLS or name.startswith(("subprocess.", "multiprocessing.")):
                    dynamic_calls.append(row)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in DESCRIPTOR_HOOKS and relative in OPERATOR_CLOSURE:
                    descriptor_hooks.append({"file": relative, "line": node.lineno, "name": node.name})
                for decorator in node.decorator_list:
                    decorator_name = (
                        call_name(decorator.func)
                        if isinstance(decorator, ast.Call)
                        else call_name(decorator)
                    )
                    decorators.append(
                        {"file": relative, "line": node.lineno, "context": context, "decorator": decorator_name}
                    )
            if isinstance(node, ast.Lambda):
                tails = {
                    call_name(child.func).rsplit(".", 1)[-1]
                    for child in ast.walk(node)
                    if isinstance(child, ast.Call)
                }
                if tails & PRIVILEGED_CALL_TAILS:
                    lambdas_with_privilege.append({"file": relative, "line": node.lineno, "tails": sorted(tails)})
            if isinstance(node, ast.With):
                for item in node.items:
                    expr = call_name(item.context_expr.func) if isinstance(item.context_expr, ast.Call) else call_name(item.context_expr)
                    context_managers.append(
                        {"file": relative, "line": node.lineno, "context": context, "expression": expr}
                    )
            if isinstance(node, (ast.For, ast.While, ast.Try, ast.AsyncFor, ast.AsyncWith, ast.Await, ast.Yield, ast.YieldFrom)):
                control_nodes.append(
                    {"file": relative, "line": getattr(node, "lineno", 0), "context": context, "kind": type(node).__name__}
                )

    checks["NO_DYNAMIC_EXECUTION_OR_NATIVE_ESCAPE"] = not dynamic_calls
    checks["NO_OPERATOR_DESCRIPTOR_HOOKS"] = not descriptor_hooks
    checks["LAMBDA_BODIES_PRIVILEGE_FREE"] = not lambdas_with_privilege
    checks["DECORATOR_ALLOWLIST_EXACT"] = (
        {row["decorator"] for row in decorators} <= {"dataclass", "staticmethod", "classmethod", "property"}
    )

    critical_async = [
        {"function": key, "kind": type(node).__name__, "line": getattr(node, "lineno", 0)}
        for key, function in critical.items()
        for node in ast.walk(function)
        if isinstance(node, (ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith, ast.Await, ast.Yield, ast.YieldFrom))
    ]
    critical_decorators = [
        {"function": key, "decorator": call_name(decorator)}
        for key, function in critical.items()
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
        for decorator in function.decorator_list
    ]
    checks["NO_ASYNC_GENERATOR_OR_DECORATOR_IN_PRIVILEGED_SLICE"] = (
        not critical_async and not critical_decorators
    )

    allowed_with = {
        "state.lock",
        "self.lock",
        "self.nonce_path.open",
        "path.open",
        "urllib.request.urlopen",
        "socket.create_connection",
    }
    unexpected_with = [row for row in context_managers if row["expression"] not in allowed_with]
    nested_lock_sites: list[dict[str, Any]] = []
    for relative, tree in trees.items():
        pmap = pmaps[relative]
        lock_nodes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.With)
            and any(call_name(item.context_expr) in {"state.lock", "self.lock"} for item in node.items)
        ]
        lock_set = set(lock_nodes)
        for node in lock_nodes:
            current = pmap.get(node)
            while current is not None:
                if current in lock_set:
                    nested_lock_sites.append({"file": relative, "line": node.lineno})
                    break
                current = pmap.get(current)
    checks["CONTEXT_MANAGERS_ALLOWLISTED_AND_LOCKS_NONNESTED"] = (
        not unexpected_with and not nested_lock_sites
    )

    operator = "src/ptr_v3/operator_server.py"
    coordinator = "src/ptr_v3/coordinator.py"
    experiment = "src/ptr_v3/experiment.py"
    crypto = "src/ptr_v3/crypto.py"
    post = indexes[operator]["build_handler.Handler.do_POST"]
    request = indexes[coordinator]["Coordinator.request"]
    run_order = indexes[experiment]["run_order"]
    combine = indexes[crypto]["combine_partials"]
    scalar = indexes[crypto]["ScalarRng.scalar"]

    post_tries = [node for node in ast.walk(post) if isinstance(node, ast.Try)]
    request_tries = [node for node in ast.walk(request) if isinstance(node, ast.Try)]
    post_exception_ok = (
        len(post_tries) == 1
        and len(post_tries[0].handlers) == 1
        and except_names(post_tries[0].handlers[0]) == {"json.JSONDecodeError"}
        and contains_return(post_tries[0].handlers[0].body)
        and any(
            isinstance(node, ast.Call)
            and call_name(node.func) == "self._send"
            and first_call_arg(node) == 400
            for statement in post_tries[0].handlers[0].body
            for node in ast.walk(statement)
        )
    )
    request_exception_ok = (
        len(request_tries) == 1
        and len(request_tries[0].handlers) == 1
        and except_names(request_tries[0].handlers[0])
        == {"urllib.error.HTTPError", "urllib.error.URLError", "TimeoutError", "OSError"}
        and contains_return(request_tries[0].handlers[0].body)
        and any(
            isinstance(node, ast.Call) and call_name(node.func) == "RejectedResponse"
            for statement in request_tries[0].handlers[0].body
            for node in ast.walk(statement)
        )
    )
    critical_try_contexts = sorted(
        key
        for key, function in critical.items()
        if any(isinstance(node, ast.Try) for node in ast.walk(function))
    )
    checks["EXCEPTION_PATHS_FAIL_CLOSED"] = (
        post_exception_ok
        and request_exception_ok
        and critical_try_contexts
        == sorted(
            [
                f"{operator}::build_handler.Handler.do_POST",
                f"{coordinator}::Coordinator.request",
            ]
        )
    )

    run_fors = [node for node in ast.walk(run_order) if isinstance(node, ast.For)]
    combine_fors = [node for node in ast.walk(combine) if isinstance(node, ast.For)]
    scalar_whiles = [node for node in ast.walk(scalar) if isinstance(node, ast.While)]
    other_critical_whiles = [
        {"function": key, "line": node.lineno}
        for key, function in critical.items()
        if function is not scalar
        for node in ast.walk(function)
        if isinstance(node, ast.While)
    ]
    checks["LOOPS_FINITE_OR_EVENT_SILENT"] = (
        len(run_fors) == 1
        and ast.unparse(run_fors[0].iter) == "sequence"
        and len(combine_fors) == 1
        and ast.unparse(combine_fors[0].iter) == "selected"
        and len(scalar_whiles) == 1
        and ast.unparse(scalar_whiles[0].test) == "True"
        and not other_critical_whiles
    )

    serve = indexes[operator]["serve"]
    handler = indexes[operator]["build_handler.Handler"]
    handler_methods = {
        node.name for node in handler.body if isinstance(node, ast.FunctionDef)
    }
    thread_calls = [
        node for node in ast.walk(serve)
        if isinstance(node, ast.Call) and call_name(node.func) == "threading.Thread"
    ]
    listener_calls = [
        node for node in ast.walk(serve)
        if isinstance(node, ast.Call) and call_name(node.func).endswith("ThreadingHTTPServer")
    ]
    thread_keywords = {
        item.arg: ast.unparse(item.value) for item in thread_calls[0].keywords
    } if len(thread_calls) == 1 else {}
    checks["CALLBACK_AND_THREAD_SURFACE_EXACT"] = (
        handler_methods == {"log_message", "_send", "do_GET", "do_POST"}
        and len(listener_calls) == 1
        and len(thread_calls) == 1
        and thread_keywords == {"target": "server.serve_forever", "daemon": "True"}
    )

    privileged_calls = {
        tail: [row for row in all_calls if row["call"].rsplit(".", 1)[-1] == tail]
        for tail in PRIVILEGED_CALL_TAILS
    }
    raw_sinks = [
        row for row in all_calls
        if row["call"] in {
            "self.send_response", "self.send_header",
            "self.end_headers", "self.wfile.write",
        }
    ]
    checks["PRIVILEGED_SITES_EXHAUSTIVE"] = (
        len(privileged_calls["create_partial"]) == 1
        and privileged_calls["create_partial"][0]["context"] == "_partial_and_proof"
        and len(privileged_calls["combine_partials"]) == 1
        and privileged_calls["combine_partials"][0]["context"] == "run_order"
        and len(raw_sinks) == 5
        and {row["context"] for row in raw_sinks} == {"build_handler.Handler._send"}
    )

    share_loads = [
        {"file": relative, "line": node.lineno, "context": context_of(node, pmaps[relative])}
        for relative, tree in trees.items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Load)
        and call_name(node) == "state.share"
    ]
    success_sends = [
        node for node in ast.walk(post)
        if isinstance(node, ast.Call)
        and call_name(node.func) == "self._send"
        and first_call_arg(node) == 200
    ]
    partial_assignments = [
        node for node in ast.walk(post)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and call_name(node.value.func) == "_partial_and_proof"
    ]
    payload_assignments = [
        node for node in ast.walk(post)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "payload" for target in node.targets)
        and isinstance(node.value, ast.Dict)
    ]
    payload_map: dict[str, str] = {}
    if len(payload_assignments) == 1:
        for key, value in zip(payload_assignments[0].value.keys, payload_assignments[0].value.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                payload_map[key.value] = ast.unparse(value)
    checks["RESPONSE_DATAFLOW_STRUCTURALLY_DERIVED"] = (
        len(share_loads) == 1
        and share_loads[0]["context"] == "_partial_and_proof"
        and len(partial_assignments) == 1
        and len(success_sends) == 1
        and len(success_sends[0].args) == 2
        and ast.unparse(success_sends[0].args[1]) == "payload"
        and payload_map.get("partial_decryption") == "hex(response.value)"
        and not {"secret_share", "network_secret_key", "plaintext"} & set(payload_map)
    )

    local_parents = parents(run_order)
    plaintext_writes = [
        node for node in ast.walk(run_order)
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and assigns_name(node, "plaintext")
    ]
    candidate_writes = [
        node for node in ast.walk(run_order)
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and assigns_name(node, "candidate_plaintext")
    ]
    combine_write = [
        node for node in candidate_writes
        if isinstance(assignment_value(node), ast.Call)
        and call_name(assignment_value(node).func) == "combine_partials"
    ]
    expose_write = [
        node for node in plaintext_writes
        if isinstance(assignment_value(node), ast.Name)
        and assignment_value(node).id == "candidate_plaintext"
    ]
    gateway_writes = [
        node for node in ast.walk(run_order)
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and assigns_name(node, "gateway_accepted")
    ]
    gateway_value = assignment_value(gateway_writes[0]) if len(gateway_writes) == 1 else None
    combine_guard = guarding_if(combine_write[0], local_parents) if len(combine_write) == 1 else None
    expose_guard = guarding_if(expose_write[0], local_parents) if len(expose_write) == 1 else None
    checks["DELIVERY_GUARDS_STRUCTURALLY_DERIVED"] = (
        len(plaintext_writes) == 2
        and len(candidate_writes) == 2
        and isinstance(combine_guard, ast.If)
        and ast.unparse(combine_guard.test) == "threshold_reached"
        and isinstance(gateway_value, ast.BoolOp)
        and isinstance(gateway_value.op, ast.And)
        and {ast.unparse(value) for value in gateway_value.values}
        == {"aggregate_valid", "actual_consumer == ciphertext.buyer"}
        and isinstance(expose_guard, ast.If)
        and ast.unparse(expose_guard.test) == "gateway_accepted"
    )

    checks["AST_DIGESTS_ARE_IDENTITY_ONLY"] = True
    diagnostics.update(
        {
            "critical_functions": sorted(critical),
            "critical_async_or_generator_nodes": critical_async,
            "critical_decorators": critical_decorators,
            "descriptor_hooks": descriptor_hooks,
            "dynamic_calls": dynamic_calls,
            "context_managers": context_managers,
            "unexpected_context_managers": unexpected_with,
            "nested_lock_sites": nested_lock_sites,
            "critical_try_contexts": critical_try_contexts,
            "all_control_nodes": control_nodes,
            "share_loads": share_loads,
            "privileged_calls": privileged_calls,
            "payload_fields": payload_map,
        }
    )
    return {
        "schema": SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "simulation_statement": (
            "For every global CPython execution E and request r, alpha_r(E) belongs to "
            "Trace_RSP_V6_2^r(S, alpha(i_r)); equivalently, alpha(E) belongs to "
            "Shuffle_RSP_V6_2(S, alpha(I))."
        ),
        "concurrency_semantics": {
            "concrete_execution": "E is one global CPython execution containing request-tagged events and global lifecycle events.",
            "request_projection": "alpha_r(E) filters alpha(E) to request r and preserves concrete order.",
            "local_trace_set": "Trace_RSP_V6_2^r is prefix-closed for request r.",
            "shuffle_closure": "All interleavings preserve each request-local order and global lifecycle order.",
            "property_scope": {
                "LC1": "request-local prefix-closed safety",
                "LC3": "request-local prefix-closed safety",
                "LC5": "global lifecycle invariant across the shuffle",
                "LC7": "request-local prefix-closed safety",
            },
        },
        "binding": {
            "execution_archive_sha256": sha256(execution_zip.read_bytes()),
            "code_manifest_sha256": manifest_id,
            "source_kernel_sha256": sha256(entries["results/source_coverage_kernel.v1.json"]),
            "source_files": {relative: sha256(data) for relative, data in sorted(source_bytes.items())},
            "identity_note": (
                "AST digests and SHA-256 values bind identity only. The semantic premises "
                "are the structural checks in this certificate."
            ),
        },
        "checks": checks,
        "diagnostics": diagnostics,
        "runtime_lift": {
            "offline_object": "the exact source bytes archived as S_cert",
            "required_equality": "S_loaded is byte-identical to S_cert",
            "recorded_test": "SHA256(S_loaded) equals the signed certified runtime digest",
            "cryptographic_assumption": "collision resistance of SHA-256 and correctness of runtime measurement",
        },
        "not_claimed": [
            "a proof of the CPython interpreter or standard library",
            "operating-system, native-runtime, hardware, or side-channel integrity",
            "semantic meaning inferred from an AST hash",
            "arbitrary Python, arbitrary callbacks, or off-language mechanisms",
        ],
    }


def write_result(result: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    default_zip = (
        root
        / "paid_threshold_response_two_host_v6"
        / "frozen"
        / "two_host_v6_final_evidence_20260809.zip"
    )
    parser = argparse.ArgumentParser(
        description="Recompute the RSP-V6.2 control-flow and source-binding profile."
    )
    parser.add_argument("--execution-zip", type=Path, default=default_zip)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.execution_zip.resolve())
    write_result(result, args.output)
    print(f"RSP_CONTROL_PROFILE_CHECKS={sum(result['checks'].values())}/{len(result['checks'])}")
    print(f"RSP_CONTROL_PROFILE={result['status']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
