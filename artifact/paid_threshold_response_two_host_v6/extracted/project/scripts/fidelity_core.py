from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable

SCHEMA = "ptr-code-manifest-fidelity/v1"
DEFAULT_HASH_ROOTS = ("src/ptr_v3", "scripts", "powershell", "tests")
DEFAULT_EXTENSIONS = (".py", ".ps1")
DEFAULT_PINNED_FILES = ("RESTRICTED_SOURCE_SOUNDNESS.md",)
DEFAULT_PUBLIC_ROUTES = ("/health", "/respond")
DEFAULT_SURFACE_ROOTS = ("src/ptr_v3", "powershell")

_DYNAMIC_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "importlib.import_module",
    "runpy.run_module",
    "runpy.run_path",
    "ctypes.CDLL",
    "ctypes.PyDLL",
}
_PROCESS_CALL_PREFIXES = (
    "subprocess.",
    "os.system",
    "os.popen",
)
_SERVER_CALL_TAILS = {
    "HTTPServer",
    "ThreadingHTTPServer",
    "TCPServer",
    "ThreadingTCPServer",
    "UnixStreamServer",
    "ThreadingUnixStreamServer",
    "create_server",
}
_PS_SENSITIVE = {
    "Invoke-Expression": re.compile(r"(?im)^\s*(?:Invoke-Expression|iex)\b"),
    "Start-Process": re.compile(r"(?im)^\s*Start-Process\b"),
    "Start-Job": re.compile(r"(?im)^\s*Start-Job\b"),
    "Add-Type": re.compile(r"(?im)^\s*Add-Type\b"),
    "TcpListener": re.compile(r"(?i)TcpListener"),
    "HttpListener": re.compile(r"(?i)HttpListener"),
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def discover_code_files(root: Path, hash_roots: Iterable[str] = DEFAULT_HASH_ROOTS) -> list[Path]:
    files: list[Path] = []
    for rel in hash_roots:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix.lower() not in DEFAULT_EXTENSIONS:
                continue
            files.append(path)
    for rel in DEFAULT_PINNED_FILES:
        path = root / rel
        if path.is_file():
            files.append(path)
    return sorted(set(files), key=lambda p: rel_posix(p, root))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _base_tail(node: ast.AST) -> str:
    name = _call_name(node)
    return name.rsplit(".", 1)[-1] if name else ""


def _is_path_reference(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "path"


def _string_constants(node: ast.AST) -> list[str]:
    values: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.append(child.value)
    return values


@dataclass(frozen=True)
class PythonSurface:
    syntax_ok: bool
    handler_methods: tuple[dict[str, Any], ...]
    http_routes: tuple[dict[str, Any], ...]
    producer_send_sites: tuple[dict[str, Any], ...]
    server_sites: tuple[dict[str, Any], ...]
    dynamic_exec_sites: tuple[dict[str, Any], ...]
    process_spawn_sites: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "syntax_ok": self.syntax_ok,
            "handler_methods": list(self.handler_methods),
            "http_routes": list(self.http_routes),
            "producer_send_sites": list(self.producer_send_sites),
            "server_sites": list(self.server_sites),
            "dynamic_exec_sites": list(self.dynamic_exec_sites),
            "process_spawn_sites": list(self.process_spawn_sites),
        }


def analyze_python(path: Path, root: Path) -> PythonSurface:
    rel = rel_posix(path, root)
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=rel)
    except (UnicodeDecodeError, SyntaxError):
        return PythonSurface(False, (), (), (), (), (), ())

    handler_methods: list[dict[str, Any]] = []
    http_routes: list[dict[str, Any]] = []
    producer_send_sites: list[dict[str, Any]] = []
    server_sites: list[dict[str, Any]] = []
    dynamic_exec_sites: list[dict[str, Any]] = []
    process_spawn_sites: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            tail = name.rsplit(".", 1)[-1] if name else ""
            if name in _DYNAMIC_CALLS:
                dynamic_exec_sites.append({"file": rel, "line": node.lineno, "call": name})
            if any(name == prefix or name.startswith(prefix) for prefix in _PROCESS_CALL_PREFIXES):
                process_spawn_sites.append({"file": rel, "line": node.lineno, "call": name})
            if tail in _SERVER_CALL_TAILS:
                server_sites.append({"file": rel, "line": node.lineno, "call": name})

    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        base_tails = {_base_tail(base) for base in cls.bases}
        looks_like_handler = "BaseHTTPRequestHandler" in base_tails or any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("do_")
            for item in cls.body
        )
        if not looks_like_handler:
            continue
        for item in cls.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) or not item.name.startswith("do_"):
                continue
            handler_methods.append({"file": rel, "class": cls.name, "method": item.name, "line": item.lineno})
            for sub in ast.walk(item):
                if isinstance(sub, ast.Compare):
                    has_path = _is_path_reference(sub.left) or any(_is_path_reference(c) for c in sub.comparators)
                    if has_path:
                        for value in _string_constants(sub):
                            if value.startswith("/"):
                                http_routes.append(
                                    {"file": rel, "class": cls.name, "method": item.name, "route": value, "line": sub.lineno}
                                )
                if isinstance(sub, ast.Call):
                    call = _call_name(sub.func)
                    if call.endswith("._send") or call.endswith(".send_response") or call.endswith(".wfile.write"):
                        producer_send_sites.append(
                            {"file": rel, "class": cls.name, "method": item.name, "call": call, "line": sub.lineno}
                        )

    def norm(items: list[dict[str, Any]], keys: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
        unique = {tuple(item.get(k) for k in keys): item for item in items}
        return tuple(unique[k] for k in sorted(unique))

    return PythonSurface(
        True,
        norm(handler_methods, ("file", "class", "method", "line")),
        norm(http_routes, ("file", "class", "method", "route", "line")),
        norm(producer_send_sites, ("file", "class", "method", "call", "line")),
        norm(server_sites, ("file", "call", "line")),
        norm(dynamic_exec_sites, ("file", "call", "line")),
        norm(process_spawn_sites, ("file", "call", "line")),
    )


def analyze_powershell(path: Path, root: Path) -> dict[str, Any]:
    rel = rel_posix(path, root)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8-sig")
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    for name, pattern in _PS_SENSITIVE.items():
        for index, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append({"file": rel, "line": index, "construct": name})
    return {"sensitive_sites": sorted(findings, key=lambda x: (x["file"], x["line"], x["construct"]))}


def derive_surface(
    root: Path,
    files: Iterable[Path],
    surface_roots: Iterable[str] = DEFAULT_SURFACE_ROOTS,
) -> dict[str, Any]:
    prefixes = tuple(str(x).rstrip("/") + "/" for x in surface_roots)
    scoped = [p for p in files if rel_posix(p, root).startswith(prefixes)]
    py = [p for p in scoped if p.suffix.lower() == ".py"]
    ps = [p for p in scoped if p.suffix.lower() == ".ps1"]
    py_surfaces = [analyze_python(path, root) for path in py]
    syntax_ok = all(surface.syntax_ok for surface in py_surfaces)

    def flatten(field: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for surface in py_surfaces:
            out.extend(getattr(surface, field))
        return sorted(out, key=lambda item: tuple(str(item[k]) for k in sorted(item)))

    ps_sites: list[dict[str, Any]] = []
    for path in ps:
        ps_sites.extend(analyze_powershell(path, root)["sensitive_sites"])

    return {
        "python_syntax_ok": syntax_ok,
        "handler_methods": flatten("handler_methods"),
        "http_routes": flatten("http_routes"),
        "producer_send_sites": flatten("producer_send_sites"),
        "server_sites": flatten("server_sites"),
        "dynamic_exec_sites": flatten("dynamic_exec_sites"),
        "process_spawn_sites": flatten("process_spawn_sites"),
        "powershell_sensitive_sites": sorted(ps_sites, key=lambda x: (x["file"], x["line"], x["construct"])),
    }


def build_manifest(
    root: Path,
    *,
    hash_roots: Iterable[str] = DEFAULT_HASH_ROOTS,
    expected_public_routes: Iterable[str] = DEFAULT_PUBLIC_ROUTES,
    surface_roots: Iterable[str] = DEFAULT_SURFACE_ROOTS,
) -> dict[str, Any]:
    files = discover_code_files(root, hash_roots)
    if not files:
        raise RuntimeError("no runtime code files discovered; run this from the project root")
    hashes = {rel_posix(path, root): sha256_file(path) for path in files}
    surface = derive_surface(root, files, surface_roots)
    server_routes = sorted({item["route"] for item in surface["http_routes"]})
    expected = sorted(set(expected_public_routes))
    if server_routes != expected:
        raise RuntimeError(
            f"server-side HTTP route surface is {server_routes}, expected exactly {expected}; "
            "inspect the runtime before freezing the manifest"
        )
    if not surface["python_syntax_ok"]:
        raise RuntimeError("at least one Python source file does not parse")
    if surface["dynamic_exec_sites"]:
        raise RuntimeError(f"dynamic execution sites present: {surface['dynamic_exec_sites']}")
    return {
        "schema": SCHEMA,
        "claim_scope": {
            "claim": "byte-bound and statically extracted code-to-manifest fidelity for the controlled Python, PowerShell, and test tree",
            "not_claimed": [
                "semantic equivalence to arbitrary deployed binaries",
                "absence of OS, firmware, hardware, side-channel, or off-tree routes",
                "deployment-wide route discovery",
            ],
        },
        "hash_roots": list(hash_roots),
        "surface_roots": list(surface_roots),
        "expected_public_http_routes": expected,
        "files": hashes,
        "surface": surface,
    }


def manifest_digest(manifest: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(manifest))


def write_manifest(manifest: dict[str, Any], manifest_path: Path, digest_path: Path | None = None) -> str:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(canonical_bytes(manifest))
    digest = manifest_digest(manifest)
    target = digest_path or manifest_path.with_suffix(manifest_path.suffix + ".sha256")
    target.write_text(digest + "\n", encoding="ascii", newline="\n")
    return digest


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != SCHEMA:
        raise RuntimeError(f"unexpected manifest schema: {value.get('schema')!r}")
    return value


def compare_surface(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, bool]:
    keys = (
        "handler_methods",
        "http_routes",
        "producer_send_sites",
        "server_sites",
        "dynamic_exec_sites",
        "process_spawn_sites",
        "powershell_sensitive_sites",
    )
    checks = {f"SURFACE_{key.upper()}_EXACT": actual.get(key) == expected.get(key) for key in keys}
    checks["PYTHON_SYNTAX"] = actual.get("python_syntax_ok") is True
    return checks


def verify_tree(
    root: Path,
    manifest: dict[str, Any],
    *,
    expected_manifest_digest: str | None = None,
) -> dict[str, Any]:
    expected_files: dict[str, str] = dict(manifest["files"])
    current_files = discover_code_files(root, manifest.get("hash_roots", DEFAULT_HASH_ROOTS))
    current_rel = [rel_posix(p, root) for p in current_files]
    expected_rel = sorted(expected_files)

    missing = sorted(set(expected_rel) - set(current_rel))
    extra = sorted(set(current_rel) - set(expected_rel))
    hash_mismatches: list[dict[str, str]] = []
    for rel in sorted(set(expected_rel) & set(current_rel)):
        actual_hash = sha256_file(root / rel)
        if actual_hash != expected_files[rel]:
            hash_mismatches.append({"file": rel, "expected": expected_files[rel], "actual": actual_hash})

    actual_surface = derive_surface(root, current_files, manifest.get("surface_roots", DEFAULT_SURFACE_ROOTS))
    surface_checks = compare_surface(manifest["surface"], actual_surface)
    actual_routes = sorted({item["route"] for item in actual_surface["http_routes"]})
    route_policy_ok = actual_routes == sorted(manifest["expected_public_http_routes"])
    digest = manifest_digest(manifest)

    checks: dict[str, bool] = {
        "MANIFEST_SCHEMA": manifest.get("schema") == SCHEMA,
        "MANIFEST_DIGEST": expected_manifest_digest is None or digest == expected_manifest_digest.upper(),
        "FILE_SET_EXACT": not missing and not extra,
        "FILE_HASHES_EXACT": not hash_mismatches,
        "EXPECTED_PUBLIC_ROUTES_EXACT": route_policy_ok,
        "NO_DYNAMIC_EXEC": not actual_surface["dynamic_exec_sites"],
        **surface_checks,
    }
    passed = all(checks.values())
    return {
        "schema": "ptr-code-manifest-fidelity-result/v1",
        "status": "PASS" if passed else "FAIL",
        "manifest_sha256": digest,
        "checks": checks,
        "diagnostics": {
            "missing_files": missing,
            "extra_files": extra,
            "hash_mismatches": hash_mismatches,
            "actual_public_http_routes": actual_routes,
            "surface_differences": {
                key: {"expected": manifest["surface"].get(key), "actual": actual_surface.get(key)}
                for key in (
                    "handler_methods",
                    "http_routes",
                    "producer_send_sites",
                    "server_sites",
                    "dynamic_exec_sites",
                    "process_spawn_sites",
                    "powershell_sensitive_sites",
                )
                if manifest["surface"].get(key) != actual_surface.get(key)
            },
        },
        "scope": manifest["claim_scope"],
    }


def print_result(result: dict[str, Any]) -> None:
    checks = result["checks"]
    width = max(len(name) for name in checks)
    for name, ok in checks.items():
        print(f"{name.ljust(width)}  {'PASS' if ok else 'FAIL'}")
    print(f"MANIFEST_SHA256={result['manifest_sha256']}")
    print(f"CODE_TO_MANIFEST_FIDELITY={result['status']}")
