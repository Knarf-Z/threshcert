from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "rsp-v6.2-effect-profile/v1"


def load_control_module():
    path = Path(__file__).with_name("verify_control_profile.py")
    spec = importlib.util.spec_from_file_location("rsp_control_profile", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load control-profile verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTROL = load_control_module()


ROOT_FUNCTIONS = {
    "src/ptr_v3/operator_server.py::_partial_and_proof",
    "src/ptr_v3/operator_server.py::build_handler.Handler._send",
    "src/ptr_v3/operator_server.py::build_handler.Handler.do_GET",
    "src/ptr_v3/operator_server.py::build_handler.Handler.do_POST",
    "src/ptr_v3/operator_server.py::serve",
    "src/ptr_v3/operator_server.py::runtime_source_digest",
    "src/ptr_v3/operator_server.py::machine_digest",
    "src/ptr_v3/operator_server.py::OperatorState.__init__",
    "src/ptr_v3/operator_server.py::OperatorState._load_nonces",
    "src/ptr_v3/coordinator.py::Coordinator._post",
    "src/ptr_v3/coordinator.py::Coordinator._verify",
    "src/ptr_v3/coordinator.py::Coordinator.request",
    "src/ptr_v3/crypto.py::ScalarRng.scalar",
    "src/ptr_v3/crypto.py::create_partial",
    "src/ptr_v3/crypto.py::combine_partials",
    "src/ptr_v3/crypto.py::verify_threshold_result",
    "src/ptr_v3/experiment.py::run_order",
}


# These calls resolve to certified local bodies and are recursively expanded.
# A dotted call is listed explicitly so that, for example, path.open cannot be
# mistaken for OrderLedger.open merely because the final attribute is "open".
FIXED_LOCAL_CALLS = {
    "_partial_and_proof",
    "_plaintext_commitment",
    "_proof_challenge",
    "_proof_witness",
    "build_handler",
    "canonical_json_bytes",
    "ciphertext.context_bytes",
    "ciphertext.to_dict",
    "Ciphertext.from_dict",
    "combine_partials",
    "coordinator.request",
    "create_partial",
    "deterministic_nonce",
    "encode_parts",
    "encrypt_capability",
    "hash_bytes",
    "hash_to_int",
    "file_sha256",
    "int_to_bytes",
    "lagrange_at_zero",
    "rng.bytes",
    "rng.scalar",
    "ledger.credit_before_release",
    "ledger.finalize_refund",
    "ledger.mark_success",
    "make_ciphertext",
    "mod_inv",
    "OrderLedger.open",
    "response.proof.to_dict",
    "SchnorrSignature.from_dict",
    "PartialDecryption.from_dict",
    "ChaumPedersenProof.from_dict",
    "self._post",
    "self._append_line",
    "self._debit_id",
    "self._load_nonces",
    "self._tick",
    "self.counted_by_host",
    "self.digest",
    "self._send",
    "self._verify",
    "self.registry.host_of",
    "self.registry.public_key",
    "sha256_hex",
    "sign",
    "signing_message",
    "signature.to_dict",
    "state._append_line",
    "state.record",
    "state.remember_nonce",
    "verify_partial",
    "verify_signature",
    "verify_threshold_result",
}


PURE_CALLS = {
    "any",
    "bytearray",
    "bytes",
    "dict",
    "enumerate",
    "float",
    "hex",
    "int",
    "int.from_bytes",
    "isinstance",
    "json.dumps",
    "json.loads",
    "len",
    "list",
    "max",
    "pow",
    "Path",
    "range",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "type",
    "zip",
    "hashlib.sha256",
    "ValueError",
    "ZeroDivisionError",
}


PURE_METHOD_TAILS = {
    "bit_length",
    "encode",
    "get",
    "hexdigest",
    "digest",
    "hex",
    "items",
    "join",
    "strip",
    "to_bytes",
    "values",
}


INTERNAL_MUTATION_TAILS = {"add", "append", "extend", "setdefault", "update"}


EXPLICIT_EFFECT_CALLS = {
    "ThreadingHTTPServer": "network-listener",
    "handle.fileno": "filesystem-handle",
    "handle.flush": "filesystem-write",
    "handle.read": "filesystem-read",
    "handle.write": "filesystem-write",
    "os.fsync": "filesystem-write",
    "path.open": "filesystem-open",
    "path.parent.mkdir": "filesystem-write",
    "secrets.randbelow": "randomness-read",
    "secrets.token_bytes": "randomness-read",
    "self._rng.getrandbits": "randomness-read",
    "self._rng.randrange": "randomness-read",
    "self.end_headers": "network-send",
    "self.rfile.read": "network-read",
    "self.send_header": "network-send",
    "self.send_response": "network-send",
    "self.wfile.write": "network-send",
    "thread.start": "thread-start",
    "threading.Thread": "thread-create",
    "time.perf_counter": "clock-read",
    "time.sleep": "scheduler-effect",
    "time.time": "clock-read",
    "urllib.request.Request": "network-request-build",
    "urllib.request.urlopen": "network-connect",
    "threading.Lock": "thread-lock-create",
    "platform.node": "environment-read",
    "platform.system": "environment-read",
    "platform.release": "environment-read",
    "platform.machine": "environment-read",
    "platform.processor": "environment-read",
    "os.cpu_count": "environment-read",
    "Path.resolve": "filesystem-metadata-read",
    "resolve": "filesystem-metadata-read",
    "self.nonce_path.exists": "filesystem-metadata-read",
    "self.nonce_path.open": "filesystem-open",
    "iter": "allowlisted-callback-loop",
}


OPERATOR_TYPE_CONTEXTS = {
    "src/ptr_v3/coordinator.py::Coordinator._verify",
    "src/ptr_v3/capability.py::Derivation.to_dict",
    "src/ptr_v3/capability.py::Node.to_dict",
    "src/ptr_v3/coordinator.py::Coordinator.request",
    "src/ptr_v3/crypto.py::ScalarRng.bytes",
    "src/ptr_v3/crypto.py::ScalarRng.scalar",
    "src/ptr_v3/crypto.py::_proof_witness",
    "src/ptr_v3/crypto.py::combine_partials",
    "src/ptr_v3/crypto.py::create_partial",
    "src/ptr_v3/crypto.py::encrypt_capability",
    "src/ptr_v3/crypto.py::lagrange_at_zero",
    "src/ptr_v3/crypto.py::mod_inv",
    "src/ptr_v3/crypto.py::verify_partial",
    "src/ptr_v3/crypto.py::verify_threshold_result",
    "src/ptr_v3/experiment.py::run_order",
    "src/ptr_v3/utils.py::file_sha256",
    "src/ptr_v3/ledger.py::OrderLedger.credit_before_release",
    "src/ptr_v3/ledger.py::OrderLedger.finalize_refund",
    "src/ptr_v3/ledger.py::OrderLedger.open",
    "src/ptr_v3/network_identity.py::OperatorRegistry.host_of",
    "src/ptr_v3/network_identity.py::OperatorRegistry.public_key",
    "src/ptr_v3/network_identity.py::sign",
    "src/ptr_v3/network_identity.py::verify",
    "src/ptr_v3/operator_server.py::OperatorState._load_nonces",
    "src/ptr_v3/operator_server.py::OperatorState._append_line",
    "src/ptr_v3/operator_server.py::build_handler.Handler.do_GET",
    "src/ptr_v3/operator_server.py::build_handler.Handler.do_POST",
    "src/ptr_v3/operator_server.py::runtime_source_digest",
    "src/ptr_v3/utils.py::hash_to_int",
    "src/ptr_v3/utils.py::int_to_bytes",
}


OPERATOR_HOOKS = {
    "__add__", "__and__", "__bool__", "__eq__", "__floordiv__",
    "__ge__", "__gt__", "__index__", "__le__", "__lt__", "__mod__",
    "__mul__", "__ne__", "__neg__", "__or__", "__radd__", "__rand__",
    "__rfloordiv__", "__rmod__", "__rmul__", "__ror__", "__rsub__",
    "__rtruediv__", "__sub__", "__truediv__",
}


DECLARED_STATE_TARGETS = {
    "self.escrow_remaining",
    "self.operator_credits[operator_id]",
    "self.operator_debit_ids[operator_id]",
    "self.step",
    "self.success_step",
    "self.operator_id",
    "self.host_id",
    "self.share",
    "self.public_share",
    "self.identity",
    "self.lock",
    "self.transcript_path",
    "self.nonce_path",
    "self.transcript",
    "self.artificial_delay_ms",
    "self.seen_nonces",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def direct_runtime_nodes(root: ast.AST) -> Iterable[ast.AST]:
    """Walk a function body without silently absorbing nested definitions."""

    stack = list(reversed(list(ast.iter_child_nodes(root))))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def annotation_nodes(function: ast.AST) -> set[int]:
    roots: list[ast.AST] = []
    if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
        if function.args.vararg:
            args.append(function.args.vararg)
        if function.args.kwarg:
            args.append(function.args.kwarg)
        roots.extend(arg.annotation for arg in args if arg.annotation is not None)
        if function.returns is not None:
            roots.append(function.returns)
    roots.extend(
        node.annotation
        for node in direct_runtime_nodes(function)
        if isinstance(node, ast.AnnAssign)
    )
    return {id(node) for root in roots for node in ast.walk(root)}


def site_id(relative: str, function: str, node: ast.AST) -> str:
    rendered = ast.dump(node, annotate_fields=True, include_attributes=False)
    digest = sha256(rendered.encode("utf-8"))[:16]
    return f"{relative}:{getattr(node, 'lineno', 0)}:{function}:{type(node).__name__}:{digest}"


def assignment_targets(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return [node.target]
    return []


def target_category(target: ast.AST) -> str | None:
    if isinstance(target, (ast.Name, ast.Tuple, ast.List)):
        return "event-pure-local-store"
    rendered = ast.unparse(target)
    if rendered in DECLARED_STATE_TARGETS:
        return "classified-declared-state-effect"
    if isinstance(target, ast.Subscript):
        root = rendered.split("[", 1)[0]
        if root in {"d", "payload", "payloads", "proof"}:
            return "event-pure-local-container-store"
    if rendered.startswith("os.environ["):
        return "external-environment-mutation"
    return None


def call_category(name: str, local_classes: set[str]) -> str | None:
    tail = name.rsplit(".", 1)[-1]
    if name in FIXED_LOCAL_CALLS or tail in {"to_dict", "from_dict"}:
        return "rsp-inline-certified-local-body"
    if name in EXPLICIT_EFFECT_CALLS:
        return f"rsp-effect-{EXPLICIT_EFFECT_CALLS[name]}"
    if name in PURE_CALLS or tail in PURE_METHOD_TAILS:
        return "event-pure-exact-builtin"
    if tail in INTERNAL_MUTATION_TAILS:
        return "classified-request-local-mutation"
    if tail in local_classes or name in local_classes or name == "cls":
        return "event-pure-accepted-constructor"
    return None


def external_sink_kind(name: str) -> str | None:
    lower = name.lower()
    tail = lower.rsplit(".", 1)[-1]
    if name in EXPLICIT_EFFECT_CALLS:
        return EXPLICIT_EFFECT_CALLS[name]
    if name == "print" or lower in {"sys.stdout.write", "sys.stderr.write"}:
        return "stdout-stderr"
    if any(piece in lower for piece in ("logging.", ".log.", ".logger.")) and tail in {
        "debug", "info", "warn", "warning", "error", "exception", "critical"
    }:
        return "logging"
    if lower.startswith(("subprocess.", "multiprocessing.", "ctypes.")):
        return "ipc-process-native"
    if lower in {"os.putenv", "os.unsetenv", "os.system", "os.popen"}:
        return "environment-or-process"
    if tail in {"send", "sendall", "connect", "listen", "accept"}:
        return "network-or-ipc"
    if tail in {"write_text", "write_bytes", "unlink", "rename", "replace", "flush", "fsync"}:
        return "filesystem-write"
    if tail in {"read_text", "read_bytes", "read", "exists", "stat"}:
        return "filesystem-read"
    if tail == "open" and "path" in lower:
        return "filesystem-open"
    return None


def resolve_local_targets(
    call: ast.Call,
    definitions_by_tail: dict[str, list[tuple[str, str, ast.AST]]],
) -> list[tuple[str, str, ast.AST]]:
    name = CONTROL.call_name(call.func)
    tail = name.rsplit(".", 1)[-1]
    if name not in FIXED_LOCAL_CALLS and tail not in {"to_dict", "from_dict"}:
        return []
    tail = "verify" if name == "verify_signature" else tail
    return definitions_by_tail.get(tail, [])


def verify(execution_zip: Path) -> dict[str, Any]:
    entries, _manifest, _inventory = CONTROL.load_archive(execution_zip)
    source_bytes = {
        relative: entries[f"project/{relative}"]
        for relative in CONTROL.SOURCE_FILES
    }
    trees = {
        relative: ast.parse(data.decode("utf-8"), filename=relative)
        for relative, data in source_bytes.items()
    }
    indexes = {relative: CONTROL.definition_index(tree) for relative, tree in trees.items()}
    all_definitions = {
        f"{relative}::{name}": node
        for relative, index in indexes.items()
        for name, node in index.items()
    }
    missing_roots = sorted(ROOT_FUNCTIONS - set(all_definitions))

    definitions_by_tail: dict[str, list[tuple[str, str, ast.AST]]] = defaultdict(list)
    local_classes: set[str] = set()
    for relative, index in indexes.items():
        for name, node in index.items():
            tail = name.rsplit(".", 1)[-1]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions_by_tail[tail].append((relative, name, node))
            elif isinstance(node, ast.ClassDef):
                local_classes.add(tail)

    queue = deque((key, all_definitions[key]) for key in sorted(ROOT_FUNCTIONS & set(all_definitions)))
    closure: dict[str, ast.AST] = {}
    unresolved_local_calls: list[dict[str, Any]] = []
    while queue:
        key, function = queue.popleft()
        if key in closure:
            continue
        closure[key] = function
        annotations = annotation_nodes(function)
        for node in direct_runtime_nodes(function):
            if not isinstance(node, ast.Call) or id(node) in annotations:
                continue
            name = CONTROL.call_name(node.func)
            if name not in FIXED_LOCAL_CALLS:
                continue
            targets = resolve_local_targets(node, definitions_by_tail)
            if not targets:
                unresolved_local_calls.append({"function": key, "line": node.lineno, "call": name})
            for relative, target_name, target in targets:
                target_key = f"{relative}::{target_name}"
                if target_key not in closure:
                    queue.append((target_key, target))

    source_operator_hooks = sorted(
        f"{relative}::{name}"
        for relative, index in indexes.items()
        for name, node in index.items()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and name.rsplit(".", 1)[-1] in OPERATOR_HOOKS
    )

    sites: list[dict[str, Any]] = []
    unclassified: list[dict[str, Any]] = []
    external_sinks: list[dict[str, Any]] = []
    operator_contexts: set[str] = set()
    counts = {"calls": 0, "assignments": 0, "operators": 0}

    for key, function in sorted(closure.items()):
        relative, function_name = key.split("::", 1)
        annotations = annotation_nodes(function)
        for node in direct_runtime_nodes(function):
            if id(node) in annotations:
                continue
            category: str | None = None
            rendered = ast.unparse(node) if hasattr(node, "lineno") else ""
            kind = ""
            if isinstance(node, ast.Call):
                kind = "call"
                counts["calls"] += 1
                name = CONTROL.call_name(node.func)
                category = call_category(name, local_classes)
                sink = external_sink_kind(name)
                if sink:
                    external_sinks.append(
                        {"site": site_id(relative, function_name, node), "call": name, "sink": sink}
                    )
                    if category is None or not category.startswith("rsp-effect-"):
                        category = f"rsp-effect-{sink}"
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                kind = "assignment"
                counts["assignments"] += 1
                categories = {target_category(target) for target in assignment_targets(node)}
                category = categories.pop() if len(categories) == 1 else None
            elif isinstance(node, (ast.BinOp, ast.BoolOp, ast.UnaryOp, ast.Compare)):
                kind = "operator"
                counts["operators"] += 1
                operator_contexts.add(key)
                if key in OPERATOR_TYPE_CONTEXTS:
                    category = "rsp-op-exact-builtin-types"
            else:
                continue

            row = {
                "site": site_id(relative, function_name, node),
                "file": relative,
                "function": function_name,
                "line": getattr(node, "lineno", 0),
                "kind": kind,
                "source": rendered,
                "classification": category or "UNCLASSIFIED",
            }
            sites.append(row)
            if category is None:
                unclassified.append(row)

    checks = {
        "FROZEN_EXECUTION_ARCHIVE_EXACT": sha256(execution_zip.read_bytes()) == CONTROL.EXECUTION_SHA256,
        "EVENT_RELEVANT_ROOTS_PRESENT": not missing_roots,
        "FIXED_LOCAL_CALLS_RESOLVE_TO_CERTIFIED_BODIES": not unresolved_local_calls,
        "EVERY_CALL_ASSIGNMENT_AND_OPERATOR_CLASSIFIED": not unclassified,
        "EVERY_EXTERNAL_SINK_RETAINED_AS_RSP_EFFECT": all(
            any(site["site"] == sink["site"] and site["classification"].startswith("rsp-effect-") for site in sites)
            for sink in external_sinks
        ),
        "NO_USER_OPERATOR_DISPATCH_HOOKS": not source_operator_hooks,
        "EVERY_OPERATOR_CONTEXT_HAS_EXACT_BUILTIN_TYPE_TABLE": operator_contexts <= OPERATOR_TYPE_CONTEXTS,
    }

    return {
        "schema": SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "binding": {
            "execution_archive_sha256": sha256(execution_zip.read_bytes()),
            "source_files": {relative: sha256(data) for relative, data in sorted(source_bytes.items())},
        },
        "checks": checks,
        "scope": {
            "root_functions": sorted(ROOT_FUNCTIONS),
            "recursive_function_closure": sorted(closure),
            "functions": len(closure),
            **counts,
            "external_sinks": len(external_sinks),
        },
        "semantics": {
            "r_silent": (
                "R-SILENT applies only to sites classified event-pure; it never erases an "
                "unclassified call, assignment, operator dispatch, or external sink."
            ),
            "r_effect": (
                "Network, filesystem, stdout/stderr, logging, environment, IPC/process, "
                "clock, randomness, scheduler, thread, and declared state effects remain "
                "explicit in the full RSP trace."
            ),
            "r_op": (
                "Every admitted operator site is bound to an exact built-in operand-type "
                "table; application operator hooks are rejected."
            ),
        },
        "diagnostics": {
            "missing_roots": missing_roots,
            "unresolved_local_calls": unresolved_local_calls,
            "source_operator_hooks": source_operator_hooks,
            "operator_contexts": sorted(operator_contexts),
            "external_sinks": external_sinks,
            "unclassified_sites": unclassified,
            "sites": sites,
        },
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
    default_zip = root / "paid_threshold_response_two_host_v6" / "frozen" / "two_host_v6_final_evidence_20260809.zip"
    parser = argparse.ArgumentParser(description="Verify the RSP-V6.2 complete effect-site profile.")
    parser.add_argument("--execution-zip", type=Path, default=default_zip)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.execution_zip.resolve())
    write_result(result, args.output)
    print(f"RSP_EFFECT_PROFILE_SITES={sum(result['scope'][k] for k in ('calls', 'assignments', 'operators'))}")
    print(f"RSP_EFFECT_PROFILE_EXTERNAL_SINKS={result['scope']['external_sinks']}")
    print(f"RSP_EFFECT_PROFILE={result['status']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
