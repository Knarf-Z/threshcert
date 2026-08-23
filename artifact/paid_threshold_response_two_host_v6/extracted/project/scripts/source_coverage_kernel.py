from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from compiler_bytecode_crosscheck import analyze_sources as analyze_bytecode

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ptr-restricted-source-kernel/v2"
PROVED = "PROVED_IN_RESTRICTED_SOURCE_MODEL"
REJECTED = "REJECTED"

EXPECTED_SOURCE_FILES = (
    "__init__.py", "capability.py", "certificate.py", "checker.py",
    "contracts.py", "coordinator.py", "crypto.py", "dealer.py", "evidence.py",
    "experiment.py", "ledger.py", "network_identity.py", "operator_server.py",
    "service_model.py", "utils.py", "witness.py",
)
EXPECTED_OPERATOR_CLOSURE = (
    "ptr_v3.__init__", "ptr_v3.crypto", "ptr_v3.network_identity",
    "ptr_v3.operator_server", "ptr_v3.utils",
)
EXPECTED_HANDLER_METHODS = ("_send", "do_GET", "do_POST", "log_message")
EXPECTED_ROUTES = {"do_GET": "/health", "do_POST": "/respond"}
EXPECTED_RUNTIME_FILES = (
    "__init__.py", "crypto.py", "network_identity.py", "operator_server.py",
    "utils.py",
)
EXPECTED_PAYLOAD_KEYS = (
    "protocol_version", "operator_id", "host_id", "order_id", "buyer",
    "resource", "epoch", "nonce", "partial_decryption",
    "chaum_pedersen_proof", "partial_hash", "proof_hash",
    "operator_signature", "runtime_source_digest",
)

FORBIDDEN_IMPORT_ROOTS = {
    "importlib", "runpy", "subprocess", "ctypes", "multiprocessing",
}
FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr",
    "globals", "locals", "vars", "os.system", "os.popen", "pickle.loads",
    "marshal.loads", "importlib.import_module", "importlib.reload",
    "runpy.run_module", "runpy.run_path", "ctypes.CDLL", "ctypes.PyDLL",
}
FORBIDDEN_PREFIXES = (
    "subprocess.", "asyncio.create_subprocess", "multiprocessing.",
)
LISTENER_TAILS = {
    "HTTPServer", "ThreadingHTTPServer", "TCPServer", "ThreadingTCPServer",
    "UnixStreamServer", "ThreadingUnixStreamServer", "create_server",
    "start_server",
}
PRIVILEGED_NAMES = {
    "create_partial", "combine_partials", "_partial_and_proof", "_send",
}
SENSITIVE_ATTRS = {"share", "public_share", "identity"}

# Populated after the reviewed V6 normal forms are frozen.
EXPECTED_CRITICAL_AST: dict[str, str] = {
    "scripts/run_two_host.py::main": "7A40BFDAC543240629025892450A7D2D6C74FCEEE2610F1AB903260C0971A404",
    "src/ptr_v3/coordinator.py::Coordinator._post": "A063642960C3475D201E8815EEEC3F4AE940EA57844BAB398CB884A209AB2743",
    "src/ptr_v3/coordinator.py::Coordinator._verify": "9F93D8535FBED6A0D6FA44F17C10D33B0B5038D158DE553CEE090C54D7E7F324",
    "src/ptr_v3/coordinator.py::Coordinator.request": "4D9F2A5390958E0BA332E898C1758D50C9692E7DB7BB9992F0E9CB198C68A3C4",
    "src/ptr_v3/crypto.py::Ciphertext.to_dict": "3ED1A0E64B531853D35A4FD09097DD053C05836054E06C663BEE135D363A727D",
    "src/ptr_v3/crypto.py::ScalarRng.bytes": "28692A038CC78002143EF121343486B62ADF0814C385A93CE2C9BD5C38ABCBE3",
    "src/ptr_v3/crypto.py::ScalarRng.scalar": "FEDC8D7822032E78B3C824C7125344B20F007504233E434B91BC85A4EA9558AC",
    "src/ptr_v3/crypto.py::combine_partials": "12ED77BD644FC1C6F49A6AF16F1D2905C2D2A0977D6030BCBF24BDBB7B620481",
    "src/ptr_v3/crypto.py::create_partial": "7763D08F20E8C576D6D2B6C0BB0A73DE79ECB1A5914D7D7785244A8DAFE8BB3A",
    "src/ptr_v3/crypto.py::encrypt_capability": "4739470BF9BCAF7DB4E898CCD2C370A47C2C2E67718B1054FE73122F54EE2908",
    "src/ptr_v3/crypto.py::verify_threshold_result": "25E2C7DB07DED659EFA2848F8EB2EDAAFBB1BE7818A8C7D1BB990E0B201DD659",
    "src/ptr_v3/experiment.py::make_ciphertext": "005D5AA631BADF490C137924BB9022DEC3CEC0CF92CA094026F24052FFB360C1",
    "src/ptr_v3/experiment.py::run_order": "EC0247E16E9475FFE2EB4D3FFC6F5859108C75ECB3E2DB8DF75A56BEDF6F38D4",
    "src/ptr_v3/network_identity.py::sign": "E4DB85DEDF6D60230FF04DC4D956CB78BAFDB6129F4F2B59965EECBD9E20A422",
    "src/ptr_v3/network_identity.py::signing_message": "C32735328A37A76FDA09B93EED856093E336CA43BEA079E51C2598C4DC48AF0F",
    "src/ptr_v3/operator_server.py::OperatorState.__init__": "716CFF34ED84794B7C9DAF3FC8B33CD782F90BA504C746CB2D202342BA37A7A3",
    "src/ptr_v3/operator_server.py::_partial_and_proof": "6CAAB5B3A2954384D3A21F193A06519C9DF74968922D843B766820EC35643A18",
    "src/ptr_v3/operator_server.py::build_handler": "F330B1D6E3A7BFB6E811D111869B228B874BB628A451CEB0CE990D8E80BBA713",
    "src/ptr_v3/operator_server.py::build_handler.Handler._send": "C8563733920DA56212EBB21178E68D70CB53057C46ABF9AE5FFD16D6C5CE3315",
    "src/ptr_v3/operator_server.py::build_handler.Handler.do_GET": "39AF26033F81FFAAC630E3A83820076D1332C3B32D7983CC7F918F8EB9EEBF9F",
    "src/ptr_v3/operator_server.py::build_handler.Handler.do_POST": "88CDEF8316643221FF7647D571E3FB2C582586CF9615232A6D75E25B077609A4",
    "src/ptr_v3/operator_server.py::main": "D0DC2445991DFC0C6C1A438E6563B758230DC6CD696F6AF4894AC36230F9A466",
    "src/ptr_v3/operator_server.py::runtime_source_digest": "0866D90B87132693286B6C62ECEA2B61633A65145AC4266A7D2231DA188F3495",
    "src/ptr_v3/operator_server.py::serve": "89CBCE6E705DF111791693C057F2719E6CB64068992B9A0B6AB8DF9382912D6C",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def ast_sha(node: ast.AST) -> str:
    value = ast.dump(node, annotate_fields=True, include_attributes=False)
    return digest(value.encode("utf-8"))


def parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def context_of(node: ast.AST, pmap: Mapping[ast.AST, ast.AST]) -> str:
    names: list[str] = []
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(current.name)
        current = pmap.get(current)
    return ".".join(reversed(names)) or "<module>"


def targets(node: ast.AST) -> Iterable[ast.AST]:
    if isinstance(node, ast.Assign):
        yield from node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        yield node.target


def assigns(node: ast.AST, name: str) -> bool:
    return any(isinstance(target, ast.Name) and target.id == name for target in targets(node))


def value_of_assignment(node: ast.AST) -> ast.AST | None:
    return node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None


def dict_items(node: ast.Dict) -> dict[str, ast.AST]:
    return {
        key.value: value
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


class DefIndex(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.nodes: dict[str, ast.AST] = {}

    def enter(self, node: ast.AST, name: str) -> None:
        qualified = ".".join((*self.stack, name))
        self.nodes[qualified] = node
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.enter(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.enter(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.enter(node, node.name)


def index(tree: ast.Module) -> dict[str, ast.AST]:
    visitor = DefIndex()
    visitor.visit(tree)
    return visitor.nodes


def load(root: Path) -> tuple[dict[str, str], dict[str, ast.Module], dict[str, str]]:
    texts: dict[str, str] = {}
    trees: dict[str, ast.Module] = {}
    errors: dict[str, str] = {}
    paths = {
        f"src/ptr_v3/{path.name}": path
        for path in sorted((root / "src" / "ptr_v3").glob("*.py"))
    }
    paths["scripts/run_two_host.py"] = root / "scripts" / "run_two_host.py"
    for relative, path in paths.items():
        try:
            text = path.read_text(encoding="utf-8")
            texts[relative] = text
            trees[relative] = ast.parse(text, filename=relative)
        except (OSError, UnicodeDecodeError, SyntaxError) as error:
            errors[relative] = str(error)
    return texts, trees, errors


def module_name(relative: str) -> str:
    if relative == "src/ptr_v3/__init__.py":
        return "ptr_v3.__init__"
    if relative.startswith("src/ptr_v3/"):
        return "ptr_v3." + Path(relative).stem
    return "script.run_two_host"


def local_imports(module: str, tree: ast.Module) -> set[str]:
    result: set[str] = set()
    package = module.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(
                alias.name for alias in node.names
                if alias.name == "ptr_v3" or alias.name.startswith("ptr_v3.")
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.module:
                    result.add(f"{package}.{node.module}")
                else:
                    result.update(f"{package}.{alias.name}" for alias in node.names)
            elif node.module and (
                node.module == "ptr_v3" or node.module.startswith("ptr_v3.")
            ):
                result.add(node.module)
    return result


def operator_closure(trees: Mapping[str, ast.Module]) -> tuple[set[str], list[str]]:
    by_module = {module_name(path): tree for path, tree in trees.items()}
    todo = ["ptr_v3.operator_server"]
    closure = {"ptr_v3.__init__"}
    missing: list[str] = []
    while todo:
        module = todo.pop()
        if module in closure:
            continue
        closure.add(module)
        tree = by_module.get(module)
        if tree is None:
            missing.append(module)
            continue
        todo.extend(local_imports(module, tree) - closure)
    return closure, sorted(missing)


def inventory_matches(
    root: Path, texts: Mapping[str, str], trees: Mapping[str, ast.Module]
) -> tuple[bool, str | None]:
    path = root / "results" / "restricted_source_inventory.v2.json"
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    files = stored.get("files", {})
    if set(files) != set(texts):
        return False, None
    for relative in texts:
        record = files.get(relative, {})
        if record.get("source_sha256") != digest(texts[relative].encode("utf-8")):
            return False, None
        if record.get("ast_sha256") != ast_sha(trees[relative]):
            return False, None
    canonical = json.dumps(stored, sort_keys=True, separators=(",", ":")).encode()
    return True, digest(canonical)

def route_guard(function: ast.FunctionDef, route: str) -> bool:
    body = list(function.body)
    if (
        body and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body or not isinstance(body[0], ast.If):
        return False
    guard = body[0]
    test = guard.test
    comparison = (
        isinstance(test, ast.Compare) and call_name(test.left) == "self.path"
        and len(test.ops) == 1 and isinstance(test.ops[0], ast.NotEq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == route
    )
    rejected = any(
        isinstance(node, ast.Call) and call_name(node.func) == "self._send"
        and node.args and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == 404
        for node in ast.walk(guard)
    )
    returns = any(isinstance(node, ast.Return) for node in ast.walk(guard))
    routes = {
        node.value for node in ast.walk(function)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value.startswith("/")
    }
    return comparison and rejected and returns and routes == {route}


def guarding_if(node: ast.AST, pmap: Mapping[ast.AST, ast.AST]) -> ast.If | None:
    current = pmap.get(node)
    while current is not None:
        if isinstance(current, ast.If):
            return current
        if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            return None
        current = pmap.get(current)
    return None


def analyze(root: Path) -> dict[str, Any]:
    root = root.resolve()
    texts, trees, parse_errors = load(root)
    pmap = {path: parents(tree) for path, tree in trees.items()}
    indexes = {path: index(tree) for path, tree in trees.items()}
    checks: dict[str, bool] = {}
    diagnostics: dict[str, Any] = {"parse_errors": parse_errors}

    source_files = tuple(sorted(
        Path(path).name for path in trees if path.startswith("src/ptr_v3/")
    ))
    checks["PYTHON_SYNTAX"] = not parse_errors
    checks["SOURCE_MODULE_SET_EXACT"] = (
        source_files == tuple(sorted(EXPECTED_SOURCE_FILES))
    )
    inventory_ok, inventory_hash = inventory_matches(root, texts, trees)
    checks["UNTRUSTED_INVENTORY_RECOMPUTED"] = inventory_ok

    closure, missing = operator_closure(trees)
    checks["OPERATOR_IMPORT_CLOSURE_EXACT"] = (
        tuple(sorted(closure)) == tuple(sorted(EXPECTED_OPERATOR_CLOSURE))
        and not missing
    )
    diagnostics["operator_import_closure"] = sorted(closure)
    diagnostics["missing_operator_imports"] = missing

    forbidden_imports: list[dict[str, Any]] = []
    forbidden_calls: list[dict[str, Any]] = []
    wildcard: list[dict[str, Any]] = []
    rebound: list[dict[str, Any]] = []
    listeners: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    sinks: list[dict[str, Any]] = []
    for relative, tree in trees.items():
        for node in ast.walk(tree):
            context = context_of(node, pmap[relative])
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS:
                        forbidden_imports.append(
                            {"file": relative, "line": node.lineno, "name": alias.name}
                        )
            elif isinstance(node, ast.ImportFrom):
                if any(alias.name == "*" for alias in node.names):
                    wildcard.append({"file": relative, "line": node.lineno})
                if node.module and node.module.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS:
                    forbidden_imports.append(
                        {"file": relative, "line": node.lineno, "name": node.module}
                    )
                for alias in node.names:
                    if alias.name in PRIVILEGED_NAMES and alias.asname:
                        rebound.append(
                            {"file": relative, "line": node.lineno, "name": alias.name}
                        )
            if isinstance(node, ast.Call):
                name = call_name(node.func)
                record = {
                    "file": relative, "line": node.lineno,
                    "context": context, "call": name,
                }
                calls.append(record)
                if name in FORBIDDEN_CALLS or any(
                    name == prefix or name.startswith(prefix)
                    for prefix in FORBIDDEN_PREFIXES
                ):
                    forbidden_calls.append(record)
                if name.rsplit(".", 1)[-1] in LISTENER_TAILS:
                    listeners.append(record)
                if name in {
                    "self.send_response", "self.send_header",
                    "self.end_headers", "self.wfile.write",
                }:
                    sinks.append(record)
            for target in targets(node):
                for child in ast.walk(target):
                    if isinstance(child, ast.Name) and child.id in PRIVILEGED_NAMES:
                        rebound.append(
                            {"file": relative, "line": node.lineno, "name": child.id}
                        )
                    if isinstance(child, ast.Attribute) and child.attr in PRIVILEGED_NAMES:
                        rebound.append(
                            {"file": relative, "line": node.lineno, "name": call_name(child)}
                        )

    checks["NO_DYNAMIC_NATIVE_OR_PROCESS_ESCAPE"] = (
        not forbidden_imports and not forbidden_calls
    )
    checks["NO_WILDCARD_IMPORT"] = not wildcard
    checks["PRIVILEGED_SYMBOLS_NOT_ALIASED_OR_REBOUND"] = not rebound
    checks["SINGLE_DECLARED_LISTENER"] = (
        len(listeners) == 1
        and listeners[0]["file"] == "src/ptr_v3/operator_server.py"
        and listeners[0]["context"] == "serve"
        and listeners[0]["call"].endswith("ThreadingHTTPServer")
    )
    diagnostics.update({
        "forbidden_imports": forbidden_imports,
        "forbidden_calls": forbidden_calls,
        "wildcard_imports": wildcard,
        "privileged_rebinding": rebound,
        "listeners": listeners,
    })

    operator = "src/ptr_v3/operator_server.py"
    experiment = "src/ptr_v3/experiment.py"
    coordinator = "src/ptr_v3/coordinator.py"
    network = "src/ptr_v3/network_identity.py"
    runner = "scripts/run_two_host.py"

    handler = indexes.get(operator, {}).get("build_handler.Handler")
    methods = {
        node.name: node for node in handler.body
        if isinstance(node, ast.FunctionDef)
    } if isinstance(handler, ast.ClassDef) else {}
    checks["HANDLER_AND_ENTRY_METHODS_EXACT"] = (
        tuple(sorted(methods)) == tuple(sorted(EXPECTED_HANDLER_METHODS))
    )
    checks["ROUTE_GUARDS_EXACT"] = all(
        isinstance(methods.get(name), ast.FunctionDef)
        and route_guard(methods[name], route)
        for name, route in EXPECTED_ROUTES.items()
    )
    checks["RAW_HTTP_SINKS_CONFINED"] = (
        len(sinks) == 5
        and {item["call"] for item in sinks} == {
            "self.send_response", "self.send_header",
            "self.end_headers", "self.wfile.write",
        }
        and {item["context"] for item in sinks}
        == {"build_handler.Handler._send"}
    )

    critical_calls = {
        name: [item for item in calls if item["call"].rsplit(".", 1)[-1] == name]
        for name in ("create_partial", "combine_partials", "_partial_and_proof")
    }
    checks["PARTIAL_PRODUCER_SITE_UNIQUE"] = (
        len(critical_calls["create_partial"]) == 1
        and critical_calls["create_partial"][0]["file"] == operator
        and critical_calls["create_partial"][0]["context"] == "_partial_and_proof"
    )
    checks["RECONSTRUCTION_SITE_UNIQUE"] = (
        len(critical_calls["combine_partials"]) == 1
        and critical_calls["combine_partials"][0]["file"] == experiment
        and critical_calls["combine_partials"][0]["context"] == "run_order"
    )
    diagnostics["critical_calls"] = critical_calls

    sensitive_loads: list[dict[str, Any]] = []
    sensitive_stores: list[dict[str, Any]] = []
    payload_ok = False
    send_ok = False
    tuple_ok = False
    tree = trees.get(operator)
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in SENSITIVE_ATTRS:
                record = {
                    "context": context_of(node, pmap[operator]),
                    "name": call_name(node), "tail": node.attr, "line": node.lineno,
                }
                if isinstance(node.ctx, ast.Load):
                    sensitive_loads.append(record)
                elif isinstance(node.ctx, ast.Store):
                    sensitive_stores.append(record)
        post = indexes[operator].get("build_handler.Handler.do_POST")
        if isinstance(post, ast.FunctionDef):
            for node in ast.walk(post):
                if isinstance(node, ast.Assign):
                    if (
                        any(
                            isinstance(target, ast.Tuple)
                            and [x.id for x in target.elts if isinstance(x, ast.Name)]
                            == ["response", "partial_hash", "proof_hash"]
                            for target in node.targets
                        )
                        and isinstance(node.value, ast.Call)
                        and call_name(node.value.func) == "_partial_and_proof"
                    ):
                        tuple_ok = True
                    if (
                        any(isinstance(target, ast.Name) and target.id == "payload"
                            for target in node.targets)
                        and isinstance(node.value, ast.Dict)
                    ):
                        items = dict_items(node.value)
                        payload_ok = (
                            tuple(items) == EXPECTED_PAYLOAD_KEYS
                            and ast.unparse(items["partial_decryption"])
                            == "hex(response.value)"
                            and not {"secret_share", "network_secret_key",
                                     "token_material", "plaintext"} & set(items)
                        )
                if (
                    isinstance(node, ast.Call) and call_name(node.func) == "self._send"                    and node.args and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == 200
                ):
                    send_ok = (
                        len(node.args) == 2
                        and isinstance(node.args[1], ast.Name)
                        and node.args[1].id == "payload"
                    )

    checks["SENSITIVE_STATE_LIFECYCLE_EXACT"] = (
        {(x["context"], x["name"]) for x in sensitive_stores} == {
            ("OperatorState.__init__", "self.share"),
            ("OperatorState.__init__", "self.public_share"),
            ("OperatorState.__init__", "self.identity"),
        }
    )
    checks["SECRET_SHARE_READ_CONFINED_TO_PRODUCER"] = (
        [(x["context"], x["name"]) for x in sensitive_loads if x["tail"] == "share"]
        == [("_partial_and_proof", "state.share")]
    )
    checks["SUCCESS_RESPONSE_DERIVED_FROM_PRODUCER"] = (
        tuple_ok and payload_ok and send_ok
    )
    diagnostics["sensitive_loads"] = sensitive_loads
    diagnostics["sensitive_stores"] = sensitive_stores

    delivery: dict[str, bool] = {}
    run_order = indexes.get(experiment, {}).get("run_order")
    if isinstance(run_order, ast.FunctionDef):
        local_parents = parents(run_order)
        plaintext_writes = [
            node for node in ast.walk(run_order)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and assigns(node, "plaintext")
        ]
        candidate_writes = [
            node for node in ast.walk(run_order)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and assigns(node, "candidate_plaintext")
        ]
        combine_writes = [
            node for node in candidate_writes
            if isinstance(value_of_assignment(node), ast.Call)
            and call_name(value_of_assignment(node).func).endswith("combine_partials")
        ]
        exposed = [
            node for node in plaintext_writes
            if isinstance(value_of_assignment(node), ast.Name)
            and value_of_assignment(node).id == "candidate_plaintext"
        ]
        gateway_writes = [
            node for node in ast.walk(run_order)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and assigns(node, "gateway_accepted")
        ]
        gateway_value = (
            value_of_assignment(gateway_writes[0])
            if len(gateway_writes) == 1 else None
        )
        marks = [
            node for node in ast.walk(run_order)
            if isinstance(node, ast.Call)
            and call_name(node.func) == "ledger.mark_success"
        ]
        outcome = [
            node for node in ast.walk(run_order)
            if isinstance(node, ast.Call) and call_name(node.func) == "OrderOutcome"
        ]
        outcome_plaintext = False
        if len(outcome) == 1:
            keywords = {item.arg: item.value for item in outcome[0].keywords}
            plain_arg = keywords.get("plaintext")
            outcome_plaintext = (
                isinstance(plain_arg, ast.Name) and plain_arg.id == "plaintext"
            )
        combine_guard = guarding_if(combine_writes[0], local_parents) if len(combine_writes) == 1 else None
        expose_guard = guarding_if(exposed[0], local_parents) if len(exposed) == 1 else None
        mark_guard = guarding_if(marks[0], local_parents) if len(marks) == 1 else None
        delivery = {
            "deliverable_has_two_writes": len(plaintext_writes) == 2,
            "deliverable_starts_empty": any(
                isinstance(value_of_assignment(node), ast.Constant)
                and value_of_assignment(node).value is None
                for node in plaintext_writes
            ),
            "candidate_has_initial_and_combine_writes": (
                len(candidate_writes) == 2 and len(combine_writes) == 1
                and any(
                    isinstance(value_of_assignment(node), ast.Constant)
                    and value_of_assignment(node).value is None
                    for node in candidate_writes
                )
            ),
            "combine_is_threshold_guarded": (
                isinstance(combine_guard, ast.If)
                and ast.unparse(combine_guard.test) == "threshold_reached"
            ),
            "gateway_guard_is_exact": (
                isinstance(gateway_value, ast.BoolOp)
                and isinstance(gateway_value.op, ast.And)
                and {ast.unparse(item) for item in gateway_value.values} == {
                    "aggregate_valid", "actual_consumer == ciphertext.buyer",
                }
            ),
            "exposure_is_gateway_guarded": (
                isinstance(expose_guard, ast.If)
                and ast.unparse(expose_guard.test) == "gateway_accepted"
            ),
            "ledger_success_has_same_guard": (
                mark_guard is expose_guard and isinstance(mark_guard, ast.If)
            ),
            "returned_field_is_guarded_deliverable": outcome_plaintext,
        }
    checks["THRESHOLD_AND_BUYER_GUARD_DELIVERY_ROOT"] = (
        bool(delivery) and all(delivery.values())
    )
    diagnostics["delivery_facts"] = delivery

    actual_fingerprints: dict[str, str] = {}
    for key in EXPECTED_CRITICAL_AST:
        relative, qualified = key.split("::", 1)
        node = indexes.get(relative, {}).get(qualified)
        if node is not None:
            actual_fingerprints[key] = ast_sha(node)
    checks["CRITICAL_NORMAL_FORMS_EXACT"] = (
        bool(EXPECTED_CRITICAL_AST)
        and actual_fingerprints == EXPECTED_CRITICAL_AST
    )
    diagnostics["critical_ast_sha256"] = actual_fingerprints

    op_text = texts.get(operator, "")
    coord_text = texts.get(coordinator, "")
    network_text = texts.get(network, "")
    runner_text = texts.get(runner, "")
    checks["RUNTIME_SOURCE_BINDING_END_TO_END"] = (
        "RUNTIME_SOURCE_FILES =" in op_text
        and all(f'"{name}"' in op_text for name in EXPECTED_RUNTIME_FILES)
        and op_text.count('"runtime_source_digest": RUNTIME_SOURCE_DIGEST') == 2
        and "runtime_source_digest=RUNTIME_SOURCE_DIGEST" in op_text
        and '"runtime_source_digest": runtime_source_digest' in network_text
        and 'payload.get("runtime_source_digest") != self.expected_runtime_source_digest'
        in coord_text
        and "runtime_source_digest=self.expected_runtime_source_digest" in coord_text
        and 'health[i].get("runtime_source_digest") == RUNTIME_SOURCE_DIGEST'
        in runner_text
    )

    bytecode = analyze_bytecode({
        module_name(path): text for path, text in texts.items()
    })
    checks["CPYTHON_BYTECODE_REPRESENTATION_CROSSCHECK"] = (
        bytecode.get("status") == "PASS"
    )

    rule_premises = {
        "R-CLOSURE": (
            "PYTHON_SYNTAX", "SOURCE_MODULE_SET_EXACT",
            "UNTRUSTED_INVENTORY_RECOMPUTED",
            "OPERATOR_IMPORT_CLOSURE_EXACT",
            "NO_DYNAMIC_NATIVE_OR_PROCESS_ESCAPE", "NO_WILDCARD_IMPORT",
            "PRIVILEGED_SYMBOLS_NOT_ALIASED_OR_REBOUND",
            "SINGLE_DECLARED_LISTENER", "CRITICAL_NORMAL_FORMS_EXACT",
        ),
        "R-EMIT": (
            "HANDLER_AND_ENTRY_METHODS_EXACT", "ROUTE_GUARDS_EXACT",
            "RAW_HTTP_SINKS_CONFINED", "PARTIAL_PRODUCER_SITE_UNIQUE",
            "SUCCESS_RESPONSE_DERIVED_FROM_PRODUCER",
        ),
        "R-SECRET": (
            "SECRET_SHARE_READ_CONFINED_TO_PRODUCER",
            "SENSITIVE_STATE_LIFECYCLE_EXACT",
            "SUCCESS_RESPONSE_DERIVED_FROM_PRODUCER",
        ),
        "R-LIFECYCLE": (
            "SENSITIVE_STATE_LIFECYCLE_EXACT",
            "RUNTIME_SOURCE_BINDING_END_TO_END",
            "OPERATOR_IMPORT_CLOSURE_EXACT",
        ),
        "R-DELIVER": (
            "RECONSTRUCTION_SITE_UNIQUE",
            "THRESHOLD_AND_BUYER_GUARD_DELIVERY_ROOT",
        ),
        "R-CROSS-REPRESENTATION": (
            "CPYTHON_BYTECODE_REPRESENTATION_CROSSCHECK",
        ),
    }
    rules = {
        name: {
            "premises": list(premises),
            "status": (
                "DERIVED" if all(checks.get(item, False) for item in premises)
                else "UNDERIVED"
            ),
        }
        for name, premises in rule_premises.items()
    }
    obligation_rules = {
        "LC1_SOURCE_PRODUCER_COMPLETENESS": ("R-CLOSURE", "R-EMIT"),
        "LC3_SOURCE_SECRET_CONFINEMENT": ("R-CLOSURE", "R-SECRET", "R-EMIT"),
        "LC5_SOURCE_LIFECYCLE_CLOSURE": ("R-CLOSURE", "R-LIFECYCLE"),
        "LC7_SOURCE_DELIVERY_ROOT": ("R-CLOSURE", "R-DELIVER"),
    }
    obligations = {
        name: {
            "rules": list(required),
            "status": (
                PROVED if all(rules[item]["status"] == "DERIVED" for item in required)
                else REJECTED
            ),
        }
        for name, required in obligation_rules.items()
    }
    proved = (
        all(checks.values())
        and all(item["status"] == PROVED for item in obligations.values())
    )

    return {
        "schema": SCHEMA,
        "status": PROVED if proved else REJECTED,
        "accepted_language": {
            "name": "RSP-V6",
            "scope": (
                "the exact module closure, privileged-operation grammar, critical "
                "normal forms, and declared first-four response service"
            ),
            "trace_events": [
                "request-entry", "share-read", "partial-create", "http-emit",
                "threshold-combine", "commitment-verify", "buyer-guard",
                "usable-deliver",
            ],
            "forbidden_constructs": [
                "dynamic import or execution",
                "reflection over capability-bearing state",
                "privileged-name aliasing or rebinding",
                "process or native-library escape",
                "undeclared listener or HTTP sink",
                "critical-function AST drift",
            ],
        },
        "checks": checks,        "rule_derivations": rules,
        "obligations": obligations,
        "source_sha256": {
            path: digest(text.encode("utf-8")) for path, text in sorted(texts.items())
        },
        "inventory_sha256": inventory_hash,
        "bytecode_crosscheck": bytecode,
        "diagnostics": diagnostics,
        "theorem_claim": (
            "For every standard-Python execution accepted by RSP-V6 whose loaded "
            "bytes equal the recorded hashes, every capability-bearing HTTP "
            "success is produced at the declared partial site; threshold shares "
            "reach external output only through that producer; the producer "
            "lifecycle is fixed by the signed runtime binding; and deliverable "
            "plaintext is populated only after threshold reconstruction, "
            "commitment verification, and the named-buyer guard."
        ),
        "assumptions": [
            "CPython parses and executes the accepted AST according to its documented semantics",
            "the imported standard-library primitives have their documented effects",
            "loaded application bytes equal the separately verified source hashes",
            "the operating system, interpreter, native runtime, and hardware are not compromised",
        ],
        "not_claimed": [
            "operating-system, interpreter, firmware, side-channel, or physical security",
            "hardware non-exportability or secure dealer erasure",
            "closure of mechanisms outside RSP-V6",
            "deployment-wide refinement",
            "independent economic control of operators",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the RSP-V6 source proof without trusting a status bit."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "results" / "source_coverage_kernel.v1.json",
    )
    args = parser.parse_args()
    result = analyze(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    for name, ok in result["checks"].items():
        print(f"{name}={'PASS' if ok else 'FAIL'}")
    for name, item in result["obligations"].items():
        print(f"{name}={item['status']}")
    print(f"RESTRICTED_SOURCE_KERNEL={result['status']}")
    print(f"SOURCE_COVERAGE_RESULT={args.output}")
    return 0 if result["status"] == PROVED else 1


if __name__ == "__main__":
    raise SystemExit(main())
